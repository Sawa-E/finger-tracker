<!--
種別: plans
対象: Phase 2 — training モジュール実装
作成日: 2026-02-26
更新日: 2026-02-26
ステータス: resolved
優先度: 中
担当: AIエージェント
-->

# Phase 2: training モジュール実装

## 概要

Roboflow からエクスポートした YOLO 形式データセットで YOLOv8-nano を fine-tuning し、学習済みモデル（best.pt）を評価・配置する training モジュールを実装する。

## 現状分析

- Phase 1（config + capture）の計画が作成済み。実装はこれから
- Roboflow でのアノテーション（約 300 枚、`red_finger` / `blue_finger`）は Phase 1 完了後に手作業で実施
- ADR 004 で学習戦略（nano, mAP50 >= 0.90, エポック 100, early stopping）が決定済み
- ADR 003 でデータセット配置（`data/datasets/finger-cots-v1/`）が決定済み
- training モジュールは RealSense 非依存（CLAUDE.md 実装ルール）

## 前提条件

- Phase 1 の config モジュールが実装済みであること
- `data/datasets/` に Roboflow エクスポート済みデータセット（YOLO 形式）が存在すること

## ゴール

- [x] `python -m finger_tracker.training` で YOLOv8-nano の fine-tuning が実行できる
- [x] 学習完了後に mAP50 等の評価指標がコンソールに表示される
- [x] `models/best.pt` に学習済みモデルが配置される
- [x] mAP50 >= 0.90 を目標とし、未達時の対応方針が明確

## スコープ

### 含む

- training モジュール（fine-tuning 実行スクリプト）
- モデル評価（mAP50 表示、結果サマリー）
- best.pt の `models/` ディレクトリへのコピー
- config.yaml への training セクション追加
- 起動時エラーハンドリング（データセット不在）

### 含まない

- Roboflow でのアノテーション作業（手作業）
- detection モジュール（Phase 3）
- データ拡張の設定（Roboflow 側で実施、ADR 004）
- TensorBoard によるメトリクス可視化（ultralytics が自動出力する `runs/` で代替）

## タスクリスト

### #002-01: config.yaml に training セクション追加

**対象ファイル**:
- `config.yaml` — training 関連の設定項目を追加

**実装内容**:
- ADR 004 の学習パラメータを config.yaml に追加:
  ```yaml
  training:
    dataset: data/datasets/finger-cots-v1/data.yaml
    epochs: 100
    patience: 50        # early stopping
    batch: 16
    imgsz: 640
    base_model: yolov8n.pt  # fine-tuning のベースモデル
  ```

**依存**: Phase 1（#001-01）完了後

- [x] 完了

### #002-02: training モジュール実装

**対象ファイル**:
- `src/finger_tracker/training/__init__.py` — 学習実行関数
- `src/finger_tracker/training/__main__.py` — エントリポイント

**実装内容**:
- `train(config)` 関数:
  - config から学習パラメータを取得
  - データセット存在チェック（不在時: エラーメッセージで終了、ADR 008）
  - `YOLO(base_model).train(data=..., epochs=..., patience=..., batch=..., imgsz=...)` を実行
  - ultralytics のデフォルト augmentation を最小限に設定（Roboflow で拡張済み、ADR 004）
  - 学習結果（best.pt パス、メトリクス）を返す
- `__main__.py`:
  - `load_config()` で設定を読み込み
  - `train(config)` を実行
  - 完了後に結果サマリーを表示（mAP50, epochs, best.pt パス）

**依存**: #002-01

- [x] 完了

### #002-03: モデル評価・配置

**対象ファイル**:
- `src/finger_tracker/training/__init__.py` — 評価・コピー関数を追加

**実装内容**:
- `evaluate_and_deploy(config, results)` 関数:
  - ultralytics の学習結果から mAP50 を取得・表示
  - `runs/detect/train/weights/best.pt` を `models/best.pt` にコピー
  - mAP50 >= 0.90 の場合: INFO ログで「目標達成」を表示
  - mAP50 < 0.90 の場合: WARNING ログで改善方針を案内（ADR 004 判断5 の順序）
  - `models/` ディレクトリが存在しない場合は自動作成
- `__main__.py` に組み込み: 学習完了後に自動実行

**依存**: #002-02

- [x] 完了

### #002-04: 動作確認

**内容**:
- データセット存在チェックの確認（`data/datasets/` がない状態でエラーメッセージ表示）
- Roboflow データセット配置後に `python -m finger_tracker.training` で学習実行
- 学習完了後の評価指標表示を確認
- `models/best.pt` が正しくコピーされていることを確認
- 実装ステータスの更新

**依存**: #002-03 + Roboflow アノテーション完了

- [x] 完了

## リスク

| リスク | 影響 | 対策 |
|--------|------|------|
| アノテーションデータ不足 | mAP50 が目標未達 | ADR 004 の改善方針に従い段階的に対処（データ確認→追加→拡張調整→モデルスケールアップ） |
| GPU 環境なし | 学習時間が長い（CPU のみ） | YOLOv8n は軽量で CPU でも学習可能。300 枚 × 100 エポックなら数十分〜数時間 |
| Roboflow エクスポート形式のずれ | data.yaml のパスが合わない | data.yaml 内のパスを training スクリプト側で調整する処理を追加 |

## 関連ドキュメント

- [ADR 003: データパイプライン](../design/decisions/003-data-pipeline.md) — データセット配置
- [ADR 004: YOLOv8 学習戦略](../design/decisions/004-yolo-training-strategy.md) — 学習パラメータ・評価基準
- [ADR 006: 設定管理方式](../design/decisions/006-config-management.md) — config.yaml 仕様
- [ADR 008: エラーハンドリング](../design/decisions/008-error-handling.md) — 起動時エラー対処
- [Phase 1 計画](./001-phase1-config-capture.md) — 前提となる config モジュール
