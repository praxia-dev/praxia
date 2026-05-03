# Quickstart

## 1. インストール

```bash
pip install agentloom            # コア (CLI + JSON memory + 6 skills + 3 flows)
pip install "agentloom[ui]"      # + Streamlit UI
pip install "agentloom[all]"     # 全部入り (Mem0 / Graph / dev tools)
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
agentloom run sales --model qwen-local --customer-name "Acme"
```

## 3. 初期化

```bash
agentloom init --user-id alice --backend json --model auto
```

## 4. フロー実行 (CLI)

```bash
# 営業準備
agentloom run sales --customer-name "Acme Corp" --product "BizFlow"

# 論理整合チェック
agentloom run logic --document path/to/report.md

# RAG 最適化 (デモ用 stub retriever)
agentloom run rag --question "AgentLoom はどのライセンスですか?"
```

## 5. 単一スキル実行

```bash
agentloom skill investment "ソニーグループ株の中期投資判断を教えて"
agentloom skill legal "業務委託契約書 template.txt のリスクを教えて"
agentloom skill patent "発電効率を高める新型太陽電池の先行技術調査を実施"
```

## 6. UI 起動

```bash
agentloom ui --port 8501
# → http://localhost:8501 を開く
```

## 7. プログラムから使う

```python
from agentloom import AgentLoom
from agentloom.flows import SalesAgentFlow

loom = AgentLoom(user_id="alice", default_model="claude")
result = loom.run(SalesAgentFlow, inputs={
    "customer_name": "Acme",
    "product": "BizFlow",
})
print(result.final_output)
```

## 8. 個人 → 組織メモリの蒸留

```bash
# まずは dry-run で何が昇格されるか確認
agentloom consolidate --dry-run

# 本番実行
agentloom consolidate --threshold 0.75
```

## 9. リソース一覧

```bash
agentloom list flows      # 利用可能なフロー
agentloom list skills     # 6 業務スキル
agentloom list models     # サポート LLM (エイリアス一覧)
agentloom list backends   # メモリバックエンド
```
