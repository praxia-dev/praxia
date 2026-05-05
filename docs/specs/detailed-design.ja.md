# Praxia — 詳細設計仕様書

> ステータス: **v1.0** · 🇬🇧 [English](detailed-design.en.md)

モジュール単位のクラス設計、横断的な処理のシーケンス図、データ構造、エラーハンドリング、並行制御モデルを記述。Praxia を拡張するときや、モジュール跨ぎの不具合を調査するときに参照。

---

## 1. パッケージ構成

```
praxia/
├── __init__.py          # 公開 API の re-export
├── config.py            # PraxiaConfig — 統一キー解決
├── core/
│   ├── llm.py           # LLM, ProviderConfig, LLMResponse, DEFAULT_ALIASES
│   ├── agent.py         # Agent (単一ターンの LLM 呼出)
│   └── orchestrator.py  # Praxia (トップレベルファサード)
├── flows/               # FlowResult, Flow, 組込フロー
├── skills/
│   ├── skill.py         # Skill, SkillManifest
│   ├── registry.py      # SkillRegistry (personal / org / distributed)
│   ├── prompts.py       # PromptStore (3 スコープ)
│   ├── output_format.py # OutputFormatSkill
│   └── business/        # 6 業務スキル
├── memory/
│   ├── personal.py      # PersonalMemory + MemoryEntry + MemoryMode
│   ├── shared.py        # SharedMemory
│   ├── markdown_store.py # Layer-4 凍結 Markdown
│   ├── consolidator.py  # SleepTimeConsolidator
│   ├── promoter.py      # PromotionEngine, PromotionVerdict
│   ├── policy.py        # MemoryAdminPolicy, MemoryUserPreference, resolve_memory_config
│   ├── composite.py     # CompositeBackend, WeightedBackend (複数 LTM 融合)
│   ├── router.py        # RuleRouter, LLMRouter, RoutedBackend, RouteDecision
│   └── backends/        # MemoryBackend Protocol 実装 6 種
├── auth/                # AuthManager, AuditLog, PolicyManager, AdminExporter, SSO
├── connectors/
│   ├── base.py          # Connector Protocol, ConnectorItem, MissingDependencyError
│   ├── registry.py      # CONNECTORS レジストリ
│   ├── box.py / sharepoint.py / dropbox_.py / gdrive.py / kintone.py / salesforce.py
│   └── oauth/           # OAuthFlow + OAuthTokenStore (暗号化)
├── io/
│   ├── parsers/         # PDF / Office / CSV / HTML / TXT / MD / structured
│   ├── audio/           # STT, TTS
│   └── exporters/       # md, html, json, pptx, docx
├── eval/                # ハルシネーション検出、retrieval メトリクス
├── analytics/           # Dashboard, 利用統計
├── extensions.py        # Registry, lazy()
├── cli/main.py          # Typer CLI
├── ui/                  # Streamlit UI (モード A)
└── server/              # FastAPI HTTP server (モード B)
```

---

## 2. コアドメインモデル

### 2.1 `Praxia` (オーケストレータファサード)

```python
class Praxia:
    def __init__(
        self,
        *,
        user_id: str = "default",
        org_id: str = "default",
        llm: LLM | None = None,
        config: PraxiaConfig | None = None,
        memory_dir: Path = Path(".praxia"),
        enable_shared_memory: bool = True,
    ) -> None: ...

    @property
    def llm(self) -> LLM: ...
    @property
    def personal_memory(self) -> PersonalMemory: ...
    @property
    def shared_memory(self) -> SharedMemory | None: ...
    @property
    def auth(self) -> AuthManager: ...

    def run_flow(self, name: str, inputs: dict) -> FlowResult: ...
    def run_skill(self, name: str, input: str, **kwargs) -> str: ...
```

`run_*` 呼出時の副作用:
1. `MemoryAdminPolicy + MemoryUserPreference` 解決 → 実効バックエンド/モード決定
2. `auth.policies` で認可チェック
3. フロー / スキル実行
4. `mode == accumulate` なら `episode` 記録
5. 監査ログ追記

### 2.2 `LLM` (プロバイダ抽象)

```python
class LLM:
    config: ProviderConfig

    @property
    def model(self) -> str: ...      # alias 解決済み
    @property
    def provider(self) -> str: ...    # 最初の '/' より前

    def complete(self, messages, *, tools=None, response_format="text", **overrides) -> LLMResponse: ...
    async def acomplete(self, messages, **kwargs) -> LLMResponse: ...
```

内部:
- `complete()` は `ProviderConfig` + 呼出毎オーバライドで kwargs 構築 → `litellm.completion(**kwargs)`
- LiteLLM は **遅延 import** — install せずスキル / フロー閲覧可
- `auto_detect()` の優先順: ANTHROPIC > OPENAI > GEMINI > DASHSCOPE > local (`PRAXIA_LOCAL_MODEL`、既定 `qwen-local`)

### 2.3 `MemoryBackend` Protocol

```python
class MemoryBackend(Protocol):
    def add(self, *, user_id, text, kind, metadata) -> MemoryRecord: ...
    def search(self, *, user_id, query, limit) -> list[MemoryRecord]: ...
    def all(self, *, user_id=None) -> list[MemoryRecord]: ...
    def clear(self, *, user_id=None) -> None: ...

@dataclass
class MemoryRecord:
    id: str
    user_id: str
    text: str
    kind: str           # "episode" | "fact" | "preference" | "outcome" | カスタム
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)
```

実装:
- **JsonBackend** — JSONL 追記 + 線形スキャン (BM25 風ランキング、追加依存ゼロ)
- **Mem0Backend** — `mem0ai` ラップ。ハイブリッド検索 + エンティティ連結
- **LangMemBackend** — `langmem` ラップ。ネームスペース付きセマンティックメモリ
- **LettaBackend** — `letta-client` ラップ。read-only ブロック対応
- **ZepBackend** — `zep-python` + Graphiti。時系列 KG
- **HindSightBackend** — `hindsight` ラップ。純ベクトル

### 2.4 複数 LTM 合成設計

```
                    PersonalMemory.search(query, limit)
                                   │
                   ┌───────────────▼──────────────┐
                   │  backend  ← ユーザ注入       │
                   └───────────────┬──────────────┘
                  ┌────────────────┼────────────────┐
                  │                │                │
        ┌─────────▼─────┐  ┌───────▼──────┐  ┌──────▼───────┐
        │ 単一バックエンド│  │ Composite    │  │ Routed       │
        │ (JsonBackend / │  │ Backend      │  │ Backend      │
        │  Mem0Backend / │  │              │  │              │
        │  ...)          │  │ 並列実行 +   │  │ Router で     │
        └────────────────┘  │ 融合         │  │ 1..N 選択     │
                            └──────┬───────┘  └──────┬───────┘
                                   │                 │
                          ┌────────▼─────────────────▼────────┐
                          │ ThreadPoolExecutor (max_workers)  │
                          └────────────┬──────────────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │  N MemoryBackend 実装    │
                          │  (各々別スレッド)        │
                          └─────────────────────────┘
```

融合戦略 (`CompositeBackend._fuse_*`):
- **rrf**: `score(d) = Σ_b weight_b / (k + rank_b(d))` k=60。既定で堅実
- **union**: id で dedupe、最初に出現した順を維持
- **intersection**: `min_agreement` 個以上のバックエンドにある id のみ
- **weighted**: `Σ_b weight_b * (1 - rank_b(d) / |R_b|)`
- **llm_rerank**: 重複除去プールを 3·limit でキャップ → `rerank_fn(query, pool)` 呼出

失敗処理: 各バックエンドの例外は捕捉して空結果扱い。生存バックエンドで fan-out 続行。

### 2.5 メモリルーティング (`RuleRouter`)

```python
DEFAULT_RULES = [
    (regex, [backend_pref...], reason),
    ...
]
```

順序:
1. 監査 / changelog / 履歴 → `[json, mem0]`
2. 時系列 (`last week` / `先月`) → `[zep, mem0, hindsight]`
3. エンティティ (`who is` / `について`) → `[mem0, hindsight, json]`
4. 類似 (`similar` / `類似`) → `[hindsight, mem0, letta]`
5. フォールバック → `[mem0, hindsight, json]`

実装上の注意: 正規表現は ASCII 部分 (`\b` 付) と CJK 部分 (`\b` 無) を or 結合。Python の `\b` は CJK 文字同士の境界には立たないため。

### 2.6 メモリポリシー解決

```
 ┌─ admin.enforced_backend? ── yes ─→ backend = enforced ─┐
 │                                                          │
 no                                                         │
 │                                                          │
 ┌─ requested_backend && admin.allowed? ─ yes ─→ requested ─┤
 │                                                          │
 no                                                         │
 │                                                          │
 ┌─ user_pref.backend && admin.allowed? ─ yes ─→ pref ──────┤
 │                                                          │
 no                                                         │
 │                                                          │
 └─→ admin.default_backend                                  │
                                                            │
                                                            ▼
                                                    (実効 backend)

 ┌─ admin.mode_locked? ── yes ─→ mode = admin.default_mode (locked)
 │
 no
 │
 ┌─ user_role in admin.accumulate_locked_to? ─ yes ─→ "accumulate" (locked)
 │
 no
 │
 ┌─ requested_mode? ─── yes ─→ requested
 │
 no
 │
 ┌─ user_pref.mode? ─── yes ─→ pref
 │
 no
 │
 └─→ admin.default_mode
```

`ResolvedMemoryConfig.reason` が解決トレースを保持。

---

## 3. 横断シーケンス図

### 3.1 SDK: メモリ + ACL を伴うフロー実行

```
 Caller   Praxia   AuthManager   PolicyManager   Memory(policy)   PersonalMemory   Flow   LLM   Backend   AuditLog
   │        │           │             │                │                  │         │     │       │         │
   ├ run_flow(name, inputs) ─────────►│                │                  │         │     │       │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ authenticate(api_key) ─►│                │                  │         │     │       │         │
   │        │◄──── User ────────────┤             │                  │         │     │       │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ authorize(user, run_flow, "flow:name") ─►│                  │         │     │       │         │
   │        │◄─────────── Allow / Deny ───────────────┤                  │         │     │       │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ resolve_memory_config(user, role) ──────►│                  │         │     │       │         │
   │        │◄──── ResolvedConfig ───────────────────┤                  │         │     │       │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ PersonalMemory(backend, mode) を生成 ───────────────────────►│         │     │       │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ flow.run(inputs) ──────────────────────────────────────────►│         │     │       │         │
   │        │           │             │                │                  │         ├ LLM.complete() ►│     │
   │        │           │             │                │                  │         │◄────────────────│      │
   │        │           │             │                │                  │         │     │       │         │
   │        │◄────────────────── 最終出力 ─────────────────────────────────┤         │     │       │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ if mode==accumulate: pm.record_episode() ──────────────────►│         │     │       │         │
   │        │           │             │                │                  ├ backend.add() ─►│      │         │
   │        │           │             │                │                  │         │     │       │         │
   │        ├ audit.write("flow.run", success=True) ──────────────────────────────────────────────────────►│
   │ FlowResult         │             │                │                  │         │     │       │         │
   │◄───────┤           │             │                │                  │         │     │       │         │
```

### 3.2 HTTP: `praxia serve` 経由の同フロー

```
Client       FastAPI app         Auth          (以降は SDK と同一)
  │             │                 │
  ├ POST /api/v1/flows/{name}     │
  │   X-API-Key: ... ───────────►│
  │             │                 │
  │             ├ Depends(current_user) ──►│
  │             │◄───── User ──────────────│
  │             │                 │
  │             ├ Praxia.run_flow(name, inputs) ──── (上記)
  │             │                 │
  │ ◄ FlowResult JSON ─┤          │
```

### 3.3 ユーザ委譲 OAuth

```
User    CLI/UI    OAuthFlow    Provider    OAuthTokenStore    Connector
  │       │           │            │              │                │
  │       ├ oauth start box --user-id alice
  │       │           │            │              │                │
  │       ├ flow.authorization_url(user="alice") ►│              │
  │       │           ├ state + PKCE 込み URL 構築 ───────────────│
  │       │ URL,state │            │              │                │
  │       │◄──────────┤            │              │                │
  │       │           │            │              │                │
  ├──────►│ URL を開く │            │              │                │
  │       │           │            │              │                │
  │       │           │ ◄ login + 同意 ───────────┤                │
  │       │           │            │              │                │
  │       │           │ ◄ code 付き redirect ─────┤                │
  │       │           │            │              │                │
  │       ├ flow.exchange_code(code, state) ─────►│                │
  │       │           ├ POST token_url ──────────►│                │
  │       │           │ access_token, refresh_token                │
  │       │           │◄───────────┤              │                │
  │       │           │            │              │                │
  │       │           ├ store.save(token) ────────────────────────►│
  │       │           │            │              │ 暗号化 + 書込み│
  │       │           │            │              │ → .praxia/oauth/alice/box.json
  │       │           │            │              │                │
  │ ────► │ 後で Box から pull                                       │
  │       │           │            │              │                │
  │       │ Connector(user_id="alice") ─── oauth_token_for(...) ──►│
  │       │           │            │              │ load + 復号    │
  │       │           │            │              ├───────────────►│
  │       │           │            │              │ token 利用     │
  │       │           │            │              │ ◄ Box API ────►│
```

---

## 4. 並行モデル

| コンポーネント | モデル | 理由 |
|---|---|---|
| `LLM.complete` | 同期 / blocking | LiteLLM の中身が I/O バウンド |
| `LLM.acomplete` | スレッドベース async (`asyncio.to_thread`) | blocking 呼出を尊重しつつ最小実装 |
| `CompositeBackend.search` | `ThreadPoolExecutor` (既定 `max_workers=6`) | N バックエンドの I/O バウンド処理 — スレッドで十分 |
| `Flow.run` | 各ステップ逐次 | ステップが前段出力を参照 |
| `OAuthTokenStore` | per-file flock でスレッドセーフ | 複数 CLI / サーバプロセスから安全に書込 |
| `AuditLog` | 書込毎 fsync | クラッシュ安全性を最低オーバヘッドで |
| `JsonBackend` | 単純 lock (v1 では粗粒度) | プロファイル次第で per-user file + shard lock へ |

---

## 5. データ永続化レイアウト

```
.praxia/
├── config.toml                   # praxia config set ...
├── auth/
│   ├── users/                    # User レコード (api_key_hash, role, ...)
│   ├── audit/audit.jsonl         # 追記専用監査ログ
│   ├── policies.json             # リソース ACL
│   └── BOOTSTRAP_API_KEY.txt     # 初期 admin キー (1 回だけ表示)
├── admin/
│   └── memory_policy.json        # MemoryAdminPolicy
├── users/
│   └── <user_id>/
│       └── memory_pref.json      # MemoryUserPreference
├── personal/                     # JsonBackend ストレージ (backend=json 時)
│   └── <user_id>.jsonl
├── shared/                       # SharedMemory (組織共通)
│   └── <org_id>/blocks.json
├── frozen/                       # Layer-4 Markdown
│   └── instructions/
├── oauth/                        # ユーザ毎暗号化トークン
│   └── <user_id>/
│       └── <provider>.json       # 暗号化された blob
└── prompts/
    ├── personal/<user_id>.json
    ├── org.json
    └── distributed.json
```

バックアップ: `.praxia/` 全体をアトミックにコピー。全ファイルが追記専用かアトミック書換。

---

## 6. エラーハンドリング

### 6.1 例外階層

```
Exception
├── MissingDependencyError(ImportError)   — connector/parser/backend で SDK 未 install
├── ImportError                           — Python レベルの import 失敗
├── KeyError                              — レジストリ未登録
├── ValueError                            — 不正入力
├── PermissionError                       — RBAC / ACL 拒否、OAuth 未認可
└── RuntimeError                          — 内部不変条件違反
```

### 6.2 リトライポリシー

| 失敗 | 再試行 | バックオフ |
|---|---|---|
| LLM API 429 | あり (LiteLLM 担当) | 指数 |
| LLM API 5xx | あり | 指数 |
| LLM API 4xx (429 以外) | なし | — |
| コネクタ通信エラー | なし (呼出側に委ねる) | — |
| メモリバックエンド検索失敗 | なし (composite が無視) | — |

### 6.3 ユーザ向けエラーメッセージ

- `MissingDependencyError`: 解決用 `pip install` コマンドを必ず含む
- CLI の `ValueError`: `rich` で赤色レンダリング、exit 1
- CLI の `PermissionError`: 拒否したポリシー / ロール情報を含む
- HTTP 4xx / 5xx: `{"detail": "..."}` 構造化、スタックトレースは漏らさない

---

## 7. テスト戦略

| 層 | 手段 |
|---|---|
| Unit | `tests/test_smoke.py` — 60 個の hermetic テスト、外部サービス接続なし |
| Mock | メモリテストは stub backend 利用、CI で LLM 呼出なし |
| プラグインテスト | 各レジストリに組込が居ることを assert |
| 統合 | `@pytest.mark.integration` でマーク、`pytest -m integration` で実行 |
| E2E | `docs/testing.md` (TODO) のチェックリスト — UI スクショ、実 OAuth フロー等 |

CI は PR 毎に unit + plugin 層を実行。統合テストは週次で実プロバイダのサンドボックスに対して実行。

---

## 8. パフォーマンス予算 (v1.0)

| 操作 | 予算 | 実測 |
|---|---|---|
| `praxia` import (cold) | < 200 ms | ~80 ms |
| `praxia init` | < 500 ms | ~250 ms |
| `praxia list flows / skills / models / backends` | < 100 ms | ~30 ms |
| `LLM.complete` 単発 (モデルレイテンシ除く) | < 5 ms フレームワーク overhead | ~2 ms |
| 4 バックエンドの `CompositeBackend.search` | 並列最大 + 融合 ~5 ms | バックエンドに依存 |
| ファイルパーサ (1 MB PDF) | < 1 s | ~400 ms |
| HTML エクスポート (10 KB md) | < 50 ms | ~5 ms |
| PPTX エクスポート (10 KB md) | < 200 ms (python-pptx 込) | ~80 ms |

ホットパスはレジストリ (`.list()` 後はキャッシュ) と LLM クライアント (LiteLLM 遅延 import)。

---

## 9. セキュリティ設計

### 9.1 機密情報の保管形態

| 機密 | at-rest 形式 |
|---|---|
| ユーザ API キー | bcrypt ハッシュ (`api_key_hash`) — raw は発行時 1 回のみ表示 |
| ユーザパスワード | 保管なし — SSO のみ |
| JWT 署名鍵 | `PRAXIA_JWT_SECRET` (env / config、ソースコードに置かない) |
| OAuth トークン | 対称暗号化 (`PRAXIA_TOKEN_ENC_KEY` 派生)、ユーザ × プロバイダ毎ファイル |
| LLM プロバイダ鍵 | env / `.env` / config、ログ出力厳禁 |

### 9.2 監査トレイル

`AuditLog.write(actor_id, action, resource=None, success=True, metadata=None)` 呼出元:
- `AuthManager` (login, ロール付与, ユーザ CRUD)
- `PolicyManager` (ポリシー追加 / 削除 / deny)
- `Praxia.run_flow / run_skill` (毎呼出)
- `OAuthFlow.exchange_code` (トークン発行)
- `AdminExporter` (export 自体も自己監査)

形式: `.praxia/auth/audit/audit.jsonl` の追記専用 JSONL。各レコードは `id`, `timestamp`, `actor_id`, `action`, `resource`, `success`, `metadata`。

### 9.3 ACL 評価順

```python
PolicyManager.evaluate(user_id, role, resource_type, resource_id, action) -> Decision
```
1. `resource_type` 一致 ∧ `resource_pattern` (glob) が `resource_id` にマッチ ∧ `actions` に `action` を含むポリシーを抽出
2. プリンシパルフィルタ: `user:<user_id>` または `role:<role>` 一致
3. **deny 優先**: 1 件でも `deny` ありなら Decision(False)
4. `allow` が 1 件以上なら Decision(True)
5. それ以外: `default_decision` (設定可能、既定 `allow`)

---

## 10. 拡張性設計 — `Registry`

```python
class Registry(Generic[T]):
    def __init__(self, *, name: str, entry_point_group: str | None = None) -> None: ...

    def register(self, name: str, cls_or_lazy: type[T] | LazyImport) -> None: ...
    def register_decorator(self, name: str) -> Callable: ...
    def get(self, name: str) -> type[T]: ...                  # 不在で KeyError
    def has(self, name: str) -> bool: ...
    def unregister(self, name: str) -> bool: ...
    def list(self) -> list[str]: ...
    def items(self) -> list[tuple[str, type[T]]]: ...
```

登録ソース (順):
1. **Direct** — import 時に `register("name", cls)`
2. **Lazy** — `register("name", lazy("module:Class"))`、初回 `get()` で解決
3. **Entry-point** — `importlib.metadata.entry_points(group=...)` から `list()` / `get()` 初回呼出時に発見

意義: Praxia の **全プラグインポイントが同一の** `Registry` を使用。カスタムスキル / コネクタ / メモリバックエンド / 出力エクスポータ / OAuth プロバイダはすべて install-and-go の同パターン。

---

## 11. 既知の制約 (v1.0)

| 領域 | 制約 | 回避策 / 計画 |
|---|---|---|
| シングルホスト | 1 プロセス 1 `.praxia/` | HA 化は複数プロセス + NFS / オブジェクトストレージへの移行 (計画) |
| LLM ストリーミング | 公開 API なし | LiteLLM ストリーミングを直接ラップ。一級対応は計画中 |
| 大容量ファイルパーサ | 全文インメモリ | ストリーム mode は計画中 |
| OAuth トークン暗号化 | 対称鍵を env 配置 | KMS ベース化を計画 |
| FastAPI サーバ | 最小エンドポイントのみ | 必要に応じて追加 — プロトコルパターンは文書化済み |
| マルチテナント | 1 プロセス 1 テナント | SaaS 版はロードマップ |

優先順位ロードマップ: [`OSS/_internal/NEXT_ACTIONS.ja.md`](../../OSS/_internal/NEXT_ACTIONS.ja.md) (内部資料)。
