# finger-tracker

RealSense D435i と YOLOv8-nano による指間距離リアルタイム計測システム

## 概要

赤・青のシリコン製指サック（カラーマーカー）を YOLOv8-nano で検出し、RealSense D435i の深度データから 3D 空間上の指間距離をリアルタイムに計測します。

将来的にはロボットハンドの遠隔操作指令値として使用し、バイラテラルテレオペレーションシステムへの発展を目指しています。

## 処理フロー

```
RealSense D435i
    ├── RGB フレーム → YOLOv8-nano → red_finger / blue_finger 検出
    │                                    ↓
    │                          BB内HSVフィルタ → マスク重心
    │                                    ↓
    └── 深度フレーム ──────→ マスク重心の深度値取得
                                ↓
              rs2_deproject_pixel_to_point で 3D座標変換
                                ↓
              各指独立 3D カルマンフィルタ（等速度モデル）
                                ↓
              フィルタ済み座標間のユークリッド距離 = 指間距離
                                ↓
              OpenCV表示 + CSV記録
```

## 必要環境

- Python 3.12+
- Intel RealSense D435i（USB 3.0 接続）
- [Roboflow](https://roboflow.com/) アカウント（アノテーション用）

## セットアップ

```bash
git clone https://github.com/Sawa-E/finger-tracker.git
cd finger-tracker

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## 使い方

### 1. 学習データの収集

RealSense を接続した状態で実行します。`s` キーで画像を保存、`q` / `ESC` で終了。

```bash
python -m finger_tracker.capture
```

保存先: `data/images/`（RGB PNG + 深度 .npy）

### 2. アノテーション

[Roboflow](https://roboflow.com/) で収集した画像をアノテーションし、YOLO 形式でエクスポートします。

- クラス: `red_finger`（赤指サック）、`blue_finger`（青指サック）
- エクスポート先: `data/datasets/finger-cots-v1/`

### 3. モデル学習

```bash
python -m finger_tracker.training
```

mAP50 >= 0.90 を目標に YOLOv8-nano を fine-tuning します。学習済みモデルは `models/best.pt` に自動配置されます。

### 4. リアルタイム計測

RealSense を接続した状態で実行します。`q` / `ESC` で終了。

```bash
python -m finger_tracker.detection
```

計測ログは `logs/` に CSV で記録されます。

## プロジェクト構造

```
finger-tracker/
├── config.yaml              # アプリケーション設定
├── requirements.txt         # Python 依存関係
├── src/finger_tracker/      # メインパッケージ
│   ├── config/              # 設定管理（YAML読み込み）
│   ├── capture/             # RealSense 画像キャプチャ
│   ├── training/            # YOLOv8-nano fine-tuning
│   └── detection/           # 推論 + 3D距離計測 + 表示 + CSV記録
├── data/                    # 学習データ（git管理外）
├── models/                  # 学習済みモデル（git管理外）
├── logs/                    # 計測ログ（git管理外）
└── docs/                    # 設計ドキュメント・ADR
```

## 技術スタック

| 技術 | 用途 |
|------|------|
| [ultralytics](https://github.com/ultralytics/ultralytics) (YOLOv8-nano) | 指サック検出 |
| [pyrealsense2](https://github.com/IntelRealSense/librealsense) | RealSense D435i 制御・深度取得 |
| [OpenCV](https://opencv.org/) | 画像処理・描画・表示 |
| [NumPy](https://numpy.org/) | 3D座標計算・カルマンフィルタ |

## 設定

`config.yaml` でカメラ解像度、モデルパス、HSV 閾値、カルマンフィルタパラメータ等を管理しています。

```bash
# 現在の設定を確認
python -m finger_tracker.config
```

## ライセンス

MIT
