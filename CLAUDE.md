# CLAUDE.md

finger-tracker — 指サックカラーマーカーによる指間距離リアルタイム計測システム

## プロジェクト概要

RealSense D435i の RGB+深度画像から、赤・青の指サック（シリコン製カラーマーカー）を YOLOv8-nano で検出し、3D座標間のユークリッド距離として指間距離をリアルタイムに計測するシステム。将来的にはロボットハンドの遠隔操作指令値として使用し、バイラテラルテレオペレーションシステムへの発展を目指す。

## プロジェクト構造

```
finger-tracker/
├── CLAUDE.md                    # プロジェクト概要・開発ルール
├── config.yaml                  # アプリケーション設定（ADR 006）
├── requirements.txt             # Python 依存関係
├── src/
│   └── finger_tracker/          # メインパッケージ
│       ├── __init__.py
│       ├── config/              # 設定管理（YAML読み込み）
│       │   ├── __init__.py
│       │   └── __main__.py
│       ├── capture/             # RealSenseからのRGB+深度キャプチャ
│       │   ├── __init__.py
│       │   └── __main__.py
│       ├── training/            # YOLOv8-nano fine-tuning
│       │   ├── __init__.py
│       │   └── __main__.py
│       └── detection/           # 推論+HSVフィルタ+3D距離計測+表示+CSV記録
│           ├── __init__.py
│           └── __main__.py
├── scripts/                     # ユーティリティスクリプト
├── tests/                       # テスト
├── data/                        # 学習データ（git管理外）
│   ├── images/                  # キャプチャ画像（RGB PNG + 深度 .npy）
│   └── datasets/                # Roboflow エクスポート（YOLO形式）
├── models/                      # 学習済みモデル .pt（git管理外）
├── logs/                        # ログ・計測CSV（git管理外）
├── runs/                        # ultralytics 学習出力（git管理外）
└── docs/                        # ドキュメント体系
```

## ビルド・テスト

```bash
# 環境構築
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# データ収集（RealSense接続が必要）
python -m finger_tracker.capture

# モデル学習
python -m finger_tracker.training

# リアルタイム計測（RealSense接続が必要）
python -m finger_tracker.detection
```

## 技術スタック

| 層 | 技術 | 用途 |
|---|---|---|
| 言語 | Python 3.12.3 | メイン言語 |
| 物体検出 | ultralytics (YOLOv8-nano) | 指サック検出 |
| 深度カメラ | pyrealsense2 | RealSense D435i 制御・深度取得 |
| 画像処理 | OpenCV | 画像表示・前処理・描画 |
| 数値計算 | NumPy | 3D座標計算・フィルタ処理 |
| アノテーション | Roboflow | 学習データラベリング（外部ツール） |

技術選定の詳細: [docs/design/decisions/001-technology-stack.md](docs/design/decisions/001-technology-stack.md)

## アーキテクチャ

### モジュール構成

| モジュール | 責務 |
|-----------|------|
| **capture** | RealSenseからRGB+深度フレームを取得し、学習用画像として保存する |
| **training** | RoboflowからエクスポートしたデータセットでYOLOv8-nanoをfine-tuningする |
| **detection** | YOLOv8推論 → BB内HSVフィルタ → マスク重心の深度取得 → 3D座標変換 → カルマンフィルタ → 距離計算 → 表示 → CSV記録 |
| **config** | カメラパラメータ、モデルパス、フィルタ設定等の一元管理 |

### 処理フロー

```
RealSense D435i
    ├── RGB フレーム → YOLOv8-nano → red_finger / blue_finger BB検出
    │                                    ↓
    │                          BB内HSVフィルタ → マスク重心ピクセル
    │                                    ↓
    └── 深度フレーム ──────→ マスク重心の深度値取得
                                ↓
              rs2_deproject_pixel_to_point で 3D座標変換
                                ↓
              各指独立3Dカルマンフィルタ（等速度モデル）
                                ↓
              フィルタ済み座標間のユークリッド距離 = 指間距離
                                ↓
              OpenCV表示 + CSV記録
```

### 検出クラス

| クラス名 | 対象 |
|---------|------|
| `red_finger` | 赤指サック（親指） |
| `blue_finger` | 青指サック（人差指） |

## 用語

| 用語 | 定義 |
|------|------|
| 指サック | シリコン製のカラーマーカー。赤（親指）と青（人差指）の2色 |
| BB | バウンディングボックス。YOLOが検出した矩形領域 |
| 深度値 | RealSenseの深度カメラが取得するピクセルごとの距離情報（mm） |
| `rs2_deproject_pixel_to_point` | pyrealsense2の関数。2Dピクセル座標+深度値→3D空間座標に変換 |
| fine-tuning | 事前学習済みYOLOv8-nanoモデルをカスタムデータセットで追加学習すること |

## 実装ルール

- RealSense関連のコードは `capture/` と `detection/` に集約する。`training/` はRealSense非依存とする
- BB内HSVフィルタでマスク重心を算出し、その深度値から3D座標を得る（ADR 002）
- 各指サックを独立した3Dカルマンフィルタ（等速度モデル）で追跡し、フィルタ済み座標から距離を算出する（ADR 002）
- 設定値（カメラ解像度、FPS、モデルパス、カルマンQ/R、HSV閾値等）はハードコードせず `config.yaml` で管理する（ADR 006）
- `data/`, `models/`, `logs/`, `runs/` はgit管理外（ADR 009）

### コミットメッセージ

形式: `type(scope): 簡潔な説明`

```
feat(capture): RealSenseからの画像キャプチャ機能を追加
feat(detection): リアルタイム距離計測の実装
fix(detection): 深度値が0の場合のフォールバック処理
```

## タスク管理ルール

### 基本設定

タスクリストID `finger-tracker-tasks` で統一（`.claude/settings.json`で設定済み）。

### サブエージェント起動

必ず `model: "sonnet"` を指定する。

```
Task {
  subagent_type: "general-purpose",
  model: "sonnet",
  prompt: "..."
}
```

## ドキュメントインデックス

| ドキュメント | 内容 |
|-------------|------|
| [docs/archive/initial_plan.md](docs/archive/initial_plan.md) | 初期仕様書 |
| [docs/design/decisions/](docs/design/decisions/) | ADR一覧（001〜009） |
| [docs/design/GUIDE.md](docs/design/GUIDE.md) | 設計書作成ガイド |
| [docs/plans/GUIDE.md](docs/plans/GUIDE.md) | 実装計画ガイド |
| [docs/review/GUIDE.md](docs/review/GUIDE.md) | レビューガイド |
| [docs/usecases/GUIDE.md](docs/usecases/GUIDE.md) | ユースケースガイド |
| [docs/status/implementation.md](docs/status/implementation.md) | 実装ステータス |
| [docs/status/roadmap.md](docs/status/roadmap.md) | ロードマップ |
