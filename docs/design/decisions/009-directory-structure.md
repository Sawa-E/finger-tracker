<!--
種別: decisions
対象: ディレクトリ構成
作成日: 2026-02-26
更新日: 2026-02-26
担当: AIエージェント
-->

# ディレクトリ構成

## 概要

finger-tracker のディレクトリ構成、Python パッケージレイアウト、モジュール分割の方針、および git 管理対象を決定する。

## 全体構成

```
finger-tracker/
├── CLAUDE.md                    # プロジェクト概要・開発ルール
├── config.yaml                  # アプリケーション設定（ADR 006）
├── requirements.txt             # Python 依存関係
├── .gitignore
├── src/
│   └── finger_tracker/          # メインパッケージ
│       ├── __init__.py
│       ├── config/              # 設定管理
│       │   ├── __init__.py
│       │   └── __main__.py
│       ├── capture/             # データ収集
│       │   ├── __init__.py
│       │   └── __main__.py
│       ├── training/            # モデル学習
│       │   ├── __init__.py
│       │   └── __main__.py
│       └── detection/           # 推論 + 3D距離計測 + 表示
│           ├── __init__.py
│           └── __main__.py
├── scripts/                     # ユーティリティスクリプト
├── tests/                       # テスト
├── data/                        # 学習データ（git管理外）
│   ├── images/                  # キャプチャ画像（RGB PNG + 深度 .npy）
│   └── datasets/                # Roboflow エクスポート（YOLO形式）
├── models/                      # 学習済みモデル（git管理外）
├── logs/                        # ログ・計測記録（git管理外）
├── runs/                        # ultralytics 学習出力（git管理外）
├── docs/                        # ドキュメント体系
└── .claude/                     # Claude Code 設定
```

## 設計判断

### 判断1: パッケージレイアウト — src レイアウト

**問題**: Python パッケージをどのレイアウトで構成するか

**選択肢**:

1. src レイアウト（`src/finger_tracker/`）
2. フラットレイアウト（`finger_tracker/` をルート直下）

**決定**: 選択肢1 — src レイアウト

**理由**:

- テストが開発中のパッケージではなくインストール済みのパッケージに対して実行されることを保証できる
- パッケージコードとプロジェクトルートのファイル（config.yaml 等）が明確に分離される
- Python パッケージングの推奨プラクティス

**トレードオフ**:

- **利点**: テストの信頼性、明確な分離、パッケージング標準に準拠
- **欠点**: パスがやや深くなる、`pip install -e .` が必要（開発時）

### 判断2: モジュール分割 — 4モジュール + scripts

**問題**: パッケージ内のモジュール分割をどうするか

**選択肢**:

1. capture / training / detection / config の 4 モジュール
2. detection を inference / display / recorder に分割（7 モジュール）

**決定**: 選択肢1 — 4 モジュール

**理由**:

- 構想段階の研究プロトタイプであり、過度な分割は複雑さを増す
- detection の責務は多い（推論 + HSVフィルタ + 深度→3D + カルマンフィルタ + 表示 + CSV記録）が、これらは密結合しておりモジュール間通信のオーバーヘッドを避けたい
- 肥大化した場合は後から分割する

**トレードオフ**:

- **利点**: シンプル、モジュール間通信が少ない
- **欠点**: detection モジュールが大きくなる可能性

**各モジュールの責務**:

| モジュール | 責務 | 関連 ADR |
|-----------|------|---------|
| **config** | YAML 読み込み、設定値の提供 | [006](./006-config-management.md) |
| **capture** | RealSense フレーム取得、RGB PNG + 深度 .npy 保存 | [003](./003-data-pipeline.md) |
| **training** | YOLOv8-nano fine-tuning、モデル評価 | [004](./004-yolo-training-strategy.md) |
| **detection** | YOLO 推論 → HSV フィルタ → 深度→3D → カルマンフィルタ → 表示 → CSV 記録 | [002](./002-depth-measurement-logic.md), [005](./005-realtime-display.md), [007](./007-logging-recording.md) |

**モジュール間の依存関係**:

```
config ←── capture
config ←── training
config ←── detection
capture ──→ data/images/    (出力)
training ──→ models/best.pt (出力)
detection ──→ models/best.pt (入力)
detection ──→ logs/          (出力)
```

### 判断3: エントリポイント — `__main__.py`

**問題**: 各モジュールをどう実行するか

**決定**: 各モジュールに `__main__.py` を配置し、`python -m` で直接実行可能にする

```bash
python -m finger_tracker.capture     # データ収集
python -m finger_tracker.training    # モデル学習
python -m finger_tracker.detection   # リアルタイム計測
python -m finger_tracker.config      # 設定確認（デバッグ用）
```

**理由**:

- Python の標準的な実行方法
- 各モジュールが独立して実行可能であることを明示
- scripts/ の補助スクリプトとの区別が明確

### 判断4: git 管理対象 — コードとドキュメントのみ

**問題**: どのファイル・ディレクトリを git 管理下に置くか

**決定**: 大容量バイナリとランタイム生成物を除外

**git 管理外（.gitignore）**:

| ディレクトリ | 理由 | 想定サイズ |
|-------------|------|-----------|
| `data/` | 学習画像・深度データ・データセット | 数GB |
| `models/` | 学習済みモデル (.pt) | 数十MB |
| `logs/` | ログ・計測CSV | 数十MB |
| `runs/` | ultralytics 学習出力 | 数百MB |
| `.venv/` | Python 仮想環境 | 数百MB |
| `__pycache__/` | Python キャッシュ | — |

**git 管理対象**:

| ディレクトリ | 内容 |
|-------------|------|
| `src/` | Python ソースコード |
| `scripts/` | ユーティリティスクリプト |
| `tests/` | テストコード |
| `docs/` | ドキュメント体系 |
| `.claude/` | Claude Code 設定・スキル |
| `config.yaml` | アプリケーション設定 |
| `requirements.txt` | 依存関係 |
| `CLAUDE.md` | プロジェクト概要 |

## 関連ドキュメント

- [003-data-pipeline.md](./003-data-pipeline.md) — data/ ディレクトリの構成
- [006-config-management.md](./006-config-management.md) — config.yaml の配置
- [007-logging-recording.md](./007-logging-recording.md) — logs/ ディレクトリの構成
- [初期仕様書](../../archive/initial_plan.md)
