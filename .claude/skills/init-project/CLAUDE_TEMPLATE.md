# CLAUDE.md テンプレート

init-project スキルが CLAUDE.md を生成する際のテンプレート。`{placeholder}` をプロジェクト固有の情報で置換する。

---

```markdown
# CLAUDE.md

{project-name} — {project-summary}

## プロジェクト概要

{project-description}

## プロジェクト構造

```
{project-tree}
```

## ビルド・テスト

```bash
{build-commands}
```

## 技術スタック

| 層 | 技術 |
|---|---|
{tech-stack-rows}

技術選定の詳細: [docs/design/decisions/001-technology-stack.md](docs/design/decisions/001-technology-stack.md)

## アーキテクチャ

{architecture-sections}

## 用語

| 用語 | 定義 |
|------|------|
{glossary-rows}

## 実装ルール

{implementation-rules}

### コミットメッセージ

形式: `type(scope): 簡潔な説明`

```
feat(module): 新機能の説明
fix(module): バグ修正の説明
```

## タスク管理ルール

### 基本設定

タスクリストID `{project-id}-tasks` で統一（`.claude/settings.json`で設定済み）。

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
{docs-index-rows}
```

---

## セクション説明

| セクション | 内容 | 参考 |
|-----------|------|------|
| プロジェクト概要 | 何を作るか、主要機能、対応プラットフォーム | cb: macOS向けクリップボードマネージャー |
| プロジェクト構造 | ディレクトリツリー + 主要ファイルの説明 | cb: Sources/, crates/, docs/ 等 |
| ビルド・テスト | ビルド・テスト・実行のコマンド一覧 | cb: cargo build, xcodegen, xcodebuild |
| 技術スタック | レイヤー別の技術選定テーブル | cb: UI/ロジック/DB/FFI/ビルド等 |
| アーキテクチャ | モジュール別の責務・処理フロー・レイヤー間連携 | cb: Swift層/Rust層/ロギング/責務分離 |
| 用語 | プロジェクト固有の用語定義 | cb: ClipboardEntry, ContentType等 |
| 実装ルール | コーディング規約・設計上の制約 | cb: Swift-Rust間の型受け渡し等 |
| コミットメッセージ | `type(scope): description` 形式 | 共通 |
| タスク管理ルール | タスクリストID、サブエージェント設定 | 共通 |
| ドキュメントインデックス | docs/ 配下の主要ドキュメントへのリンク | cb: ADR, モジュール設計, フロー等 |
