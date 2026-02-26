"""YOLOv8-nano fine-tuning モジュール（ADR 004）"""

import logging
import shutil
from pathlib import Path

from ultralytics import YOLO

logger = logging.getLogger(__name__)

_TARGET_MAP50 = 0.90


def train(config: dict):
    """YOLOv8-nano の fine-tuning を実行する。

    Args:
        config: load_config() で取得した設定 dict。

    Returns:
        ultralytics の学習結果オブジェクト。
    """
    t = config["training"]
    dataset_path = Path(t["dataset"])

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"ERROR: データセットが見つかりません: {dataset_path}\n"
            "  Roboflow からエクスポートしたデータセットを配置してください。"
        )

    model = YOLO(t["base_model"])
    results = model.train(
        data=str(dataset_path),
        epochs=t["epochs"],
        patience=t["patience"],
        batch=t["batch"],
        imgsz=t["imgsz"],
        augment=False,  # Roboflow で拡張済み（ADR 004）
    )
    return results


def evaluate_and_deploy(config: dict, results):
    """学習結果を評価し、best.pt を models/ に配置する。

    Args:
        config: load_config() で取得した設定 dict。
        results: train() の戻り値。
    """
    # mAP50 取得
    metrics = results.results_dict
    map50 = metrics.get("metrics/mAP50(B)", 0.0)

    print(f"\n{'='*40}")
    print(f"  mAP50: {map50:.4f}  (目標: {_TARGET_MAP50})")
    print(f"{'='*40}")

    if map50 >= _TARGET_MAP50:
        logger.info("目標達成: mAP50 = %.4f >= %.2f", map50, _TARGET_MAP50)
    else:
        logger.warning(
            "目標未達: mAP50 = %.4f < %.2f — "
            "改善方針: 1)データ確認 2)データ追加 3)拡張調整 4)モデルスケールアップ（ADR 004）",
            map50, _TARGET_MAP50,
        )

    # best.pt を models/ にコピー
    best_pt = Path(results.save_dir) / "weights" / "best.pt"
    models_dir = Path(config["model"]["path"]).parent
    models_dir.mkdir(parents=True, exist_ok=True)
    dest = models_dir / "best.pt"

    shutil.copy2(best_pt, dest)
    print(f"  モデル配置: {dest}")
