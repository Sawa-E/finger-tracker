---
name: init-project
description: 新規プロジェクトの初期セットアップを対話型で実行する。CLAUDE.md、docs/体系、モジュールマッピングを一括生成する。プロジェクトの新規立ち上げ時に使用。
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(mkdir*), AskUserQuestion
---

# プロジェクト初期セットアップ

新規プロジェクトの CLAUDE.md と `docs/` ディレクトリ体系を対話型で構築する。

## 前提

- ドキュメント設計パターンは [DOCS_PATTERN.md](DOCS_PATTERN.md) に準拠する
- CLAUDE.md は [CLAUDE_TEMPLATE.md](CLAUDE_TEMPLATE.md) をベースに生成する
- テンプレート集は [TEMPLATES.md](TEMPLATES.md) を参照する

## ワークフロー

```
進捗:
- [ ] Step 1: プロジェクト情報収集（対話3バッチ）
- [ ] Step 2: CLAUDE.md 生成
- [ ] Step 3: docs/ ディレクトリ構造作成
- [ ] Step 4: GUIDE.md・TEMPLATE.md 生成
- [ ] Step 5: 初期仕様書作成
- [ ] Step 6: 初期ADR作成
- [ ] Step 7: ステータス文書作成
- [ ] Step 8: execute-review モジュールマッピング更新
- [ ] Step 9: settings.json のプロジェクトID反映
- [ ] Step 10: 品質チェック
```

### Step 1: プロジェクト情報収集

AskUserQuestion で3バッチに分けて情報を収集する。

**Batch 1**（基本情報）:

1. **プロジェクト名と概要**: 何を作るか
2. **技術スタック**: 言語・フレームワーク・DB等
3. **配布方法**: App Store / GitHub Release / npm / PyPI 等

**Batch 2**（構造情報）:

1. **ディレクトリ構成**: プロジェクトのトップレベル構造（既存コードがあれば Glob で取得）
2. **モジュール分割**: モジュール名・パス・依存先（レビューのパスマッピングに使用）

**Batch 3**（規模・フェーズ）:

1. **docs カテゴリ規模**: 最小 / 標準 / フル（下記参照）
2. **現在のフェーズ**: 構想段階 / プロトタイプ / 初期開発 / 運用中

カテゴリ選択の目安:

| 規模 | カテゴリ                                             |
| ---- | ---------------------------------------------------- |
| 最小 | design/decisions/, archive/                          |
| 標準 | + design/modules/, design/flows/, usecases/, status/ |
| フル | + plans/, review/, design/usecase_mapping/           |

参照プロジェクトが指定された場合は `docs/` を Glob で走査し、構造を分析する。

### Step 2: CLAUDE.md 生成

[CLAUDE_TEMPLATE.md](CLAUDE_TEMPLATE.md) を Read し、Step 1 で収集した情報でプレースホルダを置換して CLAUDE.md を生成する。

生成ルール:

- プロジェクト構造は実際のディレクトリを Glob で確認し、主要ファイルのコメントを含める
- 技術スタックはレイヤー別テーブルで記載
- アーキテクチャは各モジュールの責務と処理フローを記述
- 用語はプロジェクト固有のもののみ記載
- 参照プロジェクトの CLAUDE.md があれば品質基準として参考にする

### Step 3: docs/ ディレクトリ構造作成

`mkdir -p` で選択されたカテゴリのディレクトリを一括作成する。

```bash
mkdir -p docs/{archive,design/{decisions,modules,flows},plans/resolved,review/modules,usecases,status}
```

不要なカテゴリは除外する。

### Step 4: GUIDE.md・TEMPLATE.md 生成

各カテゴリに GUIDE.md と TEMPLATE.md を生成する。[TEMPLATES.md](TEMPLATES.md) を Read し、プロジェクト固有の情報で埋める。

**生成ルール**:

- プロジェクト名・技術スタック・対象読者をテンプレートに反映する
- コード参照形式はプロジェクトの言語に合わせる
- 空セクションを残さない

### Step 5: 初期仕様書作成

`docs/archive/initial_plan.md` にプロジェクトの初期仕様を記録する。

含める内容:

- プロジェクト概要・動機
- コア機能一覧
- アーキテクチャ概要
- 技術要件
- ターゲットユーザー

### Step 6: 初期ADR作成

最低限の ADR を作成する。[create-adr スキル](../create-adr/SKILL.md) の手順に従う。

必須ADR:

- `001-technology-stack.md` — 技術スタック選定（言語・フレームワーク・DB・ビルド・配布）

任意ADR（プロジェクトに応じて）:

- UIデザインシステム
- アーキテクチャパターン
- データモデル方針

### Step 7: ステータス文書作成

`docs/status/` に以下を生成する:

- `implementation.md` — モジュール別実装ステータス（全て `not-started`、または既存コードがあれば適切なステータス）
- `roadmap.md` — Phase 1-3 のロードマップ

### Step 8: execute-review モジュールマッピング更新

Step 1 で収集したモジュール分割情報を使い、`.claude/skills/execute-review/SKILL.md` のパスマッピングテーブルを更新する。

プレースホルダ `{module-N}` / `{paths-N}` を実際のモジュール名・パスに置換する。

### Step 9: settings.json のプロジェクトID反映

`.claude/settings.json` の `{project-id}` をプロジェクト名（kebab-case）に置換する。

同時に `.claude/skills/review/SKILL.md` の `{project-id}` も同じ値で置換する。

### Step 10: 品質チェック

全生成物に対して確認する:

- [ ] CLAUDE.md が存在し、全セクションが埋まっている
- [ ] 各カテゴリに GUIDE.md が存在する
- [ ] TEMPLATE.md が存在する（該当カテゴリ）
- [ ] 相互参照の相対パスが正しい
- [ ] メタデータコメントが記入されている（ADR）
- [ ] 空セクション・空ファイルがない
- [ ] プロジェクト固有の情報が正しく反映されている
- [ ] execute-review のパスマッピングがプロジェクトのモジュール構成と一致する
- [ ] settings.json のプロジェクトIDが正しい
- [ ] review/SKILL.md のチーム名がプロジェクトIDと一致する

## 出力

最終的に生成されたファイル一覧をツリー形式で報告する。
