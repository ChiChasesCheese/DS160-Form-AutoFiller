"""backhome CLI. Run from the repo root (or set BACKHOME_HOME).

    backhome ingest SRC...            copy documents into raw/ (+ MANIFEST.tsv), idempotent
    backhome verify-raw               raw/ files still match their sha256
    backhome digest [--ocr]           extract text -> data/digest/, INDEX.tsv lists what needs vision
    backhome validate                 profile checks (checksums, MRZ, cross-field, provenance)
    backhome sheet APP                spec + profile -> data/applications/APP/sheet.tsv
    backhome recon APP                sheet vs snapshots -> recon.tsv, OVERVIEW.md, QUESTIONNAIRE.md
    backhome answer PATH VALUE        persist a user answer (answers.yaml overlay) with source + confidence
    backhome status APP               one-screen summary per section
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

from . import docs, forms
from .model import Confidence, Profile
from .validators import check_profile

HOME = Path(os.environ.get("BACKHOME_HOME", ".")).resolve()
FORMS_DIR = Path(__file__).parent / "forms"


def paths(app: str | None = None) -> dict[str, Path]:
    data = HOME / "data"
    p = {"raw": HOME / "raw", "data": data, "profile": data / "profile", "digest": data / "digest"}
    if app:
        p["app"] = data / "applications" / app
    return p


def load(app: str) -> tuple[dict, Profile, Path]:
    p = paths(app)
    app_yaml = p["app"] / "application.yaml"
    if not app_yaml.exists():
        sys.exit(f"no {app_yaml} — create it (see examples/applications/)")
    cfg = yaml.safe_load(app_yaml.read_text()) or {}
    spec_path = Path(cfg.get("spec") or FORMS_DIR / cfg.get("form", "ds160") / "spec.yaml")
    profile = Profile(p["profile"]).mount("app", app_yaml)
    return forms.load_spec(spec_path), profile, p["app"]


def cmd_ingest(a) -> int:
    stats = docs.ingest([Path(s) for s in a.sources], paths()["raw"])
    print(" ".join(f"{k}={v}" for k, v in stats.items()))
    return 0


def cmd_verify_raw(a) -> int:
    problems = docs.verify(paths()["raw"])
    print("\n".join(problems) or "raw/ intact")
    return 1 if problems else 0


def cmd_digest(a) -> int:
    index = docs.digest(paths()["raw"], paths()["digest"], ocr=a.ocr)
    by = {}
    for r in index:
        by[r["status"]] = by.get(r["status"], 0) + 1
    print(f"{len(index)} files: " + ", ".join(f"{k}={v}" for k, v in sorted(by.items())))
    print(f"index: {paths()['digest'] / 'INDEX.tsv'}")
    return 0


def cmd_validate(a) -> int:
    issues = check_profile(Profile(paths()["profile"]))
    errors = [i for i in issues if i.level == "error"]
    for i in issues if a.all else errors + [i for i in issues if i.level == "warn" and "confidence=" not in i.msg]:
        print(i)
    review = sum("confidence=" in i.msg for i in issues)
    print(f"\n{len(errors)} error(s), {len(issues) - len(errors) - review} warning(s), {review} fact(s) need review"
          + ("" if a.all else " (--all to list)"))
    return 1 if errors else 0


def _sheet(app: str):
    spec, profile, app_dir = load(app)
    cells = forms.build_sheet(spec, profile)
    forms.write_sheet(cells, app_dir / "sheet.tsv")
    return spec, cells, app_dir


def cmd_sheet(a) -> int:
    _, cells, app_dir = _sheet(a.app)
    bad = [c for c in cells if c.error]
    for c in bad:
        print(f"[INVALID] {c.page}.{c.id}: {c.error}")
    print(f"{len(cells)} cells, {sum(c.blocking for c in cells)} unknown, {len(bad)} invalid -> {app_dir / 'sheet.tsv'}")
    return 1 if bad else 0


def cmd_recon(a) -> int:
    spec, cells, app_dir = _sheet(a.app)
    rows = forms.recon(cells, forms.load_snapshots(app_dir / "snapshots"))
    with (app_dir / "recon.tsv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, list(forms.ReconRow.__dataclass_fields__), delimiter="\t")
        w.writeheader()
        w.writerows(asdict(r) for r in rows)
    app_cfg = yaml.safe_load((app_dir / "application.yaml").read_text()) or {}
    qs = forms.questionnaire(cells, {**spec.get("groups", {}), **app_cfg.get("prompts", {})})
    (app_dir / "OVERVIEW.md").write_text(forms.overview(spec, cells, rows, qs, a.app))
    (app_dir / "QUESTIONNAIRE.md").write_text(forms.questionnaire_md(qs, a.app))
    (app_dir / "questionnaire.yaml").write_text(yaml.safe_dump([asdict(q) for q in qs], allow_unicode=True, sort_keys=False))
    counts = {}
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1
    print(" ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for r in rows:
        if r.status in ("mismatch", "missing"):
            print(f"[{r.status.upper()}] {r.page}.{r.id}: expected {r.expected!r}, CEAC has {r.actual!r}")
    print(f"{len(qs)} open question(s). Reports: {app_dir}/OVERVIEW.md, QUESTIONNAIRE.md")
    return 1 if counts.get("mismatch") or counts.get("missing") else 0


def cmd_status(a) -> int:
    rc = cmd_recon(a)
    text = (paths(a.app)["app"] / "OVERVIEW.md").read_text()
    table = text.split("\n\n")[3]
    print("\n" + table)
    return rc


def cmd_answer(a) -> int:
    value = yaml.safe_load(a.value) if a.typed else a.value
    fact = Profile(paths()["profile"]).answer(a.path, value, a.source, Confidence(a.confidence), a.note)
    print(f"{a.path} = {fact.value!r}  [{fact.confidence.value}, {fact.source}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="backhome", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("ingest"); s.add_argument("sources", nargs="+"); s.set_defaults(fn=cmd_ingest)  # noqa: E702
    sub.add_parser("verify-raw").set_defaults(fn=cmd_verify_raw)
    s = sub.add_parser("digest"); s.add_argument("--ocr", action="store_true"); s.set_defaults(fn=cmd_digest)  # noqa: E702
    s = sub.add_parser("validate"); s.add_argument("--all", action="store_true"); s.set_defaults(fn=cmd_validate)  # noqa: E702
    for name, fn in (("sheet", cmd_sheet), ("recon", cmd_recon), ("status", cmd_status)):
        s = sub.add_parser(name); s.add_argument("app"); s.set_defaults(fn=fn)  # noqa: E702
    s = sub.add_parser("answer")
    s.add_argument("path"); s.add_argument("value")  # noqa: E702
    s.add_argument("--source", help="default user:<today>")
    s.add_argument("--confidence", default="user", choices=[c.value for c in Confidence])
    s.add_argument("--note")
    s.add_argument("--typed", action="store_true", help="parse VALUE as YAML (dates, booleans, lists)")
    s.set_defaults(fn=cmd_answer)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
