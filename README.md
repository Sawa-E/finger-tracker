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
- Intel RealSense D435i（USB 3.0 接続が必要）
- [Roboflow](https://roboflow.com/) アカウント（アノテーション用）

### ハードウェア要件

- RealSense D435i は **USB 3.0 ポートに接続**してください。USB 2.0 では帯域不足により 1280x720 解像度でのストリーミングができません。
- 赤・青のシリコン製指サックを親指（赤）と人差指（青）に装着して使用します。

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

RealSense を接続した状態で実行します。

```bash
python -m finger_tracker.capture
```

カメラのプレビューウィンドウが表示されます。赤・青の指サックを装着した手をカメラの前に置き、さまざまな角度・距離・照明条件で画像を収集します。

**キー操作**:
- `s` — 現在のフレームを保存
- `q` / `ESC` — 終了

**保存されるファイル**:
- `data/images/frame_001_rgb.png` — RGB 画像
- `data/images/frame_001_depth.npy` — 深度データ（NumPy 配列）

ファイル番号は自動でインクリメントされるため、複数回にわたって収集を続けられます。推奨枚数は 200〜400 枚程度です。

### 2. アノテーション

[Roboflow](https://roboflow.com/) で収集した RGB 画像をアノテーションします。

1. Roboflow にプロジェクトを作成（Object Detection、クラス: `red_finger`, `blue_finger`）
2. `data/images/` の RGB 画像（`*_rgb.png`）をアップロード
3. 各画像の指サック部分にバウンディングボックスを描画
4. データ分割: Train 70% / Validation 20% / Test 10%
5. **YOLOv8 形式**でエクスポートし、`data/datasets/finger-cots-v1/` に配置

配置後のディレクトリ構造:

```
data/datasets/finger-cots-v1/
├── data.yaml           # データセット定義（クラス名・パス）
├── train/
│   ├── images/         # 学習用画像
│   └── labels/         # 学習用アノテーション（YOLO形式 .txt）
├── valid/
│   ├── images/
│   └── labels/
└── test/
    ├── images/
    └── labels/
```

### 3. モデル学習

```bash
python -m finger_tracker.training
```

YOLOv8-nano を fine-tuning します。学習の進捗はコンソールに表示されます。

**学習パラメータ**（`config.yaml` で変更可能）:
- エポック数: 100（Early stopping: patience=50）
- バッチサイズ: 16
- 入力サイズ: 640x640
- データ拡張: Roboflow 側で実施済みのため無効

**学習完了後の出力**:
- `models/best.pt` — 最良の検出モデル（自動配置）
- `runs/` — ultralytics の学習ログ・メトリクス
- コンソールに mAP50 の評価結果を表示（目標: >= 0.90）

### 4. リアルタイム計測

RealSense を接続し、`models/best.pt` が存在する状態で実行します。

```bash
python -m finger_tracker.detection
```

**起動すると表示されるもの**:

```
┌─────────────────────────────────────────────┐
│ FPS: 30  Conf: 0.95/0.93                    │  ← フレームレート + 検出信頼度
│                                             │
│   ┌───┐              ┌───┐                  │
│   │RED│──── 45.2mm ──│BLU│                  │  ← BB + 距離線 + 距離値
│   └───┘              └───┘                  │
│                                             │
│ Distance: 45.2 mm                           │  ← 距離の大表示
└─────────────────────────────────────────────┘
```

- 赤色の矩形: `red_finger`（赤指サック）の検出領域
- 青色の矩形: `blue_finger`（青指サック）の検出領域
- 緑色の線: 両指サックのマスク重心間を結ぶ距離線
- 距離値: 3D空間上のユークリッド距離（mm）

**キー操作**:
- `q` / `ESC` — 終了
- `Ctrl+C` — 強制終了（CSV は安全に保存されます）

**起動時のエラー**:
- `ERROR: モデルファイルが見つかりません` — `models/best.pt` を配置してください
- `ERROR: RealSense D435i が見つかりません` — USB 接続を確認してください

### 5. 計測結果の確認

計測を実行すると、`logs/` ディレクトリに2種類のファイルが自動生成されます。

#### CSV ファイル（計測データ）

ファイル名: `logs/measurement_YYYY-MM-DD_HHMMSS.csv`

```csv
timestamp,distance_mm,red_x,red_y,red_z,blue_x,blue_y,blue_z,red_conf,blue_conf
2026-02-26T10:12:40.009,69.2,0.0617,-0.0080,0.4848,-0.0044,-0.0283,0.4838,0.92,0.91
2026-02-26T10:12:40.074,73.4,0.0617,-0.0080,0.4836,-0.0080,-0.0312,0.4845,0.93,0.95
```

| カラム | 内容 | 単位 |
|--------|------|------|
| `timestamp` | タイムスタンプ（JST、ミリ秒精度） | ISO 8601 |
| `distance_mm` | 指間距離 | mm |
| `red_x`, `red_y`, `red_z` | 赤指サックの 3D 座標（カルマンフィルタ済み） | m |
| `blue_x`, `blue_y`, `blue_z` | 青指サックの 3D 座標（カルマンフィルタ済み） | m |
| `red_conf` | 赤指サックの YOLO 検出信頼度 | 0.0-1.0 |
| `blue_conf` | 青指サックの YOLO 検出信頼度 | 0.0-1.0 |

- 両方の指サックが検出できなかったフレームでは `distance_mm` が空になります
- 片方だけ検出できた場合、検出できた側の座標と信頼度のみ記録されます
- 30fps で動作するため、1分間で約 1,800 行のデータが記録されます

CSV は Python の pandas や Excel で読み込み、グラフ化・統計分析に利用できます。

```python
import pandas as pd
df = pd.read_csv("logs/measurement_2026-02-26_101129.csv")
df["distance_mm"].plot()  # 距離の時系列グラフ
```

#### ログファイル（アプリケーションログ）

ファイル名: `logs/app_YYYY-MM-DD_HHMMSS.log`

モデルロード、計測開始/終了、フレーム取得失敗、エラー等の情報が記録されます。問題発生時のデバッグに使用します。

## 設定

すべての設定パラメータは `config.yaml` で管理されています。

```yaml
camera:
  width: 1280         # RGB・深度の解像度（横）
  height: 720         # RGB・深度の解像度（縦）
  fps: 30             # フレームレート

model:
  path: models/best.pt  # 学習済みモデルのパス
  confidence: 0.5       # YOLO 検出の信頼度閾値

hsv:                    # HSV 色フィルタの閾値
  red:
    lower: [0, 120, 70]
    upper: [10, 255, 255]
    lower2: [170, 120, 70]    # 赤は色相が 0 と 180 で分裂するため2範囲
    upper2: [180, 255, 255]
  blue:
    lower: [100, 120, 70]
    upper: [130, 255, 255]

filter:
  kalman_q: 0.01       # カルマンフィルタのプロセスノイズ（大きい→追従性↑ノイズ↑）
  kalman_r: 0.1        # カルマンフィルタの観測ノイズ（大きい→安定性↑追従遅れ↑）
  depth_timeout: 0.5   # 深度値の直前値保持タイムアウト（秒）

display:
  fps_target: 30       # 表示 FPS 目標

capture:
  output_dir: data/images  # キャプチャ画像の保存先
  prefix: frame            # ファイル名プレフィックス

training:
  dataset: data/datasets/finger-cots-v1/data.yaml
  epochs: 100
  patience: 50
  batch: 16
  imgsz: 640
  base_model: yolov8n.pt
```

現在の設定値を確認:

```bash
python -m finger_tracker.config
```

## プロジェクト構造

```
finger-tracker/
├── CLAUDE.md                # 開発ルール・プロジェクト概要
├── README.md                # 本ドキュメント
├── REPORT.md                # 開発報告書（理論詳説含む）
├── config.yaml              # アプリケーション設定
├── pyproject.toml           # Python パッケージ定義
├── requirements.txt         # 依存関係
├── src/finger_tracker/      # メインパッケージ
│   ├── config/              # 設定管理（YAML読み込み + デフォルト値マージ）
│   ├── capture/             # RealSense 画像キャプチャ
│   ├── training/            # YOLOv8-nano fine-tuning + 評価 + モデル配置
│   └── detection/           # 推論 + HSVフィルタ + 3D距離計測 + カルマンフィルタ + 表示 + CSV記録
├── data/                    # 学習データ（git管理外）
│   ├── images/              # キャプチャ画像（RGB PNG + 深度 .npy）
│   └── datasets/            # Roboflow エクスポート（YOLO形式）
├── models/                  # 学習済みモデル .pt（git管理外）
├── logs/                    # 計測 CSV + アプリケーションログ（git管理外）
├── runs/                    # ultralytics 学習出力（git管理外）
└── docs/                    # 設計ドキュメント・ADR
```

`data/`, `models/`, `logs/`, `runs/` は git 管理外です。別マシンにセットアップする場合は `models/best.pt` を手動でコピーしてください（`scp` 等）。

## 技術スタック

| 技術 | 用途 |
|------|------|
| [ultralytics](https://github.com/ultralytics/ultralytics) (YOLOv8-nano) | 指サック検出（3.2M パラメータ、推論 10-20ms） |
| [pyrealsense2](https://github.com/IntelRealSense/librealsense) | RealSense D435i 制御・深度取得・3D座標変換 |
| [OpenCV](https://opencv.org/) | 画像処理・HSVフィルタ・描画・表示 |
| [NumPy](https://numpy.org/) | 3D座標計算・カルマンフィルタ・行列演算 |
| [Roboflow](https://roboflow.com/) | 学習データのアノテーション（外部ツール） |

## 関連ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [REPORT.md](REPORT.md) | 開発報告書（detection モジュールの理論詳説含む） |
| [docs/design/decisions/](docs/design/decisions/) | ADR（アーキテクチャ決定記録）001〜009 |
| [docs/status/implementation.md](docs/status/implementation.md) | 実装ステータス |

## ライセンス

MIT
