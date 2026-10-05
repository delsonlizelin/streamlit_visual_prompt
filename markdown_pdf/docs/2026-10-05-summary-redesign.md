# Summary page redesign: audit and plan (2026-10-05)

Architecture audit written by a Fable 5.1 review agent, based on the code, the tests and summary experiments on a 24.5-minute video transcript. Paths are relative to `markdown_pdf/`.

**Status (2026-10-05): Phases 1 and 2 implemented.** Decisions: YouTube is local-only (hidden on Streamlit Cloud; no new Cloud dependency), generation defaults to Auto, and non-Chinese transcripts default to Simplified Chinese. The other open questions took the recommended defaults.

## 0. Headline verdicts

- **The failure comes from the mode's rules, not the effort level.** Three rules in the "standard" mode define "conclusion" as an argument's thesis and push situational context out:
  - the lead may contain no numbers;
  - "不从背景开始" (don't start from background);
  - the deletion test is tuned to arguments.

  Evidence: `expB`, run without reasoning and with one narrative instruction, already got the right structure. `expA`, run with reasoning at high effort in standard mode, still produced an empty lead and put the dispute's trigger in section 2.
- **More effort does not make the summary more faithful.** In the test transcript one party is accused of taking chips. `story_none` and `story_high` attributed this correctly; `expB` and `story_max` attributed it to the other party. `story_max` also stated a figure the speaker hedged as fact. The best run overall was `story_high`.
- **The number check raised only false alarms on transcripts.** For example, it flags "2016年" vs "2016" and "18000美元" vs "$18,000". The `--revise` pass then feeds these bogus warnings back to the model.
- **"Low effort failed" is a bug in how the token ceiling is sized.** `max_tokens` is a shared ceiling that only costs anything if it's hit. Tying it to effort guarantees truncation on long inputs, and a truncated call is thrown away after it's been paid for.
- **The input code has no place for a YouTube path.** There are three separate input paths, each returning a different result shape, and no way to tell the prompt facts about the material (whether it's a transcript, from speech recognition, has speaker labels, what language). YouTube should be added as a fourth parallel source.

## 1. Audit (ranked)

**P1. Standard mode suppresses situational context.** (Prompt and mode design; confirmed.)
- `deepseek.py:37–40`: the standard mode's lead rules and "不从背景…开始".
- `:247`: "lead 不放具体数字".
- `:193–194`: background only when strictly necessary.
- `:216`: rule 7 makes the lead null when there's no strong conclusion.
- `:117–118`: the length ranking puts background last.
- `:257`: the deletion test.
- Rule 3 of the expression rules (`:225`) already asks for the needed context, but the background prohibition overrides it.
- The uncommitted story-mode diff contradicts rule 7.

**P2. Attribution is unstable on spoken, pronoun-heavy material.**
- No local check can catch "who accused whom" errors.
- The fix needs three parts: a prompt rule for resolving pronouns, an opt-in check that verifies attribution, and an evaluation fixture to measure it.
- For transcripts, the byline must come from metadata (the channel name), never from the spoken outro.

**P3. The number check (`quality.py`) gives false alarms across languages and units.**
- The unit sits inside the matched token, so 万, currency symbols and 年 all break matches.
- The revision prompt then tells the model to "restore" English spellings inside a Chinese summary.

**P4. Reasoning-token ceiling policy** (`deepseek.py:22–25`, `:766–769`).
- A per-effort allowance is the wrong design. Observed reasoning on this input: low used more than 11k tokens, high about 14k, max about 26k.
- An error string in the library hard-codes a UI label.
- The request fingerprint omits `reasoning_effort`.

**P5. The input layer has three result shapes and no way to pass material facts to the prompt.**
- Pasting a YouTube URL is routed to HTML extraction, which fails with "网页正文太短" (text too short).
- The CLI doubles the H1 heading for URL sources.
- Hand-written transcript headings get copied into the summary's structure.

**P6. The app and the CLI resolve the model differently.** The page ignores `DEEPSEEK_MODEL` and the CLI honours it. A single settings resolver should replace both.

**P7. Transport and error handling.**
- A dropped connection is retried by re-sending the whole request, so the user pays twice.
- The stream parser silently ignores an error chunk.
- The timeout only limits each read, not the total time.
- The UI shows no progress during 75–120 s of reasoning.

**P8. UX on the summary page.**
- Story mode isn't offered: `mode_order` is hard-coded.
- The model labels "非思考 / High" describe the implementation, not the purpose.
- The URL placeholder only mentions WeChat.
- There's no metadata caption for transcripts.
- A long lead renders as a heavy semi-bold block.
- The lead's maximum length (360) is too small for an English story lead.

**P9. Tests.** Nothing tests story mode, effort, stream decoding, retries or the number check across languages. There is no set of fixtures covering different material types.

**P10. The prompt is long and repetitive.** It's about 5,000 characters, mostly prohibitions, and the deletion-test, budget and lead rules are each stated twice. Consolidate before adding anything.

**P11. The docs are out of date.** Both README and SKILL.md need updating, and ROADMAP needs a 5-item evaluation set now.

## 2. Material type and mode design

**Separate two things that are currently mixed together:**
- **Material profile: facts about the source.** It comes from the source layer, not from the user, though the user can override it. It's passed to the model as `task_config.material`:

  ```
  {kind: article|document|transcript, origin: wechat|web|youtube|bilibili|upload|paste,
   language, asr, speakers_labelled, duration_seconds, has_chapters}
  ```

  This replaces the growing list of genres in the prompt.
- **Summary mode: the reader's purpose.** Three options, named by purpose:
  - 先看结论 (conclusion first)
  - 来龙去脉 (how it unfolded)
  - 按章节梳理 (section by section)

  Don't add separate interview or podcast modes; the material profile covers them. Don't auto-detect the mode. Show a hint when the material is a transcript.

**Output format:** keep `title/byline/lead/sections/items`. Raise the lead's maximum length for story mode to 600. Postpone a separate `context` field to Phase 3. Lighten the CSS weight for long leads.

**Prompt changes (replacements, not additions):**

- **a) Standard-mode lead.** Replace the lead rules and "不从背景开始" with:
  > 导语与首条分工：lead 用一两句说清全文判断及必要的不确定性，统计数字、样本量和证据来源留给条目。但若原文的核心是一件事（事件、纠纷、调查、人物经历），‘结论’就是局面本身：lead 应直接说清谁与谁、因何而起、现在到哪一步，界定局面的人名、金额和日期可以出现。不从文章目录或作者的写作动作开始；背景只在它界定结论或局面时进入摘要，并放在读者第一次需要它的位置，而不是末尾。

  Also remove the duplicated deletion test from the mode text.
- **b) Rule 2 ending:** "…才进入摘要；需要的背景放在读者第一次需要它的位置。"
- **c) Rule 3 addition:** "事件、纠纷与调查类材料优先交代当事各方及其关系、起因、升级与当前状态；界定局面的背景在这类材料里就是核心信息。"
- **d) Rule 7:** "…没有足够强的全文结论、也没有需要交代的局面时，将 lead 设为 null。"
- **e) New input-permissions item 4 (the material rule):**
  > task_config.material 说明材料类型与来源。转写稿通常没有说话人标注，并含识别错误、口头禅、重复和片头片尾招呼：先按上下文确定每个代词和每句话的主语，再写‘谁指控谁、谁说了什么’；无法确定时写明原文指代不清，不得猜测。署名使用来源元数据中的频道或讲者名，不从口播内容推断；片尾招呼、口误和无法辨认的外语片段不得用作署名、人名或事实。
- **f) Output rule 3:** a generic sentence about the lead; the specific requirements come from `task_config`.
- **g) Closing check:** "…不影响读者理解主结论或局面、依据或边界时就删除。"
- **h) Story mode:**
  - "通常 3 到 4 个分区";
  - every item names its subject;
  - follow the order events happened, not the order the source tells them;
  - keep attribution for speculation and allegations.
- **i) Labels by purpose:** 先看结论 / 来龙去脉 / 按章节梳理. Move "recommended" from the label into the caption.

The net prompt size stays about the same.

## 3. Input architecture: one source layer

**`sources.py`** defines the shared types and one entry point per input path:

```python
Material(kind, origin, language, asr, speakers_labelled, duration_seconds, has_chapters)
SourceDocument(text, title, output_name, material, characters, url, site, pages, text_pages, notices)
SourceError(code, hint)
classify_url(value) -> "youtube" | "bilibili" | "web"
load_text(text) / load_upload(filename, data) / load_url(value, *, timeout, youtube)
material_task_config(material); detect_language(text); looks_like_transcript(text)
```

It wraps the existing extractors. `build_messages` takes `material`, and the fingerprint includes it.

**`youtube_documents.py`** handles YouTube:
- `extract_video_id`, `fetch_video_metadata` (public oEmbed, no API key), `fetch_youtube_transcript`, `transcript_to_markdown`.
- The text it produces is an H1 title, one metadata line, then paragraphs of about 45–60 s, each starting with its `[mm:ss]` timestamp. It invents no headings; the author's own chapters become `##` headings.

**Error messages:** each failure gets a message and a next step.
- Blocked: "云端 IP 常被拦截 → 粘贴字幕记录，或本机运行" (cloud IPs are often blocked; paste the transcript or run locally).
- No transcript available.
- Video unavailable.
- Library missing: the feature is disabled, never a traceback.

**Dependency:** `youtube-transcript-api==1.2.4`. It's pure Python and imported only when used. It's preferred over yt-dlp, which needs frequent version bumps and is blocked from cloud IPs just the same. An optional `YOUTUBE_PROXY_URL` secret can be added. Keep the existing guard against private and internal URLs.

**Pasted URLs:** a bare URL pasted as text goes through the same `classify_url`/`load_url` path. Pasted text that looks like a transcript is marked as one, and the user can override that.

**Bilibili:** Phase 3, local skill only. The app shows a message pointing to the YouTube original or pasting the text instead.

## 4. Model and reasoning policy

- **Model:** `deepseek-flash` everywhere, through one `resolve_settings()` with an allow-list of model names. Keep V4-Pro out of the UI.
- **UI choices:** 快速 (fast, non-thinking), 仔细 (careful, thinking at high effort), or 自动 (auto, the recommended default).
  - Auto picks 仔细 for 来龙去脉, for transcripts, and for sources longer than about 15k characters.
  - Hide `max` and `low` in the UI; keep them in the CLI.
- **Token ceiling:** one ceiling of output budget plus 48k (clamped to the model's maximum). Rewrite error messages without UI labels.
- **Streaming:**
  - always stream, reading incrementally;
  - a total time limit of 300 s with thinking and 120 s without, plus a 60 s idle limit;
  - turn stream error chunks into a `SummaryError`;
  - an `on_progress` callback for a live status display.
- **Retries:** retry dropped connections only if fewer than about 15 s have passed. Add effort and material to the fingerprint.
- **Cost reference** for a 25k-character source:

  | Setting | Output tokens | Time |
  |---|---|---|
  | No thinking | ~1.2k | 8 s |
  | High | ~15k | 75 s |
  | Max | ~27k | 118 s |

## 5. Front end (summary page)

- **01 Add source:**
  - The input choices are paste text, upload file, and URL; rename 文章网址 to 网址.
  - The URL placeholder shows both a WeChat and a YouTube example.
  - After loading, show a metadata caption, e.g. "已读取 YouTube 字幕 · 频道 · 24 分 26 秒 · 英文自动字幕 · 无说话人标注".
  - Failures show the error plus a hint for what to do next.
- **02 Edit and summarize:**
  - Three summary modes, captioned by purpose.
  - A hint for transcripts, without silently switching the user's choice.
  - Under other settings: material type (detected, can be overridden) and generation mode (自动/快速/仔细).
  - Live progress through `st.status`.
- **03 Results:**
  - A "核对归属" (check who said what) button for story mode and transcripts (Phase 2).
  - A softer number-check warning when the summary language differs from the source's.
  - Generation info shows effort and reasoning tokens.
- No new colours.

## 6. Reuse strategy

- **The project is the single source of truth.** `summarize_cli.py` stays in the repo; the skill only calls it.
- **YouTube fetching lives in the project,** shared by the app, the CLI and the skill.
- **Bilibili and Whisper stay in the skill.** They're local-only tools, and they write a transcript file that the CLI then reads.
- **No package yet.** A `pyproject.toml` with `pip install -e .` can come later.
- **Premature for now:**
  - Bilibili in the app;
  - Whisper in the project;
  - a framework for multiple model providers;
  - splitting long transcripts into chunks;
  - a `context` field.
- **Evaluation inputs:** real transcripts go in a gitignored `evals/` folder; synthetic fixtures go in `tests/fixtures/`.

## 7. Verdict on the uncommitted changes

| Change | Verdict |
|---|---|
| Story mode | **Keep;** revise its wording (h); show it in the UI |
| Rule 3 addition | **Modify** (c) |
| ASR sentence | **Replace** with the material rule (e) |
| Lead exception | **Replace** with (f), and fix rule 7 and the standard-mode lead rule |
| `PROMPT_VERSION` bump | **Keep** |
| `reasoning_effort` setting | **Keep** |
| Per-effort token allowance | **Revert** to one ceiling; add effort to the fingerprint |
| Streaming | **Keep the idea;** make reading incremental, add a deadline, handle error chunks, add a progress callback |
| Retry on dropped connections | **Keep,** with the elapsed-time guard |
| Test change | **Keep;** add the tests listed in section 8 |
| CLI | **Keep;** fix the default effort and the duplicate H1; use `resolve_settings`; route URLs through `sources` |

## 8. Phased plan

**Phase 1: prompt, policy, number check, CLI.** No new dependency and no Cloud rebuild.
- Prompt changes a–i.
- Story mode added to the UI's mode list.
- Lead length cap per mode, and the CSS weight tweak.
- One token ceiling; effort added to the fingerprint.
- The 自动/快速/仔细 control.
- Number check: normalize 万/亿/k/million/billion, strip currency symbols, treat 年 correctly, soften warnings across languages.
- CLI fixes.
- More robust stream decoding.
- Tests for each of the above.
- Evaluation: `evals/manifest.json` with five material types (this transcript, a WeChat opinion piece, a research-report PDF, a tutorial, and an interview transcript), plus an opt-in `scripts/eval_summaries.py` that runs the CLI and writes a CSV of results.
- Yes/no scoring rubric for each summary:
  - after the lead and section 1, a time-poor reader can say in two sentences what happened;
  - each party is identified the first time they appear;
  - the trigger is in the lead or section 1;
  - every accusation names who made it and who it targets;
  - nothing the source hedges is stated as fact;
  - numbers match the source;
  - no transcription artifacts appear in the byline or the facts;
  - it stays within the length budget;
  - in story mode, it doesn't simply copy the source's narration order.

**Phase 2: source layer and YouTube.** One `requirements.txt` edit, so one Cloud rebuild.
- `sources.py` and `youtube_documents.py`.
- `task_config.material`.
- Metadata caption and blocked-request guidance in the UI.
- `YOUTUBE_PROXY_URL` hook.
- Transcript detection for pasted text.
- The 核对归属 button.
- Updates to the skill, README and ROADMAP.
- Tests for the above.

**Phase 3: later, if evidence supports it.**
- Polished live-progress UI.
- The `context` field.
- Bilibili.
- `pyproject.toml`.
- A guard against the prompt growing again.

## 9. Open questions (recommended defaults)

1. YouTube on Streamlit Cloud: ship with graceful failure and a proxy hook, but no paid proxy? Default: yes.
2. Default generation mode: 自动 (fast for articles; careful for transcripts, 来龙去脉 and long sources)? Default: yes.
3. Is about 75 s and about 15k output tokens per transcript summary acceptable? Default: yes; hide `max`.
4. Summary language for English videos: 简体中文 for transcripts and "follow the source" for articles? Default: yes.
5. Leave Bilibili to the local skill only? Default: yes.
6. Keep evaluation inputs in a gitignored `evals/` folder? Default: yes.
7. Keep 按章节梳理 as the third mode? Default: yes.
8. Should the app honour `DEEPSEEK_MODEL`, with an allow-list? Default: yes.
