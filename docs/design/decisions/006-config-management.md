<!--
種別: decisions
対象: 設定管理方式
作成日: 2026-02-26
更新日: 2026-02-26
担当: AIエージェント
-->

# 設定管理方式

## 概要

finger-tracker の設定値（カメラパラメータ、モデルパス、フィルタ係数等）の管理方法を決定する。

## 設計判断

### 判断1: 設定ファイル形式 — YAML

**問題**: 設定値をどの形式で管理するか

**選択肢**:

1. YAML ファイル
2. Python dataclass のみ（コード内定義）
3. YAML + dataclass（外部ファイル + 型付きアクセス）

**決定**: 選択肢1 — YAML

**理由**:

- 人間が読み書きしやすく、コメントも記述できる
- PyYAML は ultralytics の依存に含まれるため追加インストール不要
- コード変更なしでパラメータ調整が可能（カルマンフィルタの Q/R チューニング等）
- dataclass へのマッピングは将来必要になったら追加する。現段階では dict アクセスで十分

**トレードオフ**:

- **利点**: コード変更なしで設定変更可能、コメント記述可能、追加依存なし
- **欠点**: 型チェックがない（typo に気づきにくい）、dict アクセスで IDE 補完が効かない

### 判断2: CLI 引数 — 不要

**問題**: コマンドライン引数で設定を上書きできるようにするか

**選択肢**:

1. CLI 引数なし（YAML 編集のみ）
2. argparse で主要設定を上書き可能にする

**決定**: 選択肢1 — CLI 引数なし

**理由**:

- 研究用途で実行者は本人のみ。YAML ファイルの直接編集で十分
- argparse を導入すると設定の二重管理（YAML + CLI）になり複雑になる

**トレードオフ**:

- **利点**: 実装がシンプル、設定の一元管理
- **欠点**: 実行ごとに異なるパラメータを試すには YAML を編集する必要がある

### 判断3: 配置場所 — プロジェクトルート

**問題**: 設定ファイルをどこに置くか

**選択肢**:

1. プロジェクトルート (`config.yaml`)
2. config ディレクトリ (`config/default.yaml`)

**決定**: 選択肢1 — プロジェクトルート

**理由**:

- 設定ファイルは 1 つのみなのでディレクトリを切る必要がない
- プロジェクトルートに置くことで見つけやすい

**トレードオフ**:

- **利点**: シンプル、発見しやすい
- **欠点**: 設定ファイルが増えた場合にルートが散らかる（現時点では問題なし）

## 設定項目一覧

```yaml
# config.yaml

camera:
  width: 1280          # RGB・Depth 解像度（幅）
  height: 720          # RGB・Depth 解像度（高さ）
  fps: 30              # RealSense ストリーム FPS

model:
  path: models/best.pt # YOLOv8 モデルファイルパス
  confidence: 0.5      # 検出信頼度の閾値

hsv:
  red:                 # 赤指サック（親指）の HSV 範囲
    lower: [0, 120, 70]
    upper: [10, 255, 255]
    lower2: [170, 120, 70]   # 赤は HSV で 0 付近と 180 付近に分かれる
    upper2: [180, 255, 255]
  blue:                # 青指サック（人差指）の HSV 範囲
    lower: [100, 120, 70]
    upper: [130, 255, 255]

filter:
  kalman_q: 0.01       # カルマンフィルタ プロセスノイズ
  kalman_r: 0.1        # カルマンフィルタ 観測ノイズ
  depth_timeout: 0.5   # 深度欠損時の直前値保持タイムアウト（秒）

display:
  fps_target: 30       # 表示 FPS 目標

udp:
  host: "127.0.0.1"      # teleop-hand の IP アドレス
  port: 50000             # teleop-hand の受信ポート
  enabled: true           # false で送信を無効化

capture:
  output_dir: data/images  # キャプチャ画像の保存先
  prefix: frame            # ファイル名のプレフィックス
```

## config モジュールの責務

- `config.yaml` を読み込み、dict として提供する
- デフォルト値の定義（YAML にキーがない場合のフォールバック）
- 各モジュール（capture, detection 等）は config モジュール経由で設定にアクセスする

```python
# 使用例
from finger_tracker.config import load_config

config = load_config()  # config.yaml を読み込み
width = config["camera"]["width"]
model_path = config["model"]["path"]
```

## 関連ドキュメント

- [002-depth-measurement-logic.md](./002-depth-measurement-logic.md) — カルマンフィルタ Q/R、HSV フィルタ
- [005-realtime-display.md](./005-realtime-display.md) — FPS 目標、表示設定
- [010-udp-publisher.md](./010-udp-publisher.md) — UDP 送信設定
- [初期仕様書](../../archive/initial_plan.md)
