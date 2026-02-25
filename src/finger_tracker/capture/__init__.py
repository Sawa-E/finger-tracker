"""RealSense キャプチャモジュール（ADR 003, 008）"""

import logging
import re
from pathlib import Path

import cv2
import numpy as np
import pyrealsense2 as rs

from finger_tracker.config import load_config

logger = logging.getLogger(__name__)


def _find_next_index(output_dir: Path, prefix: str) -> int:
    """既存ファイルの最大連番 + 1 を返す。"""
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)_rgb\.png$")
    max_idx = 0
    if output_dir.exists():
        for f in output_dir.iterdir():
            m = pattern.match(f.name)
            if m:
                max_idx = max(max_idx, int(m.group(1)))
    return max_idx + 1 if max_idx > 0 else 1


def run():
    """キャプチャのメインループ。"""
    config = load_config()
    cam = config["camera"]
    cap = config["capture"]

    output_dir = Path(cap["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = cap["prefix"]
    idx = _find_next_index(output_dir, prefix)
    saved = 0

    # RealSense 初期化
    pipeline = rs.pipeline()
    rs_config = rs.config()
    rs_config.enable_stream(rs.stream.color, cam["width"], cam["height"], rs.format.bgr8, cam["fps"])
    rs_config.enable_stream(rs.stream.depth, cam["width"], cam["height"], rs.format.z16, cam["fps"])

    try:
        pipeline.start(rs_config)
    except RuntimeError as e:
        logger.error("RealSense D435i が見つかりません: %s", e)
        print(f"ERROR: RealSense D435i が見つかりません: {e}")
        print("  USB 接続を確認してください。rs-enumerate-devices で確認できます。")
        return

    align = rs.align(rs.stream.color)

    try:
        print(f"キャプチャ開始 — 保存先: {output_dir}/")
        print("  s: 保存  q/ESC: 終了")

        while True:
            frames = pipeline.wait_for_frames()
            aligned = align.process(frames)
            color_frame = aligned.get_color_frame()
            depth_frame = aligned.get_depth_frame()

            if not color_frame or not depth_frame:
                continue

            color_image = np.asanyarray(color_frame.get_data())
            depth_array = np.asanyarray(depth_frame.get_data())

            # プレビュー表示
            display = color_image.copy()
            cv2.putText(display, f"Saved: {saved}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Capture", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("s"):
                tag = f"{prefix}_{idx:03d}"
                cv2.imwrite(str(output_dir / f"{tag}_rgb.png"), color_image)
                np.save(str(output_dir / f"{tag}_depth.npy"), depth_array)
                print(f"  保存: {tag}")
                idx += 1
                saved += 1
            elif key == ord("q") or key == 27:
                break

    except KeyboardInterrupt:
        logger.info("ユーザーによる終了 (Ctrl+C)")
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()
        print(f"終了 — 合計 {saved} 枚保存")
