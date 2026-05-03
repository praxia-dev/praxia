# Quickstart

## 1. インストール

```bash
pip install praxia            # コア (CLI + JSON memory + 6 skills + 3 flows)
pip install "praxia[ui]"      # + Streamlit UI
pip install "praxia[all]"     # 全部入り (Mem0 / Graph / dev tools)
```

## 2. API キー設定

`.env.example` をコピー:

```bash
cp .env.example .env
```

少なくとも 1 プロバイダのキーを設定:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
# OR
OPENAI_API_KEY=sk-...
# OR
GEMINI_API_KEY=...
# OR
DASHSCOPE_API_KEY=...
```

ローカル Qwen を使いたい場合:

```bash
# Ollama を別途インストール後
ollama pull qwen2.5:14b
praxia run sales --model qwen-local --customer-name "Acme"
```

## 3. 初期化

```bash
praxia init --user-id alice --backend json --model auto
```

## 4. フロー実行 (CLI)

```bash
# 営業準備
praxia run sales --customer-name "Acme Corp" --product "BizFlow"

# 論理整合チェック
praxia run logic --document path/to/report.md

# RAG 最適化 (デモ用 stub retriever)
praxia run rag --question "Praxia はどのライセンスですか?"
```

## 5. 単一スキル実行

```bash
praxia skill investment "ソニーグループ株の中期投資判断を教えて"
praxia skill legal "業務委託契約書 template.txt のリスクを教えて"
praxia skill patent "発電効率を高める新型太陽電池の先行技術調査を実施"
```

## 6. UI 起動

```bash
praxia ui --port 8501
# → http://localhost:8501 を開く
```

## 7. プログラムから使う

```python
from praxia import Praxia
from praxia.flows import SalesAgentFlow

loom = Praxia(user_id="alice", default_model="claude")
result = loom.run(SalesAgentFlow, inputs={
    "customer_name": "Acme",
    "product": "BizFlow",
})
print(result.final_output)
```

## 8. 個人 → 組織メモリの蒸留

```bash
# まずは dry-run で何が昇格されるか確認
praxia consolidate --dry-run

# 本番実行
praxia consolidate --threshold 0.75
```

## 9. リソース一覧

```bash
praxia list flows      # 利用可能なフロー
praxia list skills     # 6 業務スキル
praxia list models     # サポート LLM (エイリアス一覧)
praxia list backends   # メモリバックエンド
```
