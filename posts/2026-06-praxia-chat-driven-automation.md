# LLM デスクトップを「打つ → 結果」から「話す → 自動化」へ：Praxia v0.1.0-alpha13 の設計メモ

> Apache 2.0 の OSS / Windows デスクトップアプリ Praxia の最新リリース。
> 自然言語のリクエストを cron スケジュール・並列バッチ・テーマ付き
> PowerPoint に「即座に」変換するための実装を解説します。

## はじめに

ChatGPT Desktop も Claude Desktop も「会話 → 一発の応答」が中心です。
「毎週月曜の朝に〇〇を要約して」と頼んでも、その場で要約して終わり。
**翌週、もう一度自分で頼まないと動かない**。

これは、人間に毎週同じ依頼を続けるようなもの。AI デスクトップなら
**「一度言えば再現する」** が自然な体験のはずです。

筆者が開発している [Praxia](https://github.com/praxia-dev/praxia) の
v0.1.0-alpha13 では、この体験を**チャットだけ**で実現しました。本記
事ではその設計と落とし穴を紹介します。

```
ユーザ: 毎週月曜の朝に Documents の変更を要約して。

Praxia: スケジュールを作成しました。
        - cron: 0 9 * * 1
        - 次回実行: 2026-06-15 09:00:00
        - Schedules タブから確認・停止できます。
```

## TL;DR

- agent tool として `schedule_recurring_task(cron, prompt, label)` と
  `run_parallel_tasks(prompts[], label)` を追加
- LLM が「曜日・繰り返し表現」「リスト・各項目」を文脈から検出し
  自動でツール選択
- ストレージは HTTP ラウンドトリップを介さず、router と同じ on-disk
  形式に直接書き込み
- PyInstaller-frozen 環境でも動くようサンドボックスに in-process
  モードを追加
- デフォルトテーマと codegen プロンプトを書き直して「真っ白な PPT」
  問題を解消

## 1. なぜ「チャットから自動登録」が要るのか

最初は素直に **Schedules タブ・Batches タブを独立 UI** として実装し
ました。タブを開いて cron 式と prompt を手入力する設計です。

ところがα版を使ってもらった結果、**ほぼ誰も使わない**。なぜか:

- そもそも cron 式を書ける人が少ない
- 「いつ・何に使うのか」が UI から伝わらない
- タブを開くという 1 ステップが、それだけで `面倒` になる

LLM デスクトップにいる以上、ユーザはすでに**自然言語の世界に居る**
わけです。タブの存在自体がコンテキストスイッチになる。

そこで方針転換：

> タブは「自動登録された結果を眺める場所」に格下げし、
> 登録自体はチャットの agent tool 経由で行う。

## 2. Agent tool として実装する

OpenAI / litellm の function calling 形式で 2 つのツールを追加しま
した（`praxia/agent/tools.py`）。

### 2.1 `schedule_recurring_task`

```python
AgentTool(
    name="schedule_recurring_task",
    description=(
        "Create a recurring scheduled agent run. Call this when the "
        "user expresses a RECURRING intent: 'every weekday at 9am', "
        "'毎週月曜の朝に〜', 'jeden Montag um 8 Uhr'. NOT for one-shot "
        "requests. You are responsible for translating the user's "
        "natural-language schedule into a POSIX 5-field cron expression."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "cron":   {"type": "string"},
            "prompt": {"type": "string"},
            "label":  {"type": "string"},
        },
        "required": ["cron", "prompt"],
    },
    handler=_schedule_recurring_task,
)
```

ポイント:

- **`description` に "WHEN to call" を厚めに書く**。recurring intent
  vs one-shot vs list の三択を LLM に判別させるための文脈。
- 例（"毎週月曜の朝"）を**多言語で 2 つ以上**入れると、各言語の自
  然言語パターンへの汎化が効きます。
- 「cron 変換は LLM の責任」と明記。実装側はバリデーションのみ。

エラーメッセージは LLM が**自己修正できる形**で返します：

```python
return {
    "created": False,
    "error": (
        f"invalid cron {cron!r}: {e}. Expected 5 fields: "
        f"'minute hour day-of-month month day-of-week'. "
        f"Examples: '0 9 * * 1-5' = weekdays 9am; "
        f"'*/30 * * * *' = every 30 min; "
        f"'0 0 1 * *' = first of every month at midnight."
    ),
}
```

これで LLM は次のターンで cron を直して再送できる（実測で 80%
くらいは 1 回のリトライで通る）。

### 2.2 `run_parallel_tasks`

```python
AgentTool(
    name="run_parallel_tasks",
    description=(
        "Fan out N agent runs in parallel, one per prompt. Call this "
        "when the user has a LIST of items that all need the same "
        "treatment: 'summarise each of these 5 files', 'classify these "
        "20 support tickets', 'これらの 10 件をそれぞれ要約して'."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "prompts": {"type": "array", "items": {"type": "string"}},
            "label":   {"type": "string"},
            "max_concurrency": {
                "type": "integer", "default": 4, "minimum": 1, "maximum": 16,
            },
        },
        "required": ["prompts"],
    },
    handler=_run_parallel_tasks,
)
```

LLM はリストアイテム展開を自分でやって、各項目の prompt を組み立
てます。これが地味に強力で、ユーザは

```
ユーザ: ./contracts/ にある PDF 全部から「解約条項」を抽出して。
```

と頼むだけ。LLM は内部で:

1. `list_document_folders` で folder を見つけ、
2. `search_documents(path_prefix="contracts")` で対象ファイル一覧を取り、
3. `run_parallel_tasks(prompts=["契約 A の解約条項を抽出して", "契
   約 B の解約条項を…", …])` で並列実行

を組み立てます。これを 1 ターンで通す体験は、ChatGPT Desktop /
Claude Desktop だと **やりたくてもできない**。

## 3. ストレージは HTTP を介さず直書き

agent tool は OSS サーバの内部で動いています。素直に書くと、
schedules を作成するために自分の HTTP ハンドラを呼び出すことに
なりますが、それは:

- HTTP ラウンドトリップで認証ヘッダを偽造することになる
- async/sync の橋渡しが面倒

ので、**router が読む on-disk JSON 形式に直接書き込み**します:

```python
def _schedule_recurring_task(agent, cron, prompt, label=None):
    from praxia.server.routers.schedules import (
        ScheduleRecord, _save as _save_sched, next_run, parse_cron,
    )
    parse_cron(cron)  # validate, raises on bad input
    rec = ScheduleRecord(
        id=uuid.uuid4().hex,
        user_id=str(agent.user_id),
        cron=cron,
        prompt=prompt,
        ...
    )
    rec.next_run_at = next_run(cron, datetime.now()).timestamp()
    _save_sched(Path(agent.memory_dir), rec)
    return {...}
```

`_save_sched()` は同じ tmp+`os.replace` パターンで原子的に書き込
むので、HTTP 経由でも tool 経由でも整合性は同じ。

このおかげで:

- agent tool は同期 / 軽量、LLM のターン内で完結
- 1 分ごとの cron ticker（独立スレッド）が次のスキャンで自動的に
  拾う
- UI 側は何も変える必要がない（既存の `/schedules` リスト API を
  そのまま使える）

## 4. PyInstaller-frozen 環境とサンドボックス

Praxia は Tauri + PyInstaller でデスクトップアプリにバンドルします
が、ここで Document Designer Skill が動きませんでした。

理由は `subprocess.run([sys.executable, runner_path])` の `sys.executable`。
PyInstaller-frozen バンドルでは **これがバンドル exe 自身**を指し
ます。サブプロセスとして起動すると、サーバ起動エントリポイントが
**再び走る**だけで、生成された python-pptx コードは実行されません。

解決：サンドボックスに **in-process モード**を追加して、AST validator
は維持したまま `exec()` で実行します。

```python
def _is_frozen() -> bool:
    return getattr(sys, "frozen", False) is True

def run_in_sandbox(code, *, timeout_s=30.0, force_in_process=None, ...):
    if not skip_validate:
        validate_code(code)
    use_in_process = (
        force_in_process if force_in_process is not None else _is_frozen()
    )
    if use_in_process:
        return _run_in_process(code, timeout_s=timeout_s)
    # ... 通常の subprocess 経路
```

`_run_in_process()` 側では:

- 制限された builtins（`open` / `range` / 例外クラスなど最小限）
- `_emit(bytes)` ヘルパを namespace に注入
- `redirect_stdout` で出力をキャプチャ

サブプロセス分離はなくなりますが、信頼境界が「ユーザ自身の LLM」
である desktop sidecar では妥当な妥協です。AST validator は同じ
allowlist を通すので、`import os` / `eval()` 等は依然弾かれます。

## 5. 「真っ白な PowerPoint」の正体

α12 をユーザに渡したところ、

> 「Designer 経由のはずなのに、出力は真っ白の PowerPoint」

というフィードバック。デバッグしてみると、犯人は **デフォルト
テーマ自身**でした：

```python
# 旧
"primary":    "#1f2937",  # dark slate
"background": "#ffffff",  # WHITE!
```

LLM はテーマブロックを忠実に解釈し、

```python
slide.background.fill.solid()
slide.background.fill.fore_color.rgb = RGBColor(0xff, 0xff, 0xff)  # 白
```

としていました。「テーマに白って書いてあるんだもん…」と。

直し方は 2 つ:

**(a) デフォルト配色を変える**

```python
"primary":    "#1f3a8a",  # indigo-900
"accent":     "#f59e0b",  # amber-500
"background": "#f8fafc",  # slate-50 (薄い off-white)
```

**(b) プロンプトに「色を必ず使え」と書き、実コード例を見せる**

```
MANDATORY styling rules (a plain white deck is a FAIL):

  1. EVERY slide MUST have a colored title bar at the top using the
     primary color.
  2. EVERY slide gets a thin colored accent line using the accent color.
  3. Body text uses the `text` color on the `background` color.
  ...

Concrete styling snippet you should reuse:

    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0,
                                 Inches(13.33), Inches(1.0))
    bar.fill.solid()
    bar.fill.fore_color.rgb = PRIMARY
    ...
```

few-shot をコードレベルで見せると、LLM は**ほぼ確実にコピペ**して
スタイルを適用してくれます。ここは Anthropic Skills 設計の経験則
通り。

## 6. Documents の自動監視

最後にもうひとつ。Documents タブには「フォルダを Watch する」トグ
ルがありましたが、毎回手動で ON にするのが面倒でした。

解決はシンプル：**`localStorage` に "off" の場合だけ印を付ける**。
初期状態 = ON、明示的にユーザが Stop を押した時だけ `off=1` を保存。

```typescript
onMount(async () => {
  await refresh();
  for (const f of folders) {
    if (localStorage.getItem(`praxia.watch.${f.id}.off`) === "1") continue;
    await invoke("start_folder_watch", { folderId: f.id, path: f.path });
  }
});
```

「ON が初期値」と決めると、新規追加フォルダも何もせず watch 対象
に入る。地味ですが体感は大きく変わります。

## まとめ

- LLM デスクトップの UX は**「タブを増やす」よりも「会話だけで完結
  させる」** ほうがスケールする
- agent tool の `description` に "WHEN" を厚く書くだけで、ルーティ
  ングは LLM 任せにできる
- HTTP ラウンドトリップを避けて on-disk フォーマット直書きすると、
  ツールも UI も同じ整合性を保てる
- PyInstaller-frozen 環境のサンドボックスは AST validator + exec()
  で十分実用的
- LLM はテーマを忠実に解釈するので、デフォルト配色こそが UX を決
  める

## 試してみる

```
https://praxia.dev
↓
Praxia Desktop (.exe, 165 MB) を Windows にインストール
↓
お好みの LLM API キー (Claude / OpenAI / Gemini / etc.) を入力
↓
Chat タブで「毎週月曜の朝に〇〇」と話しかける
```

OSS の Apache 2.0 サーバは [github.com/praxia-dev/praxia](https://github.com/praxia-dev/praxia)
にあります。Windows 以外で動かしたい場合は `pip install praxia` で
SDK / CLI / Streamlit UI が手に入ります。

フィードバックはコメント欄 or GitHub Issues へ。
