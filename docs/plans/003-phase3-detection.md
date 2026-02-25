<!--
種別: plans
対象: Phase 3 — detection モジュール実装
作成日: 2026-02-26
更新日: 2026-02-26
ステータス: active
優先度: 中
担当: AIエージェント
-->

# Phase 3: detection モジュール実装

## 概要

YOLOv8-nano 推論、BB 内 HSV フィルタによるマスク重心算出、RealSense 深度→3D 座標変換、各指独立カルマンフィルタ、指間距離計算、OpenCV リアルタイム表示、CSV 記録までを一貫して行う detection モジュールを実装する。本プロジェクトの最終成果物となるモジュール。

## 現状分析

- Phase 1（config + capture）、Phase 2（training）の計画が作成済み
- ADR 002（深度計測ロジック）、ADR 005（リアルタイム表示）、ADR 007（ログ・記録）で設計判断が完了
- detection は config、models/best.pt に依存し、capture・training には直接依存しない

## 前提条件

- Phase 1 の config モジュールが実装済みであること
- `models/best.pt` に学習済みモデルが存在すること（Phase 2 完了）
- RealSense D435i が接続されていること

## ゴール

- [ ] `python -m finger_tracker.detection` でリアルタイム指間距離計測が動作する
- [ ] RGB 映像 + BB オーバーレイ + 距離表示のシングルウィンドウが表示される
- [ ] カルマンフィルタにより距離値が安定している
- [ ] 深度欠損・未検出時に ADR 002 の対処が正しく機能する
- [ ] `logs/` に CSV 計測記録が保存される
- [ ] `q` / ESC で安全に終了し、CSV がフラッシュされる

## スコープ

### 含む

- YOLO 推論 + BB 描画
- BB 内 HSV 色フィルタ → マスク重心ピクセル算出
- 深度値取得（無効値対処: マスク内→BB 内→直前値保持）
- `rs2_deproject_pixel_to_point` による 3D 座標変換
- 各指独立 3D カルマンフィルタ（等速度モデル、6D 状態）
- フィルタ済み座標間のユークリッド距離計算
- OpenCV シングルウィンドウ表示（ADR 005 レイアウト準拠）
- CSV 計測記録（ADR 007 フォーマット準拠）
- グレースフルシャットダウン（ADR 008）

### 含まない

- デバッグモード（深度マップ表示、`d` キートグル）— 後日拡張
- TensorBoard や Matplotlib によるリアルタイムグラフ
- ロボットハンドへの指令値送信（将来の拡張）
- テストコード（RealSense 依存のため別計画）

## タスクリスト

### #003-01: detection 基盤 — YOLO 推論 + HSV フィルタ + 深度→3D

**対象ファイル**:
- `src/finger_tracker/detection/__init__.py` — コア処理関数群
- `src/finger_tracker/detection/__main__.py` — エントリポイント

**実装内容**:
- RealSense パイプライン初期化（RGB + 深度、align 設定）
- YOLO モデルロード（config の model.path）
- 起動時チェック（RealSense 接続、モデルファイル存在、ADR 008）
- メインループ骨格:
  1. フレーム取得（RGB + aligned 深度）
  2. YOLO 推論 → `red_finger` / `blue_finger` の BB 取得
  3. BB 内 HSV フィルタ → マスク生成 → 重心ピクセル算出（ADR 002 判断1）
  4. 深度値取得 — 無効値対処フロー（ADR 002 判断3）:
     - マスク重心 → マスク内中央値 → BB 内探索 → 直前値保持（タイムアウト付き）
  5. `rs2_deproject_pixel_to_point` で 3D 座標に変換
- `q` / ESC で終了

**依存**: Phase 1（config モジュール）

- [ ] 完了

### #003-02: カルマンフィルタ実装

**対象ファイル**:
- `src/finger_tracker/detection/__init__.py` — カルマンフィルタクラスを追加

**実装内容**:
- `KalmanFilter3D` クラス（各指に1つずつインスタンス化）:
  - 状態ベクトル: `[x, y, z, vx, vy, vz]` (6D)
  - 観測ベクトル: `[x, y, z]` (3D)
  - 遷移行列 F（等速度モデル、dt = 1/fps）
  - 観測行列 H
  - プロセスノイズ Q（config の filter.kalman_q から生成）
  - 観測ノイズ R（config の filter.kalman_r から生成）
  - `predict()`: 予測ステップ
  - `update(measurement)`: 更新ステップ（観測あり時）
  - `get_position()`: フィルタ済み位置 [x, y, z] を返す
- メインループに統合:
  - 観測あり → predict + update
  - 観測なし（深度タイムアウト超過） → predict のみ
- フィルタ済み座標からユークリッド距離を算出

**依存**: #003-01

- [ ] 完了

### #003-03: OpenCV リアルタイム表示

**対象ファイル**:
- `src/finger_tracker/detection/__init__.py` — 描画関数を追加

**実装内容**:
- ADR 005 のレイアウトに準拠した描画:
  - BB オーバーレイ（赤 BB は赤色、青 BB は青色）
  - BB 間に距離線を描画 + 距離テキスト
  - 上部: FPS + 検出信頼度（`Conf: 0.95/0.93`）
  - 下部: 距離を大きく表示（`Distance: 45.2 mm`）
  - 未検出時: `--- mm` 表示
- FPS 計測（実測値を表示）

**依存**: #003-02（カルマンフィルタ済み座標を使用）

- [ ] 完了

### #003-04: CSV 計測記録

**対象ファイル**:
- `src/finger_tracker/detection/__init__.py` — CSV 記録関数を追加

**実装内容**:
- ADR 007 のフォーマットに準拠した CSV 出力:
  - ヘッダ: `timestamp,distance_mm,red_x,red_y,red_z,blue_x,blue_y,blue_z,red_conf,blue_conf`
  - タイムスタンプ: ISO 8601（ミリ秒精度）
  - 未検出時: 該当列を空にする
- ファイル名: `measurement_{セッション開始時刻}.csv`
- 保存先: `logs/`（ディレクトリ自動作成）
- フレームごとに書き込み（バッファリングは Python のデフォルトに任せる）

**依存**: #003-02（フィルタ済み座標を記録）

- [ ] 完了

### #003-05: グレースフルシャットダウン + 統合

**対象ファイル**:
- `src/finger_tracker/detection/__init__.py` — cleanup 処理
- `src/finger_tracker/detection/__main__.py` — try/except/finally 統合

**実装内容**:
- ADR 008 のグレースフルシャットダウン:
  - `KeyboardInterrupt` (Ctrl+C) のキャッチ
  - CSV フラッシュ・クローズ
  - RealSense パイプライン停止
  - OpenCV ウィンドウ破棄
- RealSense 実行中切断のリトライ（3回、1秒間隔、ADR 008 判断2）
- アプリケーションログ出力（Python logging、ADR 007）:
  - 起動・終了の INFO ログ
  - 設定値の INFO ログ
  - `logs/app_{セッション開始時刻}.log` に出力

**依存**: #003-01〜#003-04（全コンポーネントの統合）

- [ ] 完了

### #003-06: 動作確認

**内容**:
- RealSense 接続環境で `python -m finger_tracker.detection` を実行
- 表示レイアウトの確認（BB、距離線、FPS、信頼度、距離テキスト）
- 指サックを動かして距離値の変化・安定性を確認（カルマンフィルタ効果）
- 片方の指サックを隠して未検出時の表示を確認（`--- mm`）
- 深度欠損時の挙動確認（カメラに近づきすぎる等）
- `q` / ESC で終了し、CSV ファイルが正しく保存されていることを確認
- CSV の中身を確認（タイムスタンプ、座標値、距離値の妥当性）
- 実装ステータスの更新

**依存**: #003-05

- [ ] 完了

## リスク

| リスク | 影響 | 対策 |
|--------|------|------|
| カルマンフィルタ Q/R チューニング | 距離値が振動する or 追従が遅い | config.yaml で Q/R を変更可能。実機テストで調整 |
| HSV 閾値が環境光に依存 | 指サックの色検出が不安定 | config.yaml で HSV 範囲を調整可能。照明条件を固定して使用 |
| CPU 推論で 30fps 未達 | 表示がカクつく | YOLOv8n は CPU でも 10-20ms。パフォーマンスバジェット的には達成可能（ADR 005） |
| detection モジュールが大きくなる | 可読性・保守性の低下 | ADR 009 で「肥大化した場合は後から分割」と決定済み。まずは単一モジュールで実装 |

## 関連ドキュメント

- [ADR 002: 深度計測ロジック](../design/decisions/002-depth-measurement-logic.md) — HSV フィルタ、カルマンフィルタ、無効深度対処
- [ADR 005: リアルタイム表示設計](../design/decisions/005-realtime-display.md) — レイアウト、表示項目、FPS 目標
- [ADR 007: ログ・記録方式](../design/decisions/007-logging-recording.md) — CSV フォーマット、ログ出力
- [ADR 008: エラーハンドリング](../design/decisions/008-error-handling.md) — 起動時エラー、グレースフルシャットダウン
- [Phase 1 計画](./001-phase1-config-capture.md) — config モジュール（依存）
- [Phase 2 計画](./002-phase2-training.md) — models/best.pt の生成元
