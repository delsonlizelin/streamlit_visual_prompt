"""Local command-line summary workflow, independent of Streamlit.

Reads pasted text (stdin), a Markdown/TXT/PDF file, a public web/WeChat URL or a
YouTube URL through the shared source layer; asks DeepSeek for a structured
summary; runs the local quality lint (optionally one revision pass and an
attribution check); and writes JSON, Markdown, PDF and/or a long PNG.

    python summarize_cli.py https://youtu.be/VIDEO_ID --mode story
    python summarize_cli.py article.md --formats md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from app_settings import load_local_settings  # noqa: E402
from sources import (  # noqa: E402
    KIND_LABELS,
    SourceDocument,
    SourceError,
    load_text,
    load_upload,
    load_url,
    material_task_config,
    suggest_mode,
    suggested_language,
)
from summarizer import (  # noqa: E402
    SummaryError,
    lint_summary_document,
    resolve_generation,
    revise_summary_with_feedback,
    summarize_markdown,
)

FORMATS = ("md", "png", "json")


def read_source(value: str, settings) -> SourceDocument:  # noqa: ANN001
    if value == "-":
        return load_text(sys.stdin.read())
    if value.startswith(("http://", "https://")) or value.startswith(("youtu.be/", "www.youtube.com/")):
        return load_url(
            value,
            youtube_enabled=settings.youtube_enabled,
            youtube_proxy_url=settings.youtube_proxy_url,
        )
    path = Path(value).expanduser()
    return load_upload(path.name, path.read_bytes())


def progress_printer():  # noqa: ANN201
    last = [0.0]

    def report(elapsed: float, reasoning_chars: int, content_chars: int) -> None:
        if elapsed - last[0] >= 10:
            last[0] = elapsed
            phase = "writing" if content_chars else "thinking"
            print(f"  … {phase} · {elapsed:.0f}s · {reasoning_chars:,} reasoning chars", file=sys.stderr)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="file path, web/WeChat/YouTube URL, or '-' for stdin")
    parser.add_argument("-o", "--out", help="output directory (default: next to the source file, else cwd)")
    parser.add_argument("-n", "--name", help="output file stem (default: source title or file name)")
    parser.add_argument("--mode", choices=("auto", "standard", "story", "howto", "section"), default="auto",
                        help="auto = suggest from the material; standard 先看结论 (结论是什么); story 来龙去脉 "
                             "(发生了什么); howto 上手步骤 (怎么做); section 逐章梳理 (每章讲什么)")
    parser.add_argument("--style", choices=("direct", "beginner"), default="direct")
    parser.add_argument("--length", choices=("normal", "detailed"), default="normal")
    parser.add_argument("--lang", choices=("auto", "source", "zh", "en"), default="auto",
                        help="auto = 简体中文 for non-Chinese transcripts, otherwise follow the source")
    parser.add_argument("--material", choices=("auto", "article", "document", "transcript"), default="auto",
                        help="override the detected material type")
    parser.add_argument("--instructions", default="", help="extra preferences appended to the prompt")
    parser.add_argument("--effort", choices=("auto", "none", "low", "high", "max"), default="auto",
                        help="auto = thinking (high) for story mode, transcripts and long sources; "
                             "'none' disables thinking")
    parser.add_argument("--thinking", action="store_const", const="high", dest="effort",
                        help="shorthand for --effort high")
    parser.add_argument("--revise", action="store_true",
                        help="if the local quality lint finds issues, run one targeted revision")
    parser.add_argument("--check-attribution", action="store_true",
                        help="run one revision that re-checks who said/accused what against the source")
    parser.add_argument("--formats", default="md,png",
                        help=f"comma-separated subset of {','.join(FORMATS)}")
    parser.add_argument("--image-mode", choices=("tablet", "mobile"), default="tablet")
    parser.add_argument("--save-source", action="store_true",
                        help="also write the loaded source text (e.g. a YouTube transcript) as <name>.source.md")
    args = parser.parse_args()

    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    unknown = sorted(set(formats) - set(FORMATS))
    if unknown:
        parser.error(f"unknown format(s): {', '.join(unknown)}")

    settings = load_local_settings()
    if not settings.api_key:
        print("error: no DEEPSEEK_API_KEY in the environment or .streamlit/secrets.toml", file=sys.stderr)
        return 2

    try:
        source = read_source(args.source, settings)
    except SourceError as error:
        print(f"error: {error}" + (f"\nhint: {error.hint}" if error.hint else ""), file=sys.stderr)
        return 1
    material = source.material
    if args.material != "auto":
        from dataclasses import replace

        material = replace(material, kind=args.material)

    stem = args.name or source.output_name
    is_file = not (args.source == "-" or "://" in args.source or args.source.startswith(("youtu.be/", "www.youtube.com/")))
    if args.out:
        out_dir = Path(args.out).expanduser()
    elif is_file:
        out_dir = Path(args.source).expanduser().resolve().parent
    else:
        out_dir = Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)

    language = suggested_language(material) if args.lang == "auto" else args.lang
    if args.mode == "auto":
        args.mode, reason = suggest_mode(source.text, material)
        print(f"mode: {args.mode} (auto{': ' + reason if reason else ''})", file=sys.stderr)
    if args.effort == "auto":
        thinking, effort = resolve_generation(
            "auto", mode=args.mode, material_kind=material.kind, source_characters=len(source.text)
        )
    else:
        thinking, effort = args.effort != "none", (args.effort if args.effort != "none" else "high")

    options = dict(
        mode=args.mode, language=language, style=args.style, length=args.length,
        custom_instructions=args.instructions, material=material_task_config(material),
        api_key=settings.api_key, model=settings.model, base_url=settings.base_url,
        thinking=thinking, reasoning_effort=effort, on_progress=progress_printer(),
    )
    notices = f" · {' · '.join(source.notices)}" if source.notices else ""
    print(f"source: {source.title} · {KIND_LABELS[material.kind]}{notices} · {source.characters:,} chars", file=sys.stderr)
    print(f"summary: {settings.model} · mode {args.mode} · lang {language} · "
          f"{'thinking ' + effort if thinking else 'no thinking'}", file=sys.stderr)
    if args.save_source:
        target = out_dir / f"{stem}.source.md"
        target.write_text(source.text, "utf-8")
        print(target)

    started = time.monotonic()
    try:
        result = summarize_markdown(source.text, **options)
        report = lint_summary_document(result.document, source.text)
        if args.revise and not report.passed:
            print(f"quality: {len(report.issues)} issue(s) → one revision pass", file=sys.stderr)
            result = revise_summary_with_feedback(
                source.text, result.document, [issue.message for issue in report.issues],
                feedback_kind="quality", **options,
            )
            report = lint_summary_document(result.document, source.text)
        if args.check_attribution:
            print("attribution: re-checking who said/accused what", file=sys.stderr)
            result = revise_summary_with_feedback(
                source.text, result.document, ["核对每条的主语、指控方与被指控方是否与原文一致。"],
                feedback_kind="attribution", **options,
            )
            report = lint_summary_document(result.document, source.text)
    except SummaryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"done: {result.prompt_tokens:,} prompt + {result.completion_tokens:,} completion tokens "
          f"(last call), {time.monotonic() - started:.0f}s total", file=sys.stderr)
    for issue in report.issues:
        print(f"  check [{issue.severity}] {issue.message}", file=sys.stderr)

    written: list[Path] = []
    document = result.document
    if "json" in formats:
        target = out_dir / f"{stem}.summary.json"
        target.write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), "utf-8")
        written.append(target)
    if "md" in formats:
        target = out_dir / f"{stem}.summary.md"
        target.write_text(document.to_markdown(), "utf-8")
        written.append(target)
    if "png" in formats:
        from longread_pdf import RenderError, render_summary_long_image

        try:
            image = render_summary_long_image(document, mode=args.image_mode)
        except RenderError as error:
            print(f"render error: {error}", file=sys.stderr)
            return 1
        target = out_dir / f"{stem}.summary.png"
        target.write_bytes(image.png)
        written.append(target)

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
