"""設定管理モジュール（ADR 006）"""

from pathlib import Path

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config.yaml"

_DEFAULTS = {
    "camera": {"width": 1280, "height": 720, "fps": 30},
    "model": {"path": "models/best.pt", "confidence": 0.5},
    "hsv": {
        "red": {
            "lower": [0, 120, 70],
            "upper": [10, 255, 255],
            "lower2": [170, 120, 70],
            "upper2": [180, 255, 255],
        },
        "blue": {"lower": [100, 120, 70], "upper": [130, 255, 255]},
    },
    "filter": {"kalman_q": 0.01, "kalman_r": 0.1, "depth_timeout": 0.5},
    "display": {"fps_target": 30},
    "capture": {"output_dir": "data/images", "prefix": "frame"},
}


def _deep_merge(base: dict, override: dict) -> dict:
    """base に override をマージする。override 側が優先。"""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path | None = None) -> dict:
    """config.yaml を読み込み、デフォルト値とマージして返す。

    Args:
        path: 設定ファイルのパス。None の場合はプロジェクトルートの config.yaml を使用。

    Returns:
        設定値の dict。
    """
    config_path = path or _DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise FileNotFoundError(
            f"ERROR: config.yaml が見つかりません: {config_path}\n"
            "  プロジェクトルートに config.yaml を配置してください。"
        )

    try:
        with open(config_path) as f:
            user_config = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(
            f"ERROR: config.yaml の解析に失敗: {e}"
        ) from e

    return _deep_merge(_DEFAULTS, user_config)
