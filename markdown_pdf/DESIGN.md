---
name: Markdown PDF
description: A quiet editorial workbench for turning source material into finished reading artifacts.
colors:
  accent: "#b84316"
  accent-deep: "#92350f"
  ink: "#191b1e"
  muted: "#626971"
  rule: "#d9dde0"
  canvas: "#f1f3f4"
  surface: "#ffffff"
typography:
  display:
    fontFamily: '"Noto Sans SC", "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", sans-serif'
    fontSize: "clamp(2.3rem, 3.8vw, 3.8rem)"
    fontWeight: 760
    lineHeight: 1.05
    letterSpacing: "-.025em"
  headline:
    fontFamily: '"Noto Sans SC", "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", sans-serif'
    fontSize: "1.35rem"
    fontWeight: 680
    lineHeight: 1.25
    letterSpacing: "-.025em"
  title:
    fontFamily: '"Noto Sans SC", "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", sans-serif'
    fontSize: "14.2pt"
    fontWeight: 740
    lineHeight: 1.36
    letterSpacing: "-.018em"
  body:
    fontFamily: '"Noto Sans SC", "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", sans-serif'
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: '"Noto Sans SC", "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", sans-serif'
    fontSize: ".82rem"
    fontWeight: 760
    lineHeight: 1.35
    letterSpacing: ".05em"
rounded:
  field: ".625rem"
  surface: ".75rem"
  artifact: "3.5mm"
spacing:
  control: ".75rem"
  inset: "1rem"
  section: "1.5rem"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    rounded: "{rounded.field}"
    padding: ".5rem 1rem"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.accent-deep}"
    textColor: "{colors.surface}"
    rounded: "{rounded.field}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: ".5rem 1rem"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: ".5rem .75rem"
    height: "44px"
  proof-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "clamp(2rem, 5vw, 4.5rem)"
---

# Design System: Markdown PDF

## Overview

**Creative North Star: "The Policy Briefing Workbench"**

Markdown PDF feels like a calm desk where source material is edited on one side and a finished proof takes shape on the other. Cool gray canvas, white paper, graphite type, hairline rules, and sparse cinnabar marks create an editorial atmosphere without imitating a newsroom masthead or a generic AI dashboard.

The interface is compact where it asks for input and generous where it proves the result. Numbered steps make the workflow legible, the primary action follows the editor immediately, and the generated artifact receives the dominant share of attention. The exported long image carries the same disciplined hierarchy in a deterministic, mobile-readable format.

**Key Characteristics:**

- Quiet policy-briefing workbench rather than promotional software chrome.
- One high-contrast cinnabar signal against cool neutral paper and graphite text.
- Compact numbered rail on desktop; natural stacked reading flow on mobile.
- Dense, deterministic editorial output with visible conclusions and evidence.
- No fabricated logo, source snapshot, footer, or generic disclaimer in the artifact.

## Colors

The palette is a cool neutral field with a single warm signal; rarity gives the accent authority.

### Primary

- **Cinnabar Signal** (`colors.accent`): Marks primary actions, step numbers, bullets, and decisive evidence. It is a navigational and semantic cue, not decoration.
- **Deep Cinnabar** (`colors.accent-deep`): Reserved for the primary action's hover state so interaction remains clear without adding another hue.

### Neutral

- **Graphite Ink** (`colors.ink`): Main headings, labels, and body text requiring maximum authority.
- **Cool Slate** (`colors.muted`): Introductory copy, metadata, captions, and supporting explanation.
- **Hairline Gray** (`colors.rule`): Section seams, field boundaries, and quiet structural dividers.
- **Workbench Gray** (`colors.canvas`): App canvas and exported-image surround.
- **Proof White** (`colors.surface`): Fields, controls, containers, and the finished proof sheet.

### Named Rules

**The One Signal Rule.** Cinnabar is the only accent hue and should occupy a small minority of any screen; use it for action, order, or evidence.

**The Paper-and-Canvas Rule.** White holds authored content and controls; cool gray establishes the workspace around them.

## Typography

**Display Font:** Project-hosted Noto Sans SC variable font (with Noto Sans CJK SC, Source Han Sans SC, PingFang SC, and sans-serif fallbacks)
**Body Font:** Project-hosted Noto Sans SC variable font (with Noto Sans CJK SC, Source Han Sans SC, PingFang SC, and sans-serif fallbacks)

**Character:** One Chinese-first grotesk family keeps the application and generated artifact direct, literate, and operational. Hierarchy comes from weight, scale, compact tracking, and spacing rather than ornamental font changes.

### Hierarchy

- **Display** (760, `clamp(2.3rem, 3.8vw, 3.8rem)`, 1.05): The page promise; bold and tightly tracked, with a mobile override that preserves impact without clipping.
- **Headline** (680, 1.35rem, 1.25): Numbered workbench section titles and major interface landmarks.
- **Title** (740, 14.2pt, 1.36): Natural editorial headings inside the exported summary.
- **Body** (400, 1rem, 1.7): Editable source, guidance, and explanatory copy; allow Chinese paragraphs to breathe rather than compressing line height.
- **Label** (760, .82rem, .05em): Compact step numbers and short operational markers, using tabular numerals when numbered.

### Named Rules

**The Weight-Before-Decoration Rule.** Establish hierarchy through size, weight, spacing, and short lines; do not introduce display serifs, novelty fonts, or decorative text effects.

## Layout

The application sits in a centered container capped at 1240px. On desktop, the summary workbench uses two unequal columns: a compact source-and-settings rail and a wider proof column. Each section begins with a hairline top rule and a two-character numbered marker aligned to its heading. The generate action sits immediately below the editable source, while refinements follow as secondary controls.

At 768px and below, the columns become a natural vertical flow with 1rem side insets, full-width controls, and a 44px minimum touch target. Headings wrap rather than shrink into a desktop proportion. The proof follows the controls, and the exported artifact remains a single reading surface instead of turning into nested cards.

The long image uses a white rounded proof sheet on the cool canvas. Its sections stack vertically with consistent seams, compact heading-to-body distance, and narrow outer gutters. The proof sheet itself adds no second page inset: only the sheet gutter, section inset, and list hanging indent shape the measure, keeping roughly 80% of the mobile canvas available to body text without making it feel edge-bound.

**The Proof-First Rule.** On wide screens, result proof receives more width than configuration; on narrow screens, source, action, refinements, and proof follow task order.

## Elevation & Depth

The system is flat by default. Canvas, white surfaces, borders, and seams create most of the depth; only the rendered proof preview receives a soft ambient lift (`0 18px 48px rgba(25, 27, 30, .12)`) to distinguish the finished artifact from controls.

### Shadow Vocabulary

- **Proof Lift** (`box-shadow: 0 18px 48px rgba(25, 27, 30, .12)`): Applied only to the generated image preview in the app.

### Named Rules

**The Flat-Until-Proven Rule.** Inputs, expanders, uploaders, and empty states stay flat; elevation belongs to a completed artifact, not routine interface chrome.

## Shapes

Controls use gently curved field corners (`rounded.field`), while containers and preview surfaces use the slightly larger surface radius (`rounded.surface`). The generated summary sheet uses its print-native rounded value (`rounded.artifact`). Hairline borders define structure; pill shapes, floating capsules, and decorative clipping are absent. Inside the exported artifact, sections share one outer silhouette and are divided by square internal seams rather than becoming separate cards.

## Components

### Buttons

- **Shape:** Gently curved, compact controls (`rounded.field`) with a 44px mobile touch height.
- **Primary:** Cinnabar fill, white text, medium-bold label, and full width in the generation or download row.
- **Hover / Focus:** Deepen to Deep Cinnabar over 140ms ease-out; focus uses a 3px translucent cinnabar outline offset by 2px.
- **Secondary:** Proof White with Graphite Ink and a Hairline Gray border; navigation remains content-sized while share actions may stretch to the available column.

### Segmented Controls

- **Style:** A single white rail with Hairline Gray boundary and compact equal-width choices.
- **State:** The selected segment uses a pale cinnabar wash, cinnabar text, and a cinnabar boundary. Selection must remain legible without color through its enclosed shape.

### Cards / Containers

- **Corner Style:** Gently rounded outer surface (`rounded.surface`); summary sections inside one artifact have square internal corners.
- **Background:** Proof White on Workbench Gray.
- **Shadow Strategy:** Flat for editors, uploaders, expanders, and empty states; Proof Lift only for the finished preview.
- **Border:** A single Hairline Gray boundary or top seam.
- **Internal Padding:** Compact for controls and generous for proof surfaces, expanding responsively.

### Inputs / Fields

- **Style:** White field, Graphite Ink, one Hairline Gray stroke, and field-radius corners; editable source areas preserve generous line height.
- **Focus:** Cinnabar border plus a visible translucent cinnabar outline; never rely on color alone.
- **Disabled:** Preserve readable text and boundary contrast while reducing emphasis; do not erase the control's shape.

### Navigation

Navigation is a single compact secondary button that names the sibling workflow. It stays visually quieter than the generate action and remains visible before the page title on both desktop and mobile.

### Numbered Workbench Heading

A two-digit cinnabar index sits in a narrow rail beside a strong Graphite Ink heading, with a Hairline Gray rule above. The same grammar organizes the exported editorial sections so interface process and reading artifact feel related without becoming identical.

### Summary Proof

The proof is one white editorial sheet. Its sections use two-digit cinnabar numbering, natural graphite headings, quiet seams, and concise body copy. Cinnabar emphasizes only conclusion-changing phrases and list markers. Metadata is subordinate, and no fake logo, snapshot, promotional footer, or generic disclaimer is appended.

## Do's and Don'ts

### Do:

- **Do** keep the primary action immediately after the editable source.
- **Do** let the proof dominate the desktop composition and preserve task order on mobile.
- **Do** use Cinnabar Signal for primary action, numbering, bullets, and decisive evidence only.
- **Do** treat white as authored paper and cool gray as the surrounding workbench.
- **Do** preserve keyboard focus, 44px touch targets, text contrast, and production-quality Chinese line breaking.

### Don't:

- **Don't** introduce extra accent hues, gradients, decorative illustration, or generic AI-dashboard chrome.
- **Don't** fragment the long image into floating cards; keep one deterministic editorial reading surface.
- **Don't** let configuration controls compete visually with the result proof.
- **Don't** fabricate a logo, source snapshot, footer, performance claim, or disclaimer absent from the source.
- **Don't** use color as the only signifier of selection, focus, status, or evidence.
