<!--
種別: plans
対象: Phase 1 — config + capture モジュール実装
作成日: 2026-02-26
更新日: 2026-02-26
ステータス: resolved
優先度: 高
担当: AIエージェント
-->

# Phase 1: config + capture モジュール実装

## 概要

プロジェクト基盤（requirements.txt、config.yaml、パッケージ構造）を整備し、config モジュール（設定管理）と capture モジュール（RealSense 画像キャプチャ）を実装する。これにより YOLO 学習用データの収集が可能になる。

## 現状分析

- ADR 001〜009 が完成済み。設計判断はすべて記録されている
- ディレクトリ構造（`src/finger_tracker/{config,capture,training,detection}/`）は作成済みだが、Python ファイルは存在しない
- `requirements.txt`、`config.yaml`、`__init__.py` がいずれも未作成
- ロードマップ Phase 1 の開始段階

## ゴール

- [x] `python -m finger_tracker.config` で設定内容を確認できる
- [x] `python -m finger_tracker.capture` で RealSense から RGB+深度画像を取得・保存できる
- [x] `data/images/` に `frame_001_rgb.png` + `frame_001_depth.npy` のペアが保存される
- [x] Roboflow アップロード可能な RGB 画像が得られる

## スコープ

### 含む

- プロジェクト基盤ファイル（pyproject.toml、requirements.txt、.gitignore、__init__.py 群、config.yaml）
- config モジュール（YAML 読み込み、デフォルト値、設定確認コマンド）
- capture モジュール（RealSense 接続、フレーム取得、RGB PNG + 深度 .npy 保存）
- 起動時エラーハンドリング（RealSense 未接続、config.yaml 不在）

### 含まない

- training モジュール（Phase 2）
- detection モジュール（Phase 3）
- テストコード（RealSense 依存のためモック設計が必要。別計画で対応）
- Roboflow アノテーション作業（手作業）

## タスクリスト

### #001-01: プロジェクト基盤ファイル作成

**対象ファイル**:
- `pyproject.toml` — パッケージ定義（src レイアウト対応）
- `requirements.txt` — 依存パッケージ定義
- `config.yaml` — アプリケーション設定（ADR 006 の設定項目一覧をそのまま使用）
- `.gitignore` — git 管理外ファイル定義（ADR 009）
- `src/finger_tracker/__init__.py` — パッケージ初期化

**実装内容**:
- pyproject.toml: src レイアウトで `python -m finger_tracker.xxx` を動かすためのパッケージ定義。`pip install -e .` で開発インストール（ADR 009）
- requirements.txt: `ultralytics`, `pyrealsense2`, `opencv-python`, `numpy`, `pyyaml`
- config.yaml: ADR 006 で定義した全設定項目をコメント付きで記載
- .gitignore: `data/`, `models/`, `logs/`, `runs/`, `.venv/`, `__pycache__/`, `*.egg-info/`
- `__init__.py`: 空ファイル（パッケージ認識用）

**依存**: なし（最初に実行）

- [x] 完了

### #001-02: config モジュール実装

**対象ファイル**:
- `src/finger_tracker/config/__init__.py` — `load_config()` 関数
- `src/finger_tracker/config/__main__.py` — 設定確認用エントリポイント

**実装内容**:
- `load_config(path=None)`: プロジェクトルートの `config.yaml` を読み込み dict を返す
  - path 未指定時はスクリプトの実行ディレクトリから `config.yaml` を探索
  - ファイル不在時: `FileNotFoundError` + エラーメッセージ（ADR 008）
  - YAML 構文エラー時: `yaml.YAMLError` + エラーメッセージ（ADR 008）
- `__main__.py`: `load_config()` を呼び、設定内容を整形表示

**依存**: #001-01

- [x] 完了

### #001-03: capture モジュール実装

**対象ファイル**:
- `src/finger_tracker/capture/__init__.py` — キャプチャ機能
- `src/finger_tracker/capture/__main__.py` — エントリポイント

**実装内容**:
- RealSense パイプライン初期化（config の camera 設定を使用）
  - RealSense 未接続時: エラーメッセージで終了（ADR 008）
- RGB + 深度フレームのアライン
- キーボード操作でキャプチャ:
  - `s` キー: 現在のフレームを保存（RGB PNG + 深度 .npy）
  - `q` キー or ESC: 終了
- ファイル命名: `{prefix}_{連番3桁}_rgb.png` / `{prefix}_{連番3桁}_depth.npy`（ADR 003）
- 保存先: `config.yaml` の `capture.output_dir`（デフォルト `data/images/`）
- 連番は既存ファイルの最大番号 + 1 から開始（途中追加対応）
- OpenCV ウィンドウでプレビュー表示（RGB フレーム + 保存枚数カウント）

**依存**: #001-02

- [x] 完了

### #001-04: 動作確認

**内容**:
- `python -m finger_tracker.config` で設定表示を確認
- `python -m finger_tracker.capture` でプレビュー表示・画像保存を確認（RealSense 接続環境）
- 保存されたファイルの確認（PNG の画質、.npy のデータ型と形状）
- 実装ステータスの更新

**依存**: #001-03

- [x] 完了

## リスク

| リスク | 影響 | 対策 |
|--------|------|------|
| RealSense 未接続環境での開発 | capture モジュールの実装・テストが困難 | config + 基盤は RealSense なしで実装可能。capture は ADR 準拠で書き、接続環境で動作確認 |
| pyrealsense2 のインストール問題 | WSL2 環境での USB デバイスアクセス | usbipd-win でデバイス転送。pip install に失敗する場合は公式ビルド手順を確認 |
| 深度フレームとRGBフレームの位置合わせ | 保存画像のペアが空間的にずれる | `rs2.align(rs2.stream.color)` で深度をRGBに合わせる |

## 関連ドキュメント

- [ADR 003: データパイプライン](../design/decisions/003-data-pipeline.md) — 保存形式・命名規約
- [ADR 006: 設定管理方式](../design/decisions/006-config-management.md) — config.yaml 仕様
- [ADR 008: エラーハンドリング](../design/decisions/008-error-handling.md) — 起動時エラー対処
- [ADR 009: ディレクトリ構成](../design/decisions/009-directory-structure.md) — パッケージ構造
- [ロードマップ](../status/roadmap.md) — Phase 1 の位置づけ
