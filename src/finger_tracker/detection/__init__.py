"""リアルタイム指間距離計測モジュール（ADR 002, 005, 007, 008）"""

import csv
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import cv2
import numpy as np
import pyrealsense2 as rs
from ultralytics import YOLO

from finger_tracker.config import load_config

logger = logging.getLogger(__name__)

_JST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# カルマンフィルタ（ADR 002 判断2: 各指独立 3D 等速度モデル）
# ---------------------------------------------------------------------------

class KalmanFilter3D:
    """3D 等速度モデルのカルマンフィルタ。

    状態: [x, y, z, vx, vy, vz] (6D)
    観測: [x, y, z] (3D)
    """

    def __init__(self, q: float, r: float, dt: float):
        self.dt = dt
        # 状態ベクトル
        self.x = np.zeros(6)
        # 共分散行列
        self.P = np.eye(6) * 1.0
        # 遷移行列 F（等速度モデル）
        self.F = np.eye(6)
        self.F[0, 3] = dt
        self.F[1, 4] = dt
        self.F[2, 5] = dt
        # 観測行列 H
        self.H = np.zeros((3, 6))
        self.H[0, 0] = 1.0
        self.H[1, 1] = 1.0
        self.H[2, 2] = 1.0
        # プロセスノイズ Q
        self.Q = np.eye(6) * q
        # 観測ノイズ R
        self.R = np.eye(3) * r
        self._initialized = False

    def predict(self):
        """予測ステップ。"""
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update(self, measurement: np.ndarray):
        """更新ステップ。

        Args:
            measurement: [x, y, z] の観測値。
        """
        if not self._initialized:
            self.x[:3] = measurement
            self._initialized = True
            return
        y = measurement - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ self.H) @ self.P

    def get_position(self) -> np.ndarray:
        """フィルタ済み位置 [x, y, z] を返す。"""
        return self.x[:3].copy()


# ---------------------------------------------------------------------------
# HSV フィルタ（ADR 002 判断1）
# ---------------------------------------------------------------------------

def _hsv_mask(roi_bgr: np.ndarray, hsv_params: dict) -> np.ndarray:
    """BB 内 ROI に対して HSV 色フィルタを適用しマスクを返す。"""
    hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_params["lower"]), np.array(hsv_params["upper"]))
    if "lower2" in hsv_params:
        mask2 = cv2.inRange(hsv, np.array(hsv_params["lower2"]), np.array(hsv_params["upper2"]))
        mask = cv2.bitwise_or(mask, mask2)
    return mask


def _mask_centroid(mask: np.ndarray):
    """マスクの重心ピクセル座標 (cx, cy) を返す。見つからなければ None。"""
    M = cv2.moments(mask)
    if M["m00"] == 0:
        return None
    return int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])


# ---------------------------------------------------------------------------
# 深度フォールバック（ADR 002 判断3）
# ---------------------------------------------------------------------------

def _get_depth(depth_frame, mask: np.ndarray, cx: int, cy: int,
               x1: int, y1: int, x2: int, y2: int,
               last_depth: float, last_depth_time: float,
               depth_timeout: float) -> tuple[float, float]:
    """深度値をフォールバックチェーンで取得する。

    Returns:
        (depth_value, last_depth_time) — depth_value=0 なら計測不能。
    """
    now = time.monotonic()

    # 1. マスク内有効ピクセルの中央値（ノイズ耐性を優先）
    ys, xs = np.where(mask > 0)
    if len(ys) > 0:
        vals = np.array([depth_frame.get_distance(x1 + int(mx), y1 + int(my))
                         for my, mx in zip(ys, xs)])
        valid = vals[vals > 0]
        if len(valid) > 0:
            return float(np.median(valid)), now

    # 2. マスク重心の深度（マスク内で有効値がない場合のフォールバック）
    d = depth_frame.get_distance(cx, cy)
    if d > 0:
        return d, now

    # 3. BB 内全体で有効ピクセル探索
    bb_depths = []
    for by in range(y1, y2, 2):  # ステップ2でサンプリング
        for bx in range(x1, x2, 2):
            val = depth_frame.get_distance(bx, by)
            if val > 0:
                bb_depths.append(val)
    if bb_depths:
        return float(np.median(bb_depths)), now

    # 4. 直前値保持（タイムアウト付き）
    if last_depth > 0 and (now - last_depth_time) < depth_timeout:
        return last_depth, last_depth_time

    return 0.0, now


# ---------------------------------------------------------------------------
# 検出処理
# ---------------------------------------------------------------------------

def _process_detection(box, class_name: str, color_image: np.ndarray,
                       depth_frame, intrinsics,
                       hsv_config: dict, depth_timeout: float,
                       last_depths: dict, last_depth_times: dict):
    """1つの検出結果から 3D 座標を取得する。

    Returns:
        (point_3d, conf, pixel) — point_3d は [x,y,z] (meters) or None。
            pixel は (cx, cy) マスク重心ピクセル座標 or None。
    """
    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
    conf = float(box.conf[0])

    # BB クリップ
    h, w = color_image.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    if x2 <= x1 or y2 <= y1:
        return None, conf, None

    # HSV フィルタ → マスク重心
    roi = color_image[y1:y2, x1:x2]
    hsv_key = "red" if class_name == "red_finger" else "blue"
    mask = _hsv_mask(roi, hsv_config[hsv_key])
    centroid = _mask_centroid(mask)

    if centroid is None:
        return None, conf, None

    cx_local, cy_local = centroid
    cx, cy = x1 + cx_local, y1 + cy_local

    # 深度取得（フォールバック付き）
    last_d = last_depths.get(class_name, 0.0)
    last_t = last_depth_times.get(class_name, 0.0)
    depth, dep_time = _get_depth(depth_frame, mask, cx, cy,
                                  x1, y1, x2, y2,
                                  last_d, last_t, depth_timeout)
    last_depths[class_name] = depth
    last_depth_times[class_name] = dep_time

    if depth <= 0:
        return None, conf, (cx, cy)

    # 3D 座標変換
    point_3d = rs.rs2_deproject_pixel_to_point(intrinsics, [cx, cy], depth)
    return np.array(point_3d), conf, (cx, cy)


# ---------------------------------------------------------------------------
# 描画（ADR 005）
# ---------------------------------------------------------------------------

_RED_COLOR = (0, 0, 255)
_BLUE_COLOR = (255, 100, 0)
_WHITE = (255, 255, 255)
_GREEN = (0, 255, 0)


def _draw_overlay(image: np.ndarray, results, fps: float,
                  distance_mm: float | None,
                  red_conf: float | None, blue_conf: float | None,
                  centroid_pixels: dict):
    """BB、距離線、ステータス情報を描画する。"""
    h, w = image.shape[:2]

    # BB 描画
    if results and len(results) > 0:
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            cls_id = int(box.cls[0])
            cls_name = results[0].names[cls_id]
            color = _RED_COLOR if cls_name == "red_finger" else _BLUE_COLOR
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

    # 距離線（両方のマスク重心が取得できている時）
    red_px = centroid_pixels.get("red_finger")
    blue_px = centroid_pixels.get("blue_finger")
    if red_px is not None and blue_px is not None:
        cv2.line(image, red_px, blue_px, _GREEN, 2)
        mid = ((red_px[0] + blue_px[0]) // 2, (red_px[1] + blue_px[1]) // 2 - 10)
        if distance_mm is not None:
            cv2.putText(image, f"{distance_mm:.1f}mm", mid,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, _GREEN, 2)

    # 上部: FPS + Conf
    conf_text = "Conf: "
    conf_text += f"{red_conf:.2f}" if red_conf is not None else "---"
    conf_text += "/"
    conf_text += f"{blue_conf:.2f}" if blue_conf is not None else "---"
    cv2.putText(image, f"FPS: {fps:.0f}  {conf_text}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, _WHITE, 2)

    # 下部: 距離を大きく表示
    if distance_mm is not None:
        dist_text = f"Distance: {distance_mm:.1f} mm"
    else:
        dist_text = "Distance: --- mm"
    cv2.putText(image, dist_text, (10, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, _GREEN, 2)


# ---------------------------------------------------------------------------
# CSV 記録（ADR 007）
# ---------------------------------------------------------------------------

_CSV_HEADER = ["timestamp", "distance_mm",
               "red_x", "red_y", "red_z",
               "blue_x", "blue_y", "blue_z",
               "red_conf", "blue_conf"]


def _open_csv(session_time: str) -> tuple:
    """CSV ファイルを開き、(file, writer) を返す。"""
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"measurement_{session_time}.csv"
    f = open(path, "w", newline="")
    writer = csv.writer(f)
    writer.writerow(_CSV_HEADER)
    logger.info("CSV 記録開始: %s", path)
    return f, writer


def _write_csv_row(writer, distance_mm: float | None,
                   red_pos, blue_pos,
                   red_conf: float | None, blue_conf: float | None):
    """1フレーム分のデータを書き込む。"""
    ts = datetime.now(_JST).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
    row = [ts]
    row.append(f"{distance_mm:.1f}" if distance_mm is not None else "")
    if red_pos is not None:
        row.extend([f"{red_pos[0]:.4f}", f"{red_pos[1]:.4f}", f"{red_pos[2]:.4f}"])
    else:
        row.extend(["", "", ""])
    if blue_pos is not None:
        row.extend([f"{blue_pos[0]:.4f}", f"{blue_pos[1]:.4f}", f"{blue_pos[2]:.4f}"])
    else:
        row.extend(["", "", ""])
    row.append(f"{red_conf:.2f}" if red_conf is not None else "")
    row.append(f"{blue_conf:.2f}" if blue_conf is not None else "")
    writer.writerow(row)


# ---------------------------------------------------------------------------
# ログ設定（ADR 007）
# ---------------------------------------------------------------------------

def _setup_logging(session_time: str):
    """ファイル + コンソールのログ設定。"""
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"app_{session_time}.log"

    root_logger = logging.getLogger("finger_tracker")
    root_logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(levelname)s %(message)s"))

    root_logger.addHandler(fh)
    root_logger.addHandler(ch)


# ---------------------------------------------------------------------------
# メインループ
# ---------------------------------------------------------------------------

_MAX_RETRY = 3
_RETRY_INTERVAL = 1.0


def run():
    """detection のメインループ。"""
    config = load_config()
    cam = config["camera"]
    hsv_config = config["hsv"]
    flt = config["filter"]
    model_path = config["model"]["path"]

    session_time = datetime.now(_JST).strftime("%Y-%m-%d_%H%M%S")
    _setup_logging(session_time)

    # モデル存在チェック（ADR 008）
    if not Path(model_path).exists():
        print(f"ERROR: モデルファイルが見つかりません: {model_path}")
        print("  config.yaml の model.path を確認、または学習を実行してください。")
        return

    model = YOLO(model_path)
    logger.info("モデルロード完了: %s", model_path)

    # RealSense 初期化（ADR 008）
    pipeline = rs.pipeline()
    rs_config = rs.config()
    rs_config.enable_stream(rs.stream.color, cam["width"], cam["height"], rs.format.bgr8, cam["fps"])
    rs_config.enable_stream(rs.stream.depth, cam["width"], cam["height"], rs.format.z16, cam["fps"])

    try:
        profile = pipeline.start(rs_config)
    except RuntimeError as e:
        print(f"ERROR: RealSense D435i が見つかりません: {e}")
        print("  USB 接続を確認してください。rs-enumerate-devices で確認できます。")
        return

    align = rs.align(rs.stream.color)
    intrinsics = profile.get_stream(rs.stream.color).as_video_stream_profile().get_intrinsics()

    # カルマンフィルタ初期化
    dt = 1.0 / cam["fps"]
    kf_red = KalmanFilter3D(flt["kalman_q"], flt["kalman_r"], dt)
    kf_blue = KalmanFilter3D(flt["kalman_q"], flt["kalman_r"], dt)
    kf_map = {"red_finger": kf_red, "blue_finger": kf_blue}

    # 状態変数
    last_depths: dict[str, float] = {}
    last_depth_times: dict[str, float] = {}
    confidence = config["model"]["confidence"]

    # CSV
    csv_file, csv_writer = _open_csv(session_time)

    logger.info("計測開始 — camera: %dx%d@%dfps", cam["width"], cam["height"], cam["fps"])
    print("計測開始 — q/ESC で終了")

    prev_time = time.monotonic()
    retry_count = 0

    try:
        while True:
            # フレーム取得（リトライ付き、ADR 008 判断2）
            try:
                frames = pipeline.wait_for_frames(timeout_ms=5000)
                retry_count = 0
            except RuntimeError:
                retry_count += 1
                logger.warning("フレーム取得失敗 (%d/%d)", retry_count, _MAX_RETRY)
                if retry_count >= _MAX_RETRY:
                    logger.warning("RealSense 復帰不能 — 終了します")
                    break
                time.sleep(_RETRY_INTERVAL)
                continue

            aligned = align.process(frames)
            color_frame = aligned.get_color_frame()
            depth_frame = aligned.get_depth_frame()
            if not color_frame or not depth_frame:
                continue

            color_image = np.asanyarray(color_frame.get_data())

            # YOLO 推論
            results = model(color_image, conf=confidence, verbose=False)

            # 各指の処理
            red_pos = blue_pos = None
            red_conf = blue_conf = None
            centroid_pixels: dict[str, tuple[int, int] | None] = {}

            # 検出結果をクラス名でマッピング
            detected: dict[str, object] = {}
            if results and len(results) > 0:
                for box in results[0].boxes:
                    cls_name = results[0].names[int(box.cls[0])]
                    if cls_name in kf_map:
                        detected[cls_name] = box

            # 全フィルタに predict() を実行し、検出時のみ update()（ADR 002）
            for cls_name, kf in kf_map.items():
                kf.predict()

                if cls_name in detected:
                    box = detected[cls_name]
                    point_3d, conf, pixel = _process_detection(
                        box, cls_name, color_image, depth_frame, intrinsics,
                        hsv_config, flt["depth_timeout"],
                        last_depths, last_depth_times,
                    )

                    if point_3d is not None:
                        kf.update(point_3d)

                    pos = kf.get_position() if kf._initialized else None
                    centroid_pixels[cls_name] = pixel

                    if cls_name == "red_finger":
                        red_pos = pos
                        red_conf = conf
                    else:
                        blue_pos = pos
                        blue_conf = conf
                else:
                    # 未検出: predict のみ（フィルタ状態を進める）
                    if kf._initialized:
                        pos = kf.get_position()
                        if cls_name == "red_finger":
                            red_pos = pos
                        else:
                            blue_pos = pos

            # 距離計算
            distance_mm = None
            if red_pos is not None and blue_pos is not None:
                distance_mm = float(np.linalg.norm(red_pos - blue_pos) * 1000)

            # FPS
            now = time.monotonic()
            fps = 1.0 / max(now - prev_time, 1e-6)
            prev_time = now

            # 描画
            _draw_overlay(color_image, results, fps, distance_mm,
                          red_conf, blue_conf, centroid_pixels)
            cv2.imshow("Detection", color_image)

            # CSV
            _write_csv_row(csv_writer, distance_mm, red_pos, blue_pos,
                           red_conf, blue_conf)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                break

    except KeyboardInterrupt:
        logger.info("ユーザーによる終了 (Ctrl+C)")
    except Exception as e:
        logger.error("予期しないエラー: %s", e)
    finally:
        csv_file.flush()
        csv_file.close()
        pipeline.stop()
        cv2.destroyAllWindows()
        logger.info("計測終了")
        print("終了")
