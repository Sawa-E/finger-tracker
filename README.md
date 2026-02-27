# finger-tracker

RealSense D435i と YOLOv8-nano による指間距離リアルタイム計測システム

## 概要

赤・青のシリコン製指サック（カラーマーカー）を YOLOv8-nano で検出し、RealSense D435i の深度データから 3D 空間上の指間距離をリアルタイムに計測します。

計測データは UDP で [teleop-hand](https://github.com/Sawa-E/teleop-hand)（C++ リアルタイム制御システム）に送信され、1-DOF ロボットハンドの遠隔操作指令値として使用されます。

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
                    ┌───────────┼───────────┐
                    ↓           ↓           ↓
              OpenCV表示    CSV記録    UDP送信 → teleop-hand
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

学習完了後、`models/best.pt` にモデルが自動配置されます。`runs/` に学習ログ・メトリクスが出力されます。目標精度は mAP50 >= 0.90 です。

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

### 5. teleop-hand 連携

detection モジュールは毎フレーム、計測データを UDP で teleop-hand に送信します。

```
finger-tracker (Python)                    teleop-hand (C++)
─────────────────────                      ─────────────────
detection ループ (30Hz)                    recv_command (10kHz ポーリング)
    │                                          │
    ├─ distance_mm                             │
    ├─ red_x, red_y, red_z      sendto        │
    ├─ blue_x, blue_y, blue_z  ───────→  recvfrom (UDP:50000)
    │   28 bytes, little-endian                │
    │                                          ├─ 逆運動学 → θ_cmd
    │                                          ├─ PD + DOB 制御
    │                                          └─ DA ボード出力
```

**パケット形式**: 28 バイト、リトルエンディアン float32 x 7

| オフセット | 型 | フィールド | 説明 |
|-----------|-----|-----------|------|
| 0 | float32 | `distance_mm` | 指間距離 [mm]。検出失敗時は `-1.0` |
| 4 | float32 | `red_x` | 親指 X 座標 [m] |
| 8 | float32 | `red_y` | 親指 Y 座標 [m] |
| 12 | float32 | `red_z` | 親指 Z 座標 [m] |
| 16 | float32 | `blue_x` | 人差指 X 座標 [m] |
| 20 | float32 | `blue_y` | 人差指 Y 座標 [m] |
| 24 | float32 | `blue_z` | 人差指 Z 座標 [m] |

**起動順序**: finger-tracker と teleop-hand はどちらを先に起動しても動作します（UDP の性質上、受信者不在でも送信側はエラーになりません）。

**送信を無効にする場合**: `config.yaml` で `udp.enabled: false` に設定してください。teleop-hand なしで finger-tracker を単体で使用する場合に有用です。

### 6. 計測結果の確認

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

## 設定リファレンス

すべての設定は `config.yaml` で管理されています（コード内ハードコードなし）。現在の設定値は `python -m finger_tracker.config` で確認できます。

### camera — RealSense カメラ設定

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `width` | `1280` | RGB・深度ストリームの横解像度 [px] |
| `height` | `720` | RGB・深度ストリームの縦解像度 [px] |
| `fps` | `30` | フレームレート [Hz]。カルマンフィルタの dt にも使用 |

> D435i は 1280x720@30fps / 640x480@60fps 等に対応。解像度を下げると処理が軽くなりますが、小さい指サックの検出精度が下がります。

### model — YOLOv8 推論設定

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `path` | `models/best.pt` | 学習済みモデルファイルのパス |
| `confidence` | `0.5` | 検出信頼度の閾値。これ未満の検出は無視される |

> `confidence` を下げると検出漏れが減りますが、誤検出が増えます。照明が安定した環境では `0.5`〜`0.7` が推奨です。

### hsv — HSV 色フィルタ閾値

YOLO の BB 内で色フィルタを適用し、指サックのマスク重心を求めます。HSV 値は `[H, S, V]` の配列で指定します。

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `red.lower` | `[0, 120, 70]` | 赤の HSV 下限（色相 0〜10 の範囲） |
| `red.upper` | `[10, 255, 255]` | 赤の HSV 上限 |
| `red.lower2` | `[170, 120, 70]` | 赤の HSV 下限 2（色相 170〜180 の範囲） |
| `red.upper2` | `[180, 255, 255]` | 赤の HSV 上限 2 |
| `blue.lower` | `[100, 120, 70]` | 青の HSV 下限 |
| `blue.upper` | `[130, 255, 255]` | 青の HSV 上限 |

> **赤が2範囲ある理由**: OpenCV の HSV 色相は 0〜180 で、赤は 0 付近と 180 付近に分裂します。両方の範囲を OR で結合してマスクを生成します。
>
> **チューニング方法**: 照明環境が変わって検出が不安定な場合、S（彩度）と V（明度）の下限を調整してください。暗い環境では `V` を下げ（例: `50`）、蛍光灯下では `S` を上げる（例: `150`）と改善することがあります。

### filter — カルマンフィルタ・深度フィルタ設定

各指サックの 3D 座標を独立にカルマンフィルタ（等速度モデル、6D 状態 `[x,y,z,vx,vy,vz]`）で追跡します。

| パラメータ | デフォルト | 説明 | 大きくすると | 小さくすると |
|-----------|-----------|------|-------------|-------------|
| `kalman_q` | `0.01` | プロセスノイズ。システムの不確実性 | 追従性↑ ノイズ↑ | 安定性↑ 追従遅れ↑ |
| `kalman_r` | `0.1` | 観測ノイズ。センサの不確実性 | 安定性↑ 追従遅れ↑ | 追従性↑ ノイズ↑ |
| `depth_timeout` | `0.5` | 深度欠損時に直前値を保持する時間 [秒] | 欠損耐性↑ 古い値のリスク↑ | 即座に欠損扱い |

> **チューニングの目安**: 指を素早く動かす用途では `kalman_q` を大きく（例: `0.05`）、静止計測では小さく（例: `0.005`）します。`kalman_r` はセンサの深度ノイズに応じて調整し、通常は `0.05`〜`0.2` の範囲です。

### udp — teleop-hand 通信設定

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `host` | `"127.0.0.1"` | teleop-hand の IP アドレス |
| `port` | `50000` | teleop-hand の受信ポート（`config/comm.json` と一致させる） |
| `enabled` | `true` | `false` で UDP 送信を無効化 |

> teleop-hand なしで finger-tracker を単体利用する場合は `enabled: false` に設定してください。`true` のままでも受信者不在ではエラーにはなりません。

### display — 表示設定

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `fps_target` | `30` | 表示 FPS の目標値 |

### capture — データ収集設定

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `output_dir` | `data/images` | キャプチャ画像の保存先ディレクトリ |
| `prefix` | `frame` | ファイル名のプレフィックス（`{prefix}_001_rgb.png`） |

### training — モデル学習設定

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `dataset` | `data/datasets/finger-cots-v1/data.yaml` | データセット定義ファイルのパス |
| `epochs` | `100` | 最大エポック数 |
| `patience` | `50` | Early stopping の許容エポック数（改善がなければ停止） |
| `batch` | `16` | バッチサイズ |
| `imgsz` | `640` | 入力画像サイズ [px] |
| `base_model` | `yolov8n.pt` | fine-tuning のベースモデル |

> データ拡張は Roboflow のエクスポート時に適用済みのため、ultralytics 側の augmentation は無効にしています。

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
│   └── detection/           # 推論 + HSVフィルタ + 3D距離計測 + カルマンフィルタ + 表示 + CSV記録 + UDP送信
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
| [docs/design/decisions/](docs/design/decisions/) | ADR（アーキテクチャ決定記録）001〜010 |
| [docs/status/implementation.md](docs/status/implementation.md) | 実装ステータス |
| [docs/status/roadmap.md](docs/status/roadmap.md) | ロードマップ |

## ライセンス

MIT
