<!--
種別: plans
対象: UDP データパブリッシャ実装
作成日: 2026-02-28
更新日: 2026-02-28
ステータス: resolved
優先度: 高
担当: AIエージェント
-->

# Phase 4: UDP データパブリッシャ実装

## 概要

detection モジュールが計測した指間距離と指先3D座標を、UDP ソケット経由で teleop-hand（C++ リアルタイム制御システム）に毎フレーム送信する機能を追加する。

## 現状分析

- detection モジュールは毎フレーム `distance_mm`、`red_pos`（[x,y,z]）、`blue_pos`（[x,y,z]）を算出済み
- データは CSV に記録されているが、外部プロセスへのリアルタイム送信手段がない
- teleop-hand 側の受信は完全実装済み:
  - `inc/comm/finger_data.h` — 28バイト構造体（float32 × 7）
  - `inc/comm/udp_receiver.h` — ノンブロッキング UDP 受信クラス
  - `config/comm.json` — ポート 50000
- finger-tracker の `config.yaml` に UDP 関連の設定項目がない

## ゴール

- [x] detection の毎フレームで teleop-hand 互換の 28バイト UDP パケットが送信される
- [x] 検出失敗時は `distance_mm = -1.0` のセンチネルパケットが送信される
- [x] `config.yaml` の `udp.enabled: false` で送信を無効化できる
- [x] finger-tracker 単体起動時（teleop-hand 未起動）でもエラーなく動作する

## スコープ

### 含む

- `config.yaml` への `udp` セクション追加（host, port, enabled）
- `detection/__init__.py` への UDP 送信コード組み込み（初期化・送信・クリーンアップ）
- ADR 010 に準拠したパケットレイアウト（28バイト、リトルエンディアン float32 × 7）

### 含まない

- teleop-hand 側のコード変更（既に実装済み）
- teleop-hand との結合テスト手順（別途実施）
- 自動テストコード（RealSense 依存のため別計画）
- パケットロス統計やヘルスチェック機能

## タスクリスト

### #004-01: config.yaml に udp セクションを追加

**対象ファイル**:
- `config.yaml`

**実装内容**:
- `udp` セクションを追加:
  ```yaml
  udp:
    host: "127.0.0.1"    # teleop-hand の IP アドレス
    port: 50000           # teleop-hand の受信ポート
    enabled: true         # false で送信を無効化
  ```
- teleop-hand の `config/comm.json`（`"port": 50000`）と一致させる

**依存**: なし

- [x] 完了

### #004-02: detection モジュールに UDP 送信を組み込む

**対象ファイル**:
- `src/finger_tracker/detection/__init__.py`

**実装内容**:

1. **インポート追加**（ファイル先頭）:
   - `import socket`
   - `import struct`

2. **UDP 送信関数の追加**:
   - `_send_udp(sock, dest, distance_mm, red_pos, blue_pos)`:
     - 両座標有効時: `struct.pack("<7f", distance_mm, *red_pos, *blue_pos)`
     - それ以外: `struct.pack("<7f", -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)`
     - `sock.sendto(packet, dest)` で送信

3. **`run()` 初期化部**（CSV 初期化の直後あたり）:
   - `config.yaml` から `udp` セクションを読み込み
   - `enabled: true` の場合のみ `socket.socket(AF_INET, SOCK_DGRAM)` を作成
   - 送信先タプル `(host, port)` を保持
   - ログ出力: `logger.info("UDP 送信有効: %s:%d", host, port)`

4. **メインループ内**（CSV 書き込み直後、`cv2.waitKey` の前）:
   - `_send_udp()` を呼び出し

5. **`finally` ブロック**（`pipeline.stop()` の前）:
   - `udp_sock.close()`

**依存**: #004-01

- [x] 完了

### #004-03: 動作確認 + ドキュメント更新

**内容**:
- `config.yaml` の `udp.enabled: false` で finger-tracker を起動し、UDP 関連のエラーが出ないことを確認
- `udp.enabled: true` で起動し、teleop-hand 未起動でもエラーなく動作することを確認（UDP は sendto で相手不在でもエラーにならない）
- `docs/status/implementation.md` にフェーズ4完了を追記

**依存**: #004-02

- [x] 完了

## リスク

| リスク | 影響 | 対策 |
|--------|------|------|
| sendto でのネットワークエラー | 計測ループが止まる | try/except で sendto を囲み、エラーをログに記録して続行 |
| エンディアン不一致 | teleop-hand がデータを正しく読めない | 両端 x86 リトルエンディアン。`struct.pack("<7f", ...)` で明示的に指定 |
| ポート番号の不一致 | パケットが届かない | config.yaml と teleop-hand の comm.json で同一ポートを管理。ADR 010 に記録済み |

## 関連ドキュメント

- [ADR 010: UDP パブリッシャ](../design/decisions/010-udp-publisher.md) — 通信方式の設計判断
- [ADR 006: 設定管理方式](../design/decisions/006-config-management.md) — config.yaml 管理方針
- [ADR 008: エラーハンドリング](../design/decisions/008-error-handling.md) — グレースフルシャットダウン
- [Phase 3 計画](./resolved/003-phase3-detection.md) — detection モジュール実装（本計画の前提）
- teleop-hand: `inc/comm/finger_data.h` — パケット構造体
- teleop-hand: `inc/comm/udp_receiver.h` — UDP 受信クラス
