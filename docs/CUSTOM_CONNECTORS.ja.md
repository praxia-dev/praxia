# 独自コネクタ開発ガイド

> 🇬🇧 English: [CUSTOM_CONNECTORS.md](CUSTOM_CONNECTORS.md)

Praxia は Box / SharePoint・OneDrive / Dropbox / Google Drive / kintone / Salesforce 用のコネクタを同梱しています。連携したい先がこの一覧にない場合は、`Connector` プロトコルに従う Python クラスを 1 つ書けば、Praxia 側のレジストリ・OAuth・ACL・監査ログは全自動で接続されます。

このガイドは動作する例を交えて手順を一通り示します。

---

## 1. インターフェース契約

すべてのコネクタは 2 つのメソッドを実装します:

```python
class Connector(Protocol):
    name: str

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        """`path` (フォルダ ID / クエリ / テーブル名等) からアイテムを読む。"""

    def push(self, path: str, data: ConnectorItem | dict) -> dict:
        """`path` に `data` を書く。プロバイダ固有の receipt を返す。"""
```

`ConnectorItem` は最小データクラス:

```python
@dataclass
class ConnectorItem:
    id: str
    name: str
    content: str | bytes
    mime_type: str = "text/plain"
    metadata: dict[str, Any] = field(default_factory=dict)
```

これを read / write できれば何でも有効なコネクタです。

---

## 2. 例: Notion コネクタの実装

「Notion を使っているのでフロー入力 (`pull`) とスキル出力 (`push`) を Notion につなぎたい」と仮定。

### 2.1 プロジェクト構成

Praxia 本体に内蔵する方法と、別パッケージとして公開する方法があります。**別パッケージ推奨** — 独立して更新・配布できます。

```
praxia-connector-notion/
├── pyproject.toml
└── src/
    └── praxia_connector_notion/
        ├── __init__.py
        └── notion_connector.py
```

### 2.2 最小実装

```python
# src/praxia_connector_notion/notion_connector.py
from __future__ import annotations

from typing import Any

from praxia.connectors.base import (
    Connector,           # Protocol — 型ヒント用
    ConnectorItem,
    MissingDependencyError,
    _require,
)


class NotionConnector:
    name = "notion"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        user_id: str | None = None,
    ) -> None:
        # 1) SDK の import は遅延 — notion-client 未インストールでも
        #    パッケージ自体は import できるようにする
        notion_client = _require("notion_client", "pip install notion-client")

        # 2) ユーザ委譲 OAuth 経路: user_id 指定で api_key 未指定なら、
        #    暗号化トークンストアから取得する。Box / Google などと同一の
        #    保存形式
        if user_id and not api_key:
            from praxia.connectors.oauth import oauth_token_for
            tok = oauth_token_for(user_id, "notion")
            api_key = tok.access_token

        if not api_key:
            raise ValueError(
                "api_key か user_id (保存済みトークン) を指定してください"
            )

        self._client = notion_client.Client(auth=api_key)

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        """`path` は Notion データベース ID。"""
        results = self._client.databases.query(database_id=path, page_size=limit)
        out: list[ConnectorItem] = []
        for page in results.get("results", []):
            title = self._extract_title(page)
            content = self._page_to_markdown(page)
            out.append(
                ConnectorItem(
                    id=page["id"],
                    name=title,
                    content=content,
                    mime_type="text/markdown",
                    metadata={"notion_url": page.get("url"), "kind": "database_row"},
                )
            )
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        """`path` は親ページ / DB ID。"""
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        result = self._client.pages.create(
            parent={"page_id": path},
            properties={"title": [{"text": {"content": data.name}}]},
            children=self._markdown_to_blocks(str(data.content)),
        )
        return {"id": result["id"], "url": result.get("url")}

    # --- ヘルパー (実装は別途) ---------------------------------------------

    @staticmethod
    def _extract_title(page: dict) -> str: ...
    @staticmethod
    def _page_to_markdown(page: dict) -> str: ...
    @staticmethod
    def _markdown_to_blocks(md: str) -> list[dict]: ...
```

コア部分はおおむね **50 行程度**。残りは Notion API ↔ Markdown 変換の実装ボリュームです。

### 2.3 entry-point で登録 (Praxia 本体への変更ゼロ)

```toml
# pyproject.toml
[project]
name = "praxia-connector-notion"
version = "0.1.0"
dependencies = [
    "praxia>=1.0",
    "notion-client>=2.0",
]

[project.entry-points."praxia.connectors"]
notion = "praxia_connector_notion.notion_connector:NotionConnector"
```

`pip install praxia-connector-notion` (or `pip install -e .` で開発) すると Praxia が自動検出:

```bash
praxia connector list
# → notion が box / dropbox 等と並んで表示される
```

```python
from praxia.connectors import get_connector
notion = get_connector("notion", user_id="alice")
items = notion.pull("a1b2c3...notion-db-id...", limit=20)
```

### 2.4 ユーザ委譲 OAuth の組み込み (任意・推奨)

OAuth 2.0 対応サービスの場合、プロバイダ設定を登録すれば authorize → callback → 暗号化トークン保存の流れが自動化されます:

```python
# src/praxia_connector_notion/oauth.py
from praxia.connectors.oauth import OAuthProviderConfig

NOTION_OAUTH = OAuthProviderConfig(
    name="notion",
    authorize_url="https://api.notion.com/v1/oauth/authorize",
    token_url="https://api.notion.com/v1/oauth/token",
    default_scopes=[],         # Notion はスコープレス
    response_type="code",
    auth_method="basic",       # client_id:client_secret を HTTP Basic で
)
```

登録を公開:

```python
# src/praxia_connector_notion/__init__.py
from praxia.connectors.oauth import register_provider
from praxia_connector_notion.oauth import NOTION_OAUTH

register_provider(NOTION_OAUTH)
```

`pyproject.toml` 追記:

```toml
[project.entry-points."praxia.oauth_providers"]
notion = "praxia_connector_notion:NOTION_OAUTH"
```

これでユーザは:

```bash
praxia oauth start notion --user-id alice
# https://api.notion.com/v1/oauth/authorize?... が開く → ユーザ認可 →
# トークンが暗号化されて .praxia/oauth/alice/notion.json に保存
```

`NotionConnector(..., user_id="alice")` が呼ばれると保存済みトークンが自動でロード。`refresh_token` を返すプロバイダなら更新も自動。

---

## 3. ACL と監査ログとの統合

コネクタ自身は ACL を意識する必要なし — Praxia の `PolicyManager` が `connector:<name>:<path>` リソースを pull / push の前に評価します。協力するべき点:

1. **安定的かつ予測可能なリソース ID** を使う。`box:0/Confidential/q3.pdf` は OK、`box:abcd1234random` は管理者がポリシー書きにくい。
2. `Praxia.run_flow()` 経由なら **監査ログは自動記録**。直接 `connector.pull()` を叩く場合は明示記録:

```python
from praxia.auth import AuthManager
auth = AuthManager()
auth.audit.write(
    actor_id="alice",
    action="connector.pull",
    resource=f"notion:{path}",
    success=True,
    metadata={"item_count": len(items)},
)
```

---

## 4. エラーハンドリング — 何を raise すべきか

| 状況 | 投げる例外 | 理由 |
|---|---|---|
| SDK 未インストール | `MissingDependencyError` (`_require()` 利用) | クリーンな install ヒント |
| 認証情報不足 | `ValueError` + 明示メッセージ | CLI/UI 側で 400 として扱える |
| 外部 API のレート制限 | 標準例外をそのまま | オーケストレータが再試行可能 |
| 不正入力 (空 path 等) | `ValueError` | ユーザエラーとインフラエラーの区別 |
| プロバイダ側の権限拒否 | `PermissionError` | server モジュールが HTTP 403 にマップ |

---

## 5. テスト手法

`tests/test_smoke.py` のパターン:

```python
def test_notion_connector_missing_dep_raises_clear_error():
    """notion-client 未インストール時はメッセージで対処方法が分かる。"""
    from praxia_connector_notion.notion_connector import NotionConnector
    from praxia.connectors.base import MissingDependencyError

    try:
        NotionConnector(api_key="dummy")
    except (MissingDependencyError, ImportError) as e:
        assert "notion-client" in str(e).lower()
```

実プロバイダ統合テスト:

1. サンドボックス / テストワークスペースを使用
2. 認証情報は `~/.praxia-test-secrets.env` (絶対 commit しない)
3. `@pytest.mark.integration` で CI 既定スキップに

---

## 6. 公開前チェックリスト

PyPI 公開前に:

- [ ] `pyproject.toml` の `name` が `praxia-connector-<service>` 命名規則
- [ ] entry-point を `[project.entry-points."praxia.connectors"]` で宣言
- [ ] ライセンスが Apache 2.0 互換 (MIT / BSD / Apache)
- [ ] `pull()` / `push()` 両方実装 (read-only なら `raise NotImplementedError("read-only connector")` で OK)
- [ ] ユーザ委譲 OAuth 経路あり、**または** README で service-account 認証が必要な理由を記述
- [ ] SDK 不在パスのユニットテスト
- [ ] README が本ガイドへリンク + `pull()` / `push()` の `path` セマンティクスを文書化
- [ ] git でバージョンタグ済み

[praxia.dev/plugins] への掲載手順:
1. GitHub リポジトリに `praxia-connector` トピックを付与
2. Praxia 本体への PR で `docs/PLUGINS.md` に追加

---

## 7. パターン概要

| ステップ | あなたが書く | Praxia が提供 |
|---|---|---|
| 1 | `name`/`pull()`/`push()` を持つクラス | Connector プロトコル + `ConnectorItem` |
| 2 | `__init__` で `_require(...)` | Install ヒント自動 |
| 3 | 任意: `OAuthProviderConfig` | 暗号化トークンストア + 自動更新 |
| 4 | `pyproject.toml` の entry-point | 自動検出 (本体改変不要) |
| 5 | ユニット/統合テスト | 上記パターン |
| 6 | PyPI から `pip install` | レジストリ・ACL・監査ログ自動接続 |

同パターンは Praxia の **全プラグインポイント** に適用 — コネクタ / メモリバックエンド / ファイルパーサ / 出力エクスポータ / OAuth プロバイダ / スキル / フロー。共通プリミティブは `praxia.extensions.Registry`。詳細は [PLUGINS.md](PLUGINS.md)。
