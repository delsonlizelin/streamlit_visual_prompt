"""Local command-line summary workflow, independent of Streamlit.

Reads pasted text (stdin), a Markdown/TXT/PDF file, a public web/WeChat URL or a
YouTube URL through the shared source layer; gets a structured summary; runs the
local quality lint (optionally one revision pass and an attribution check); and
writes JSON, Markdown and/or a long PNG.

The model calls go to DeepSeek by default. With `--engine session` they are handed
to the calling agent (for example Claude Code) as request files in a job folder;
the agent writes each reply and runs `--resume` until the outputs are written.

    python summarize_cli.py https://youtu.be/VIDEO_ID --mode story
    python summarize_cli.py article.md --formats md
    python summarize_cli.py article.md --engine session   # then: --resume article.session
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Mapping

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
    SessionJob,
    SummaryDocument,
    SummaryError,
    SummaryRequest,
    lint_summary_document,
    resolve_generation,
    run_summary_steps,
    summary_workflow,
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


def print_step(request: SummaryRequest) -> None:
    if request.step != "summary":
        print(f"{request.step}: {request.note}" if request.note else request.step, file=sys.stderr)


def write_outputs(document: SummaryDocument, source_text: str, output: Mapping[str, Any]) -> int:
    """Lint, then write the requested formats; shared by both engines."""
    for issue in lint_summary_document(document, source_text).issues:
        print(f"  check [{issue.severity}] {issue.message}", file=sys.stderr)
    out_dir = Path(output["out_dir"])
    stem = output["stem"]
    written: list[Path] = []
    if "json" in output["formats"]:
        target = out_dir / f"{stem}.summary.json"
        target.write_text(json.dumps(document.to_dict(), ensure_ascii=False, indent=2), "utf-8")
        written.append(target)
    if "md" in output["formats"]:
        target = out_dir / f"{stem}.summary.md"
        target.write_text(document.to_markdown(), "utf-8")
        written.append(target)
    if "png" in output["formats"]:
        from longread_pdf import RenderError, render_summary_long_image

        try:
            image = render_summary_long_image(document, mode=output["image_mode"])
        except RenderError as error:
            print(f"render error: {error}", file=sys.stderr)
            return 1
        target = out_dir / f"{stem}.summary.png"
        target.write_bytes(image.png)
        written.append(target)
    for path in written:
        print(path)
    return 0


def advance_session(job: SessionJob) -> int:
    """Write the next request for the agent, or finish once every request has a reply."""
    try:
        outcome = job.advance()
    except SummaryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if isinstance(outcome, SummaryDocument):
        code = write_outputs(outcome, job.source, job.output)
        if code == 0:
            shutil.rmtree(job.directory)
        return code
    number, request = outcome
    print_step(request)
    print(f"session: request {number} ({request.step}) is ready; save the JSON reply as "
          f"{job.reply_path(number).name}, then run --resume {job.directory}", file=sys.stderr)
    print(job.request_path(number))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", nargs="?", help="file path, web/WeChat/YouTube URL, or '-' for stdin")
    parser.add_argument("--engine", choices=("deepseek", "session"), default="deepseek",
                        help="deepseek = the API; session = hand each model call to the calling agent "
                             "as a request file in <out>/<name>.session/")
    parser.add_argument("--resume", metavar="JOB_DIR",
                        help="continue a session job after writing its latest reply; the job keeps the "
                             "options it was started with")
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

    if args.resume:
        if args.source:
            parser.error("--resume takes no source; the job keeps the options it was started with")
        try:
            job = SessionJob.load(Path(args.resume).expanduser().resolve())
        except SummaryError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        return advance_session(job)
    if not args.source:
        parser.error("a source is required (or --resume JOB_DIR)")

    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    unknown = sorted(set(formats) - set(FORMATS))
    if unknown:
        parser.error(f"unknown format(s): {', '.join(unknown)}")

    settings = load_local_settings()
    if args.engine == "deepseek" and not settings.api_key:
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
        out_dir = Path(args.out).expanduser().resolve()
    elif is_file:
        out_dir = Path(args.source).expanduser().resolve().parent
    else:
        out_dir = Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)

    language = suggested_language(material) if args.lang == "auto" else args.lang
    if args.mode == "auto":
        args.mode, reason = suggest_mode(source.text, material)
        print(f"mode: {args.mode} (auto{': ' + reason if reason else ''})", file=sys.stderr)

    task = dict(
        mode=args.mode, language=language, style=args.style, length=args.length,
        custom_instructions=args.instructions, material=material_task_config(material),
    )
    flags = dict(revise=args.revise, check_attribution=args.check_attribution)
    output = dict(out_dir=str(out_dir), stem=stem, formats=formats, image_mode=args.image_mode)
    notices = f" · {' · '.join(source.notices)}" if source.notices else ""
    print(f"source: {source.title} · {KIND_LABELS[material.kind]}{notices} · {source.characters:,} chars", file=sys.stderr)
    if args.save_source:
        target = out_dir / f"{stem}.source.md"
        target.write_text(source.text, "utf-8")
        print(target)

    if args.engine == "session":
        print(f"summary: session (calling agent) · mode {args.mode} · lang {language}", file=sys.stderr)
        try:
            job = SessionJob.create(out_dir / f"{stem}.session", source=source.text, task=task,
                                    flags=flags, output=output)
        except SummaryError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        return advance_session(job)

    if args.effort == "auto":
        thinking, effort = resolve_generation(
            "auto", mode=args.mode, material_kind=material.kind, source_characters=len(source.text)
        )
    else:
        thinking, effort = args.effort != "none", (args.effort if args.effort != "none" else "high")
    print(f"summary: {settings.model} · mode {args.mode} · lang {language} · "
          f"{'thinking ' + effort if thinking else 'no thinking'}", file=sys.stderr)

    started = time.monotonic()
    try:
        result = run_summary_steps(
            summary_workflow(source.text, task, **flags),
            api_key=settings.api_key, model=settings.model, base_url=settings.base_url,
            thinking=thinking, reasoning_effort=effort,
            on_progress=progress_printer(), on_step=print_step,
        )
    except SummaryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"done: {result.prompt_tokens:,} prompt + {result.completion_tokens:,} completion tokens, "
          f"{time.monotonic() - started:.0f}s total", file=sys.stderr)
    return write_outputs(result.document, source.text, output)


if __name__ == "__main__":
    raise SystemExit(main())
