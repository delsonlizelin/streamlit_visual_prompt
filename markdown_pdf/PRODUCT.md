# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are Chinese-speaking readers who receive long articles, public-account posts, reports, and Markdown drafts and need either a calm reading PDF or a concise mobile summary they can understand and share quickly. They may be using the tool from a desktop while preparing an artifact or from a phone while consuming and sharing it.

## Product Purpose

Markdown PDF turns source material into two finished reading artifacts: a restrained long-form PDF and an information-dense summary image. Success means the result is immediately readable, faithful to the source, and finished enough to download or share without manual cleanup.

## Positioning

The product combines source-aware editorial compression with deterministic typography. The model decides what matters; the renderer—not an image model—controls Chinese text, hierarchy, emphasis, and export quality.

## Operating Context

Users paste text, upload Markdown, TXT, or text-based PDFs, or provide a public article URL. They can edit extracted text before generation. Summary generation sends the selected source to DeepSeek only after the user acts; an explicit feedback-revision action additionally sends the current summary and local quality findings. PDF conversion and local file extraction remain local to the app runtime.

## Capabilities and Constraints

- Two independent workflows: Markdown-to-PDF and article-to-summary-image.
- Summary inputs include pasted text, Markdown, TXT, text PDFs, and public URLs, including WeChat articles when their content can be extracted.
- Summary output is a deterministic high-resolution PNG designed for mobile reading and sharing.
- PDF output supports desktop/A4, tablet, and phone reading formats.
- Source extraction completeness is a prerequisite for summary quality; image-only and access-protected sources may require OCR or a fallback source.
- The service must not invent facts, silently launder opinions into facts, or add generic disclaimers absent from the source.

## Brand Commitments

The product voice is calm, direct, literate, and non-promotional. The interface and artifacts should feel minimal and editorial rather than like a generic AI dashboard. Warm orange may be used sparingly to mark decisive information. The user-provided “总结一下鸭” examples are a content-density and mobile-reading reference, not a request to reproduce its logo, chrome, or source snapshot.

## Evidence on Hand

- User-provided reference screenshots: `/var/folders/wv/xpps24ln1_n3m131tdy7bxc00000gn/T/codex-clipboard-d2277993-6d2f-4ac8-91af-c6d55cad6301.png` and `/var/folders/wv/xpps24ln1_n3m131tdy7bxc00000gn/T/codex-clipboard-c62d7d1b-0b72-475a-8feb-d3ddbad59440.png`.
- A real WeChat source article and its official full-text speech counterpart are available for extraction and summary regression testing.
- No customer logos, testimonials, performance claims, or proprietary brand assets are available and none should be fabricated.

## Product Principles

1. Content before ceremony: spend space on conclusions, evidence, and causal logic rather than framing or disclaimers.
2. Structure follows information: sections and length adapt to the source instead of satisfying a rigid quota.
3. Faithful but editorial: remove repetition and rhetoric while preserving attribution, uncertainty, and conclusion-changing conditions.
4. Deterministic output: use structured content and code-driven rendering for reliable Chinese typography and export.
5. Quiet operation: expose only choices that materially change the artifact and keep the primary workflow obvious.

## Accessibility & Inclusion

Core controls must remain keyboard accessible and usable at narrow mobile widths. Text contrast, focus visibility, touch targets, and Chinese line breaking should meet production web expectations; color must not be the only carrier of meaning.
