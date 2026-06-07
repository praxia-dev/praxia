# Praxia Desktop — 60-second walkthrough (alpha13)

Target: replace the current youtu.be/o_6NbjJU1AA (alpha8-era) with a
walkthrough that lands the new chat-driven story.

Constraints:
- 60 seconds total
- 1080p, 16:9, soundless OK (subtitles burned in)
- Recorded on Praxia Desktop alpha13 (v0.1.0-13)
- No personally-identifying info on screen

Vibe: brisk, every shot earns its keep, no slow zooms.

---

## Shot list

| # | t (s) | Visual | Voiceover / On-screen text | Notes |
|---|---|---|---|---|
| 1 | 0–3  | Praxia logo + tagline fades up against soft indigo→amber gradient. | TEXT: **Praxia Desktop** / SUBTITLE: *Talk to it. It schedules, batches, and learns.* | Use the same indigo (#1f3a8a) + amber (#f59e0b) as the new default Designer theme — visual continuity with the HP. |
| 2 | 3–8  | Cut to the Praxia Chat tab, user types: <br>「毎週月曜の朝に Documents の変更点を要約して」 | TEXT (top-right callout): *Recurring? It schedules it.* | Real key-press cadence, no fake typing animation. |
| 3 | 8–13 | Agent response renders. Highlight the line: <br>*"スケジュールを作成しました。 cron: 0 9 * * 1 / 次回 2026-06-15 09:00:00"* | TEXT: *Praxia parsed the intent → POSIX cron → next firing.* | Pause briefly on the cron expression — that's the magic moment. |
| 4 | 13–17 | Click into the **Schedules** tab. The new schedule is there at the top. | TEXT: *Visible. Cancellable. Re-fires every week.* | Show the next-run timestamp clearly. |
| 5 | 17–22 | Back to Chat. User types: <br>「これら 8 つの議事録 PDF からアクションアイテムを抽出して」 | TEXT (top-right callout): *List of items? It runs them in parallel.* | Same composer, different intent — shows the LLM does the routing. |
| 6 | 22–28 | Agent response: *"バッチを作成しました。8 件並列実行中 (同時 4)…"* Cut to **Batches** tab — composite progress bar fills up. | TEXT: *8 children · 4 in flight · live progress.* | Capture the count ticker — visual proof of parallelism. |
| 7 | 28–34 | Cut to one child Task expanded — shows the agent's per-PDF result, then back to the Batches tab showing all 8 marked Done. | TEXT: *Each result is auditable.* | This is the "I trust this" moment. |
| 8 | 34–40 | Switch to Chat. User types: <br>「Q3 売上の振り返り資料を作って」 (or: *"draft a Q3 revenue retro deck"*) | TEXT (top-right callout): *Need a deck? It designs one.* | |
| 9 | 40–46 | Pending Ops panel shows the render op with the green **✨ Designer mode** badge. User clicks **Apply**. Saved-to banner pops with the file path. | TEXT: *Designer mode · sandboxed · themable.* | Showcase the Designer badge — that's the chip the alpha12 release added to make routing visible. |
| 10 | 46–52 | Open the saved .pptx in PowerPoint. Flip through 3 slides quickly: title slide (full primary background), bullets slide (colored title bar + accent stripe), chart slide (matplotlib bars). | TEXT: *Real layouts. Real colors. Real charts.* | This kills the "white slides" perception in one shot. |
| 11 | 52–57 | Cut to **Documents** tab. Drag a file into the watched folder externally → after a beat the activity badge flickers `↻ filename.pdf`, count increments. | TEXT: *Auto-re-index on file change. No clicks.* | Demonstrates the auto-watch alpha13 default. |
| 12 | 57–60 | Cut to Praxia logo + CTA. | TEXT: **praxia.dev** / SUBTITLE: *Open source. Apache 2.0. Free download for Windows.* | Light "click" SFX OK on the URL appear. |

---

## Subtitles (multi-language fallback)

Burn EN + JA subtitles in by default since those two cover the bulk
of expected viewers. Other locales: provide YouTube subtitle tracks
as SRT.

### English subtitle track

```
00:00:00,000 --> 00:00:03,000
Praxia Desktop — Talk to it.

00:00:03,000 --> 00:00:08,000
Say "every Monday morning, summarise yesterday's docs"

00:00:08,000 --> 00:00:13,000
and Praxia parses the intent into POSIX cron, instantly.

00:00:13,000 --> 00:00:17,000
The schedule lives in the Schedules tab — cancellable, auditable.

00:00:17,000 --> 00:00:22,000
Have a list? Say "for each of these 8 PDFs, extract action items."

00:00:22,000 --> 00:00:28,000
Praxia fans them out in parallel — concurrency-capped, one batch ID.

00:00:28,000 --> 00:00:34,000
Every child Task is its own auditable record.

00:00:34,000 --> 00:00:40,000
Need a deck? "Draft a Q3 revenue retro."

00:00:40,000 --> 00:00:46,000
Designer mode — the LLM writes python-pptx code in a sandbox.

00:00:46,000 --> 00:00:52,000
Real layouts. Real colors. Real charts. Not bullet soup.

00:00:52,000 --> 00:00:57,000
Drop a file in a watched folder — auto-re-index, no clicks.

00:00:57,000 --> 00:01:00,000
praxia.dev — Open source. Free for Windows.
```

### 日本語字幕

```
00:00:00,000 --> 00:00:03,000
Praxia Desktop — 話しかけるだけ。

00:00:03,000 --> 00:00:08,000
「毎週月曜の朝に Documents の変更を要約して」

00:00:08,000 --> 00:00:13,000
Praxia が即座に POSIX cron に変換します。

00:00:13,000 --> 00:00:17,000
スケジュールタブで確認・停止可能。

00:00:17,000 --> 00:00:22,000
「これら 8 つの PDF からアクションアイテムを抽出して」

00:00:22,000 --> 00:00:28,000
並列実行で一気に。同時実行数は自動制御。

00:00:28,000 --> 00:00:34,000
各子タスクも個別に確認できます。

00:00:34,000 --> 00:00:40,000
「Q3 売上の振り返り資料を作って」

00:00:40,000 --> 00:00:46,000
Designer モード — LLM が python-pptx コードをサンドボックス内で生成。

00:00:46,000 --> 00:00:52,000
本物のレイアウト・色・グラフ。箇条書きだけじゃない。

00:00:52,000 --> 00:00:57,000
監視中のフォルダにファイルを入れる → 自動で再インデックス。

00:00:57,000 --> 00:01:00,000
praxia.dev — オープンソース・Windows 無料。
```

---

## Recording notes

- **Pre-flight**: spin up a fresh Praxia install on a clean Windows
  VM so there's no prior memory clutter. Configure a single LLM
  provider (Claude 4 Sonnet works well — punctual replies, no
  hallucinated tool calls).
- **Reset between takes**: schedule + batch records persist to disk,
  so wipe `%LOCALAPPDATA%\Praxia\` between attempts if a take fails.
- **Window size**: 1440×900, scaled 100% — fits 1080p capture without
  cropping.
- **Avoid**: real API keys visible anywhere (Settings tab is OK because
  the keys are masked). No real PDFs with PII — use the synthetic
  "Q3 retro" example PDFs in `samples/` for the batch demo.
- **Capture tool**: OBS Studio, 60 fps, MP4 H.264. The HP `<video>`
  tag picks up `.webm` first then falls back to `.mp4` — encode both.

## Post-production checklist

- [ ] Burn EN + JA subtitles into the master file
- [ ] Export `.mp4` (H.264, 8 Mbps) and `.webm` (VP9, 6 Mbps)
- [ ] Replace `web-publish/videos/demo-60s.{mp4,webm}` (HP picks these up)
- [ ] Replace `web-publish/images/demo-thumb.png` with a still from
      shot #6 (Batches progress bar — the most visually distinctive moment)
- [ ] Upload to YouTube — same channel as the existing alpha8 video
- [ ] Update `i18n.js` keys `hero.video.full` href + `i18n.js`
      youtube URL: edit the 8 occurrences of `o_6NbjJU1AA` to the new ID
- [ ] Update Linear / memory snapshot of video URL
- [ ] Leave the old video unlisted (not deleted) for 30 days in case
      anything still embeds it

## Why this script is shaped this way

3 shots × 3 use cases = 9 substantive shots; 3 bookend / transition
shots. The pacing puts the most novel thing (chat → cron) first
because that's the alpha13 hook; the deck design lands in the middle
where attention is at the lull point and the visual payoff (colored
slides) is biggest; the auto-watch goes at the end as a "and also"
because it's a smaller delight.

Total runtime budget: 60s. If you go over, cut shot #11 (auto-watch
demo) first — it's the most droppable. Don't cut shot #9-10 (Designer
deck) under any circumstance — that's the alpha12+13 visual story.
