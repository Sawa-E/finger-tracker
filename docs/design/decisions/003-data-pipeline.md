<!--
種別: decisions
対象: データパイプライン
作成日: 2026-02-26
更新日: 2026-02-26
担当: AIエージェント
-->

# データパイプライン

## 概要

RealSense でのデータ収集から Roboflow でのアノテーション、YOLOv8 学習、リアルタイム推論までのデータフローと、各段階でのデータ形式・保存規約を決定する。

## 全体フロー

```
[capture]                [Roboflow (外部)]           [training]              [detection]
RealSense D435i          手動アップロード             YOLOv8-nano             リアルタイム推論
  │                        │                          │                        │
  ├── RGB (PNG) ──────────▶│ アノテーション             │                        │
  │                        │ (Box Prompting +          │                        │
  │                        │  Label Assist)            │                        │
  │                        │                          │                        │
  └── 深度 (NumPy .npy)    │ YOLO形式で               │                        │
       (デバッグ用)         │ ダウンロード ────────────▶│ fine-tuning             │
                           │                          │                        │
                           │                          ├── best.pt ───────────▶│ 推論
                           │                          │   (models/)            │
                           │                          └── メトリクス            │
                                                          (runs/)              │
                                                                               └── 3D距離
```

## 設計判断

### 判断1: キャプチャ画像の保存形式 — RGB (PNG) + 深度 (NumPy .npy) ペア保存

**問題**: RealSense で撮影したデータをどの形式で保存するか

**選択肢**:

1. RGB のみ PNG で保存
2. RGB (PNG) + 深度 (16bit PNG) をペア保存
3. RGB (PNG) + 深度 (NumPy .npy) をペア保存
4. RealSense .bag でストリーム一括記録

**決定**: 選択肢3 — RGB (PNG) + 深度 (NumPy .npy) ペア保存

**理由**:

- YOLO 学習には RGB 画像のみ必要だが、深度データはパイプライン全体のオフライン検証・デバッグに不可欠
- RGB は PNG（可逆圧縮）で保存し、そのまま Roboflow にアップロードできる
- 深度は NumPy .npy で保存することで、値の精度が完全に保たれ、`np.load` で即座に読み込める
- 16bit PNG は画像ビューアで確認できるが、1mm 単位に丸められる。.npy は float 精度を維持
- .bag はストリーム再生には便利だが、フレーム単位の操作にはスクリプトが必要で、Roboflow アップロードには不向き

**トレードオフ**:

- **利点**: RGB は Roboflow 直接アップロード可、深度は完全精度保持、Python での扱いが容易
- **欠点**: .npy は Python 以外での閲覧が不便（このプロジェクトでは問題なし）

**ファイル命名規約**:

```
data/images/
  frame_001_rgb.png
  frame_001_depth.npy
  frame_002_rgb.png
  frame_002_depth.npy
  ...
```

- 連番は3桁ゼロ埋め（300枚想定、必要なら4桁に拡張）
- RGB と深度はサフィックス `_rgb` / `_depth` で対応付け

### 判断2: Roboflow との連携方式 — 手動アップロード/ダウンロード

**問題**: Roboflow とのデータ受け渡しをどう行うか

**選択肢**:

1. 手動でアップロード・ダウンロード（Web UI 経由）
2. Roboflow Python SDK でスクリプト化

**決定**: 選択肢1 — 手動アップロード/ダウンロード

**理由**:

- 約300枚のデータセットでは自動化の工数対効果が低い
- Roboflow の Web UI でアノテーション作業（Box Prompting, Label Assist）を行うため、UI は必ず使用する
- ダウンロードは YOLOv8 形式を選択し、`data/datasets/` に展開する

**トレードオフ**:

- **利点**: 追加の依存関係なし、セットアップ不要、柔軟性が高い
- **欠点**: データセット追加時に手作業が発生（頻度は低い）

**Roboflow からのダウンロードデータ配置**:

```
data/datasets/
  finger-cots-v1/        # Roboflow からエクスポートしたデータセット
    data.yaml            # クラス名・パス定義
    train/
      images/
      labels/
    valid/
      images/
      labels/
    test/
      images/
      labels/
```

### 判断3: 学習済みモデルの管理 — ローカルファイル

**問題**: 学習済みモデル (.pt) をどう管理するか

**選択肢**:

1. `models/` にローカル保存し、ファイル名でバージョニング
2. MLflow / Weights & Biases で実験管理

**決定**: 選択肢1 — ローカルファイル

**理由**:

- 研究用プロトタイプであり、実験管理ツールのセットアップは過剰
- ultralytics の学習出力（`runs/detect/train/weights/best.pt`）を `models/` にコピーして使用
- バージョンはファイル名で管理（`best_v1.pt`, `best_v2.pt`）

**トレードオフ**:

- **利点**: セットアップ不要、シンプル
- **欠点**: メトリクスの比較が手動（ultralytics の TensorBoard 出力で代替可能）

**ディレクトリ構成**:

```
models/
  best.pt               # 現在使用中のモデル（detection が参照）
  best_v1.pt            # バージョン履歴
  best_v2.pt
```

### 判断4: オフラインとリアルタイムの境界

**問題**: パイプラインのどこでオフライン処理とリアルタイム処理を分離するか

**決定**: `models/best.pt` を境界とする

```
オフライン（事前準備）:
  capture → Roboflow → training → models/best.pt

リアルタイム（実行時）:
  RealSense → detection（models/best.pt をロード）→ 3D距離表示
```

- オフラインパイプラインは RealSense 接続環境で段階的に実行する
- リアルタイムパイプラインは `models/best.pt` の存在のみを前提とし、Roboflow や学習環境に依存しない
- detection モジュールは training モジュールに依存しない。モデルファイルのパスのみが接続点

## 関連ドキュメント

- [001-technology-stack.md](./001-technology-stack.md) — 技術スタック選定
- [002-depth-measurement-logic.md](./002-depth-measurement-logic.md) — 深度計測ロジック
- [初期仕様書](../../archive/initial_plan.md)
