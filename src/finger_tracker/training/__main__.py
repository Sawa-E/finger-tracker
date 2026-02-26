"""学習エントリポイント: python -m finger_tracker.training"""

from finger_tracker.config import load_config
from finger_tracker.training import evaluate_and_deploy, train


def main():
    config = load_config()
    print("YOLOv8-nano fine-tuning 開始...")
    results = train(config)
    evaluate_and_deploy(config, results)
    print("完了")


if __name__ == "__main__":
    main()
