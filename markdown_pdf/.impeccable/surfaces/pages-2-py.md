---
version: 1
slug: "pages-2-py"
primary_target: "pages/2_文章摘要.py"
related_targets: ["longread_pdf/assets/summary_template.html","longread_pdf/assets/summary.css","longread_pdf/assets/long_image.css"]
---

## Scope and mode

- Surface: article-to-summary-image workflow (`pages/2_文章摘要.py`) and its deterministic exported artifact.
- Mode: Operate for the web surface; Read for the exported long image.

## Audience, job, action, and proof

- A reader or knowledge worker supplies a long source and needs a faithful, share-ready mobile brief with minimal setup.
- Primary action: generate the summary image.
- Proof: the structured long-image result is the dominant artifact, not marketing copy or synthetic metrics.
- Constraints: preserve Streamlit behavior, responsive stacking, keyboard access, source editability, and deterministic Chinese typography.

## Chosen direction

- Direction: policy-briefing workbench on cool uncoated paper. A compact source/settings rail supports a dominant proof surface. Graphite carries content; cinnabar marks only active state, section numerals, and conclusion-changing evidence.
- Approved comp: `.impeccable/mocks/summary-workbench-b-approved.png`.
- Memorable moment: the same numbered editorial sections visible in the model's structured output become the exported long image without layout guesswork.
- Mobile: the rail becomes a single reading flow above the result; no persistent sidebar.

## Component and composition inventory

| Ingredient | Commitment | Medium |
| --- | --- | --- |
| Page shell | Cool gray field, generous centered workspace, hairline top navigation | Semantic Streamlit HTML + CSS |
| Source/settings region | Compact numbered workflow, flat white fields, 10–12px corner language, no card stack | Streamlit controls + CSS |
| Primary action | Full-width cinnabar button, no gradient or glow | Streamlit button + CSS |
| Result proof | Largest region on wide screens; freshness, quality, and local-edit controls precede the potentially tall image; natural stack on mobile | Streamlit controls + deterministic PNG renderer |
| Summary header | Title, optional source/author metadata, no fake snapshot or logo | HTML template |
| Summary sections | One white reading sheet with hairline separation, no nested page inset, and a compact number rail so body copy keeps roughly 80% of the mobile canvas | Structured data + HTML/CSS |
| Emphasis | 0–2 short spans per item, cinnabar plus weight; routine bullets remain neutral and color is never the sole carrier | Escaped HTML spans |
| Type | Project-hosted Noto Sans SC variable font, tabular section figures, strong scale contrast | CSS font stack |
| Elevation | None for controls; only a subtle page lift for the generated artifact | CSS |

## Unresolved decisions

- None blocking. OCR for image-only sources remains outside this implementation unless an existing dependency makes it safe and local.
