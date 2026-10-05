"""Opt-in summary evaluation: runs real DeepSeek requests and costs money.

Reads `evals/manifest.json` (gitignored; see `scripts/eval_manifest.example.json`),
summarizes each source in each listed mode and generation choice, and writes the
summaries plus a `results.csv` with timing, tokens, lint findings and empty rubric
columns for manual yes/no scoring.

    python scripts/eval_summaries.py --yes
    python scripts/eval_summaries.py --yes --only dispute-video
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from app_settings import load_local_settings  # noqa: E402
from sources import SourceError, load_text, load_upload, load_url, material_task_config, suggested_language  # noqa: E402
from summarizer import SummaryError, lint_summary_document, resolve_generation, summarize_markdown  # noqa: E402

RUBRIC = (
    "two_sentence_retell",      # after lead + section 1, a reader can retell what happened / the main point
    "parties_identified",       # people and organisations identified at first mention
    "trigger_early",            # the origin or central question is in the lead or section 1
    "attribution_correct",      # every claim and accusation names who made it and its target
    "hedges_kept",              # nothing the source hedges is stated as fact
    "numbers_match",            # numbers match the source after unit conversion
    "no_asr_artifacts",         # no outro phrases or recognition errors used as byline or facts
    "within_budget",            # length within the mode's budget
)


def load_source(entry: dict, settings, base: Path):  # noqa: ANN001, ANN201
    value = entry["source"]
    if value.startswith(("http://", "https://")):
        return load_url(value, youtube_enabled=settings.youtube_enabled,
                        youtube_proxy_url=settings.youtube_proxy_url)
    path = (base / value).expanduser()
    if entry.get("paste"):
        return load_text(path.read_text("utf-8"))
    return load_upload(path.name, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default=str(PROJECT_DIR / "evals" / "manifest.json"))
    parser.add_argument("--only", action="append", help="run only these entry ids")
    parser.add_argument("--yes", action="store_true", help="confirm that real API requests may be sent")
    args = parser.parse_args()
    if not args.yes:
        print("This sends real DeepSeek requests. Re-run with --yes to proceed.", file=sys.stderr)
        return 2

    manifest_path = Path(args.manifest)
    entries = json.loads(manifest_path.read_text("utf-8"))
    settings = load_local_settings()
    run_dir = manifest_path.parent / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for entry in entries:
        if args.only and entry["id"] not in args.only:
            continue
        try:
            source = load_source(entry, settings, manifest_path.parent)
        except (SourceError, OSError) as error:
            print(f"{entry['id']}: source failed: {error}", file=sys.stderr)
            continue
        for mode in entry.get("modes", ["standard"]):
            for choice in entry.get("generation", ["auto"]):
                thinking, effort = resolve_generation(
                    choice, mode=mode, material_kind=source.material.kind,
                    source_characters=len(source.text),
                )
                label = f"{entry['id']}.{mode}.{choice}"
                print(f"{label}: running ({'thinking' if thinking else 'fast'})…", file=sys.stderr)
                try:
                    result = summarize_markdown(
                        source.text, mode=mode,
                        language=entry.get("language") or suggested_language(source.material),
                        material=material_task_config(source.material),
                        api_key=settings.api_key, model=settings.model, base_url=settings.base_url,
                        thinking=thinking, reasoning_effort=effort,
                    )
                except SummaryError as error:
                    rows.append({"run": label, "error": str(error)})
                    continue
                document = result.document
                (run_dir / f"{label}.summary.json").write_text(
                    json.dumps(document.to_dict(), ensure_ascii=False, indent=2), "utf-8"
                )
                report = lint_summary_document(document, source.text)
                rows.append({
                    "run": label,
                    "material": source.material.kind,
                    "seconds": round(result.milliseconds / 1000, 1),
                    "completion_tokens": result.completion_tokens,
                    "lead_chars": len(document.lead or ""),
                    "items": sum(len(section.items) for section in document.sections),
                    "lint": " | ".join(issue.code for issue in report.issues),
                    **{name: "" for name in RUBRIC},
                    "error": "",
                })

    fields = ["run", "material", "seconds", "completion_tokens", "lead_chars", "items", "lint", *RUBRIC, "error"]
    with (run_dir / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    print(run_dir / "results.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
