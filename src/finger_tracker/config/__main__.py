"""設定確認用エントリポイント: python -m finger_tracker.config"""

import json

from finger_tracker.config import load_config


def main():
    config = load_config()
    print(json.dumps(config, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
