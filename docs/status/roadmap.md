<!--
種別: status
対象: ロードマップ
作成日: 2026-02-26
更新日: 2026-02-28
担当: AIエージェント
-->

# ロードマップ

## Phase 1: データ収集・アノテーション

目標: YOLOv8 学習に十分な品質のデータセットを構築する

- config モジュール（カメラ設定）
- capture モジュール（RealSense画像キャプチャ）
- Roboflow でのアノテーション（約300枚、`red_finger` / `blue_finger`）

## Phase 2: モデル学習・評価

目標: リアルタイム推論に十分な精度・速度の YOLOv8-nano モデルを得る

- training モジュール（YOLOv8-nano fine-tuning）
- 推論精度・速度の評価
- 必要に応じてデータ拡張・追加収集

## Phase 3: リアルタイム計測

目標: 指間距離をリアルタイムで安定して計測できるシステムを完成させる

- detection モジュール（推論 + 3D距離計測）
- 深度ノイズ対策（中央値フィルタ）
- リアルタイム表示
- scripts（ユーティリティ）

## Phase 4: teleop-hand 連携

目標: 計測データを teleop-hand にリアルタイム送信し、ロボットハンド遠隔操作を実現する

- UDP データパブリッシャ（detection → teleop-hand、28バイトバイナリパケット）
- config.yaml による送信先・有効/無効の設定管理
