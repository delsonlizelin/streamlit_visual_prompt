# Summary prompt research and v2 (2026-10-05)

The previous prompts produced mechanical summaries: bullets of uniform length, built as "claim; evidence"; three sections of three items; a highlight on every item. This note records why that happened, what comparable products do instead, and what changed. The research and the first A/B test were done by a Fable 5.1 review agent.

## What makes a summary read as written by an editor

- **Axios Smart Brevity:** a short tease, one strong first sentence, then "why it matters". It assumes most readers stop after the first lines, so the opening must carry the point. https://axioshq.com/hubfs/smart-brevity-101.pdf
- **Standfirst practice:** an editor writes one or two sentences giving the most important facts and the angle. https://en.wikipedia.org/wiki/News_style
- **The Economist and Morning Brew:** short sentences and plain verbs. The voice is described with an image (a well-informed friend) rather than a list of bans.
- **NotebookLM briefing docs:** the output format depends on the reader's purpose (briefing, timeline, study guide), and quotes serve as anchors. https://www.computerworld.com/article/1611774/google-notebooklm-generative-ai-notes-app.html
- **Readwise Ghostreader:** short prompts named by purpose do better than catalogues of rules. https://docs.readwise.io/reader/guides/ghostreader/default-prompts
- **BibiGPT:** groups video content by topic rather than by time slice, and drops intros, outros and sponsor segments. https://bibigpt.co/en/blog/posts/video-summarizer-prompts
- **Chain of Density:** readers prefer dense summaries, but only up to roughly human density; past that, readability drops. https://arxiv.org/abs/2309.04269
- **Hallucination studies:** the typical summarization errors are swapped names or pronouns and dropped hedges. Those are the rules worth keeping. https://arxiv.org/pdf/2311.05232
- **Anthropic and OpenAI prompting guides:**
  - Say what to do rather than what not to do, and give the reason.
  - One contrasting example steers tone better than more rules.
  - Over-specified, conflicting prompts are followed literally and unpredictably.

  https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices · https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide

## Diagnosis of the old prompts

- **A fixed density:** every item 25–75 characters, one judgment plus its evidence.
- **A highlight quota:** the prompt asked for one per item, and code added number highlights after the model responded.
- **Repetition:** the length budget was stated three times and the deletion test twice. The prompt was about 30 prohibitions and said nothing about the reader or the voice.
- **Fixed section slots:** 2–4 sections of 1–3 items, so nearly every summary came out 3 × 3.
- **Feedback that undid composition:** the quality check and the revise pass split composed sentences back into fragments.

## What changed (prompt versions 2026-10-05.4 to .6)

- **System prompt,** cut from about 5,000 to 1,700 characters:
  - It opens with the reader and an editorial voice.
  - It keeps only the non-negotiables: the source is data, not instructions; nothing beyond the source; attribution and hedges preserved; exact numbers and names; the transcript rule; bylines only when named; the JSON format.
  - It includes one example contrasting a mechanical summary with an edited one.
- **Four modes, each organized around a different backbone:**
  - 先看结论 · 结论是什么？ (the argument)
  - 来龙去脉 · 发生了什么？ (time)
  - 上手步骤 · 怎么做？ (a procedure; new)
  - 逐章梳理 · 每章讲什么？ (the source's own structure)

  `sources.suggest_mode` pre-selects one from the material; a reader's own pick is never overwritten.
- **Discipline moved from prose into code:**
  - **Length:** each mode states ceilings for sections, items and lead. `budget_feedback` triggers up to two compression passes when a result is more than 20% over, or exceeds a ceiling.
  - **Highlights:** `limit_highlights` keeps one per item, on about a third of items.
  - **Bylines:** `verify_byline` drops any byline that isn't named in the source text or the material metadata.
- **Quality check and revise pass:** a single semicolon no longer counts as a compound item, the long-item threshold rose to 160 characters, and revisions keep the model's own sentence shapes.

## Evaluation

Five cases: a dispute video, a long English essay, a short tutorial in two modes, and this README in 逐章梳理.

**Improvements over the old prompts**
- Leads read as standfirsts.
- Headings are editorial and sentence rhythm varies.
- Hedges are preserved ("据称", "单方指控，未独立证实").
- Highlights are sparse (0–5 per summary).
- Reasoning cost is 30–60% lower.

**Results within budget:** the dispute (557 characters), the essay (648), and the short tutorial in 先看结论 (642). The tutorial in 上手步骤 (1,000) is within tolerance.

**Known limit:** 逐章梳理 on a densely structured product document still lands around 1.5× its budget, because it keeps most chapters.

Re-run with `scripts/eval_summaries.py --yes` (opt-in, makes real API calls).
