<!--
種別: status
対象: 実装ステータス
作成日: 2026-02-26
更新日: 2026-02-26
担当: AIエージェント
-->

# 実装ステータス

## モジュール別ステータス

| モジュール | ステータス | 備考 |
|-----------|----------|------|
| config | `done` | 設定管理 |
| capture | `done` | RealSense画像キャプチャ（RealSense接続環境で実機確認が必要） |
| training | `not-started` | YOLOv8モデル学習 |
| detection | `not-started` | 推論+3D距離計測 |
| scripts | `not-started` | ユーティリティ |

## 機能別ステータス

| 機能 | モジュール | ステータス | 備考 |
|------|-----------|----------|------|
| RealSense画像取得 | capture | `done` | RGB+深度フレーム取得 |
| 学習データ保存 | capture | `done` | 画像をdata/images/に保存 |
| YOLOv8 fine-tuning | training | `not-started` | Roboflowデータセット使用 |
| モデル評価 | training | `not-started` | 精度・速度の確認 |
| リアルタイム推論 | detection | `not-started` | YOLOv8-nano推論 |
| 深度→3D座標変換 | detection | `not-started` | rs2_deproject_pixel_to_point |
| ユークリッド距離計算 | detection | `not-started` | 2点間の3D距離 |
| ノイズフィルタ | detection | `not-started` | 中央値フィルタ |
| 設定ファイル管理 | config | `done` | カメラ・モデル・フィルタ設定 |
