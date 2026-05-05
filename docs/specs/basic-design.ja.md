# Praxia — 基本設計仕様書

> ステータス: **v1.0** · 最終更新: 2026-05 · 🇬🇧 [English](basic-design.en.md)

---

## 1. 目的

Praxia は **個人 → 組織のサイクリックなメモリ循環** を備えたマルチエージェントオーケストレータ。明示的な「保存」操作なしに、個人の暗黙的業務知見を組織資産化するためのランタイム。

設計思想:

- **OSS 第一** (Apache 2.0) — 採用判断にセールス商談を必要としない
- 全プラグインポイントで **ベンダーニュートラル**: LLM (LiteLLM) / LTM (6 種 + 合成) / コネクタ (6 種既定 + entry-point) / ファイル形式 / 出力形式
- **エンタープライズ要件をカーネル組込み**: RBAC / SSO / ACL / 監査ログ / ユーザ委譲 OAuth
- **コンポーザブル** — 全拡張ポイントで `Registry` プリミティブを共有

## 2. スコープ

| 含む | 含まない (v1) |
|---|---|
| マルチエージェントフローのオーケストレーション | マルチテナント SaaS ホスティング |
| 個人メモリの自動抽出 | モバイルネイティブアプリ |
| 個人 → 組織への昇格 | ホスト型 GUI / ダッシュボードサービス |
| 6 業務ドメインスキル + 拡張ポイント | リアルタイムストリーミング生成 |
| 6 ストレージ/SaaS コネクタ + 拡張ポイント | フェデレーション学習 |
| 認証 / 認可 / SSO / ACL / 監査ログ | アウトカムへの因果推論 |
| ファイルパーサ (PDF / Office / CSV / HTML / TXT / MD) | |
| 出力エクスポータ (HTML / PPTX / DOCX / MD / JSON) | |
| 音声 I/O (STT + TTS) | |
| 任意 FastAPI HTTP サーバ (`praxia serve`) | |

## 3. システムコンテキスト

```
                    ┌──────────────────────────────────────┐
                    │       外部利用者 / クライアント       │
                    │  (browser / mobile / CLI / SDK)      │
                    └──────────────┬───────────────────────┘
                                   │
                  ┌────────────────┴───────────────────┐
                  │                                    │
        ┌─────────▼──────────┐               ┌─────────▼──────────┐
        │  Streamlit UI      │               │  FastAPI server    │
        │  (モード A)        │               │  (モード B 任意)   │
        └─────────┬──────────┘               └─────────┬──────────┘
                  │            Praxia SDK              │
                  └────────────────┬───────────────────┘
                                   │
       ┌───────────────────────────▼────────────────────────────┐
       │                    オーケストレータ                    │
       │  ┌────────┐  ┌─────────┐  ┌─────────┐  ┌────────────┐  │
       │  │ Flows  │  │ Skills  │  │  Auth   │  │ Connectors │  │
       │  │ engine │  │ registry│  │ + ACL   │  │  registry  │  │
       │  └────┬───┘  └────┬────┘  └────┬────┘  └─────┬──────┘  │
       │       │           │            │             │         │
       │      ┌────────▼──┐ ┌─▼──────────┐ ┌▼─────────────────┐ │
       │      │ Memory    │ │  I/O       │ │ LLM (LiteLLM)    │ │
       │      │ (5 層 +   │ │ parsers /  │ │ Claude / GPT /   │ │
       │      │  policy)  │ │ exporters /│ │ Gemini / Qwen /  │ │
       │      └───────────┘ │ audio      │ │ Gemma / Ollama   │ │
       │                    └────────────┘ └──────────────────┘ │
       └────────────────────────────┬───────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
   ┌────▼──────┐  ┌────────────┐  ┌─▼─────────┐  ┌──────────────▼──┐
   │ LTM       │  │ Box / SP / │  │ OIDC IdP  │  │ ローカル FS:    │
   │ (Mem0/Zep/│  │ Drive /    │  │ (Google / │  │ JSON memory,    │
   │ HindSight)│  │ kintone /  │  │  MS Entra │  │ frozen .md,     │
   │           │  │ Salesforce │  │  / Okta)  │  │ audit JSONL     │
   └───────────┘  └────────────┘  └───────────┘  └─────────────────┘
```

## 4. レイヤアーキテクチャ

| 層 | モジュール | 役割 |
|---|---|---|
| 0 | `praxia.config` | 統一設定: env > .env > `.praxia/config.toml` |
| 1 | `praxia.core.llm` | マルチプロバイダ LLM クライアント (LiteLLM) |
| 2 | `praxia.core.agent` / `flows` / `skills` | エージェント + フロー + スキルレジストリ |
| 3 | `praxia.memory` | 5 層メモリスタック + ポリシー + 複数 LTM 合成 |
| 4 | `praxia.auth` | 認証 (API キー + JWT + SSO) / 認可 (RBAC + ACL) / 監査 |
| 5 | `praxia.connectors` | ストレージ / SaaS 連携 + ユーザ委譲 OAuth |
| 6 | `praxia.io` | ファイルパーサ + 音声 I/O + 出力エクスポータ |
| 7 | `praxia.cli` / `praxia.ui` / `praxia.server` | フロント — CLI / Streamlit / FastAPI |

層は単方向 (下位は上位を import しない)。プラグイン検出は全拡張ポイントで `praxia.extensions.Registry` を使用。

## 5. メモリアーキテクチャ (層 3 詳細)

```
  ┌── Layer 1: 個人メモリ ──────────┐    バックエンド選択肢:
  │  PersonalMemory(user_id, ...)   │    - json (既定)
  │  Mode: accumulate / read_only   │    - mem0 / langmem / letta /
  │                                 │      zep / hindsight
  │                                 │    - CompositeBackend (RRF 融合)
  │                                 │    - RoutedBackend (rule/LLM router)
  └────────────────┬────────────────┘
                   │  SleepTimeConsolidator
                   │  3 経路 PromotionEngine: 頻度 + 成果 + LLM 自己評価
                   ▼
  ┌── Layer 3: 共有ブロック (組織) ──┐
  │  SharedMemory(org_id, ...)      │
  │  Letta スタイル read/write      │
  └────────────────┬────────────────┘
                   │  PR レビュー (キュレーション)
                   ▼
  ┌── Layer 4: Markdown 凍結 + git ──┐
  │  MarkdownStore(...)              │
  │  Claude Skills / Cursor Rules /  │
  │  Copilot instructions と互換     │
  └──────────────────────────────────┘

  Layer 5 (任意): Graph 層 — Zep / Graphiti による時系列 KG
```

二重制御 (admin policy + user preference) で Layer 1 のバックエンド選択と蓄積モードを統制。詳細: `praxia.memory.policy`。

## 6. 設定モデル

優先順位 (上位優先):

1. プロセス環境変数 (例: `ANTHROPIC_API_KEY`)
2. 作業ディレクトリの `.env`
3. `.praxia/config.toml` (`praxia config set / get / show` で管理)

カテゴリ:
- LLM プロバイダ鍵 (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DASHSCOPE_API_KEY`, `OLLAMA_API_BASE`)
- メモリ (`PRAXIA_MEMORY_BACKEND`, `PRAXIA_MEMORY_MODE`)
- 認証 (`PRAXIA_JWT_SECRET`, `PRAXIA_TOKEN_ENC_KEY`)
- SSO (`PRAXIA_SSO_PROVIDER`, `PRAXIA_SSO_CLIENT_ID`, ...)
- ユーザ委譲 OAuth (`PRAXIA_OAUTH_<PROVIDER>_CLIENT_ID/SECRET`)
- コネクタ共通認証情報 (`PRAXIA_CONN_<NAME>_<KEY>`)

正準リファレンスは `.env.example` を参照。

## 7. 非機能要件

| NFR | 目標 | 達成手段 |
|---|---|---|
| パフォーマンス | 初回フロー実行 5 秒以内 (LLM レイテンシ除く) | レジストリキャッシュ・ストリーム解析・インメモリエクスポート |
| スケーラビリティ | 単一プロセスで 100 アクティブユーザ | ユーザ毎ネームスペース、I/O バウンド設計 |
| 可用性 | 99.5% (単一ホスト自管理) | `.praxia/` 以外は stateless、共有 FS で HA 化 |
| セキュリティ | OWASP Top 10 準拠 | API キーハッシュ・OAuth トークン暗号化・JWT 署名・監査ログ |
| プライバシー | 個人 → 組織昇格時の PII フィルタ | `PromotionEngine._self_eval` で除外 |
| 監査性 | 全特権アクション記録 | `.praxia/audit/` 追記専用 JSONL、CSV/JSON エクスポート |
| 互換性 | Claude / OpenAI / Gemini / Qwen / Gemma / 100+ (LiteLLM) | LLM 層でプロバイダ非依存 |
| ポータビリティ | Linux / macOS / Windows | Pure Python、C 拡張は任意依存のみ |
| 拡張性 | 新コネクタ / バックエンド / スキルが 50 LoC 未満 | `Registry` + entry-points |

## 8. デプロイトポロジ

| モード | 構成要素 | 推奨ケース |
|---|---|---|
| **A. フルスタック** | Streamlit UI + Praxia コア | 内製チーム、最短ルート |
| **B-1. SDK 埋込** | ユーザの Python サービス + Praxia ライブラリ | Python 既存基盤 |
| **B-2. HTTP サービス** | `praxia serve` (FastAPI) + 自前フロント | Python 以外 / モバイル |

詳細: [`docs/deployment-modes.ja.md`](../deployment-modes.ja.md)。

## 9. ライフサイクル / データフロー

「フロー実行」典型ライフサイクル:

1. クライアント → 認証 (API キー / JWT 検証)
2. 認証 → ACL (resource:action 許可確認)
3. Praxia → Flow (`flows.get(name)`)
4. Flow → Skills / Agent (各ステップ、systemprompt + LLM via LiteLLM)
5. Skills → Memory (関連コンテキスト検索、accumulate なら episode 記録)
6. Memory → backend (単一 / composite / routed)
7. 結果 → Exporter (ユーザ要求形式)
8. 監査ログ書き込み

## 10. Out-of-band ライフサイクル

| プロセス | 頻度 | 用途 |
|---|---|---|
| `praxia consolidate` | 夜間 | sleep-time 統合実行 → 個人 → 組織昇格 |
| `praxia freeze` | 安定パターン検出時 | 共有ブロックを git 管理 Markdown へ |
| `praxia admin export-*` | 必要時 / 定期 | コンプライアンス / SIEM への監査ログ・ユーザデータエクスポート |
| OAuth トークン更新 | 失効時 | サイレント (`OAuthTokenStore` が処理) |

## 11. 信頼境界

```
   [ブラウザ/クライアント] -->|HTTPS|--> [Auth: AuthManager]
                                            |
                                  (API キー / JWT / SSO)
                                            |
   [信頼できない入力]                        v
   [ユーザアップロードファイル] -->|parser|-> [サニタイズ済みテキスト]
                                            |
   [LLM プロバイダ]  <--|HTTPS|<-- [LLM: LiteLLM クライアント]
                                            |
   [メモリバックエンド]    <-- [Memory + Policy ガード] <-- [ACL チェック]
   [コネクタ連携先]        <-- [ユーザ毎 OAuth トークン]  <-- [ACL チェック]
   [監査ログ .jsonl]       <-- [AuditLog (追記専用)]
```

ユーザアップロードファイルは `praxia.io.parsers` 経由で「信頼できない」→「信頼可能テキスト」の境界を越える。LLM 応答は盲信せず `praxia.eval.hallucination` で検証可能。

## 12. 標準 / 相互運用

- **Claude Skills 形式** — `Skill.to_skill_md()` で Anthropic 仕様互換 SKILL.md
- **Model Context Protocol (MCP)** — スキルが互換ツール記述子を実装
- **OpenAI tool-call 形式** — flows / agents が GPT-4o 形式のツールコールを発行
- **OIDC / OAuth 2.0** — SSO + ユーザ委譲は PKCE 付き標準フロー
- **OWASP ASVS Level 1** — 認証認可設計が ASVS コントロール準拠

## 13. 用語集

| 用語 | 意味 |
|---|---|
| Flow | エージェントステップの宣言的 DAG |
| Skill | Capability bundle: prompt + tools + ref docs (Claude Skills 互換) |
| LTM | Long-term memory backend (長期記憶) |
| RRF | Reciprocal Rank Fusion (複数バックエンド融合) |
| Promotion | 個人 → 組織メモリ昇格 |
| Consolidator | PromotionEngine を全ユーザに走らせる sleep-time ジョブ |
| Connector | 外部ストレージ / SaaS の pull/push プラグイン |
| Mode (memory) | accumulate (書込有効) / read_only (書込無効化) |
