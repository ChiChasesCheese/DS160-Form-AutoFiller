"""One command, whole pipeline: raw -> digest -> validate -> sheet -> recon -> preflight -> review (HTML + PDF).

Each stage reports ok / warn / fail; the run stops at the first failing gate that makes later stages
meaningless (raw tampering, profile errors) and otherwise runs to the end so the reports are always fresh.
"""

from __future__ import annotations

import csv
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from . import docs, forms, review
from .model import Profile
from .validators import check_profile


@dataclass
class Stage:
    name: str
    status: str  # ok | warn | fail | skip
    detail: str
    seconds: float = 0.0


def run(home: Path, app: str, spec_path: Path, *, pdf: bool = True, mask: bool = False) -> list[Stage]:
    raw, data = home / "raw", home / "data"
    app_dir = data / "applications" / app
    stages: list[Stage] = []

    def stage(name, fn):
        t = time.perf_counter()
        try:
            status, detail = fn()
        except Exception as e:  # noqa: BLE001 — a stage failure is a result, not a crash
            status, detail = "fail", f"{type(e).__name__}: {e}"
        stages.append(Stage(name, status, detail, round(time.perf_counter() - t, 2)))
        return status != "fail"

    def s_raw():
        if not (raw / "MANIFEST.tsv").exists():
            return "skip", "no raw/ manifest (run `backhome ingest` to add documents)"
        problems = docs.verify(raw)
        return (
            ("fail", f"{len(problems)} file(s) changed/missing: {problems[:3]}")
            if problems
            else ("ok", f"{len(docs.load_manifest(raw))} documents, sha256 intact")
        )

    def s_digest():
        if not (raw / "MANIFEST.tsv").exists():
            return "skip", "no raw/"
        index = data / "digest" / "INDEX.tsv"
        if index.exists() and index.stat().st_mtime >= (raw / "MANIFEST.tsv").stat().st_mtime:
            return "ok", "up to date"
        rows = docs.digest(raw, data / "digest")
        vision = sum(r["status"] == "needs-vision" for r in rows)
        return ("warn" if vision else "ok"), f"{len(rows)} files, {vision} need visual reading"

    profile_holder = {}

    def s_validate():
        p = Profile(data / "profile").mount("app", app_dir / "application.yaml")
        profile_holder["p"] = p
        issues = check_profile(p)
        errors = [i for i in issues if i.level == "error"]
        review_n = sum("confidence=" in i.msg for i in issues)
        if errors:
            return "fail", "; ".join(map(str, errors[:3]))
        return ("warn" if review_n else "ok"), f"0 errors, {review_n} fact(s) to confirm"

    sheet_holder = {}

    def s_sheet():
        spec = forms.load_spec(spec_path)
        cells = forms.build_sheet(spec, profile_holder["p"])
        forms.write_sheet(cells, app_dir / "sheet.tsv")
        sheet_holder.update(spec=spec, cells=cells)
        bad = [c for c in cells if c.error]
        unknown = sum(c.blocking for c in cells)
        status = "fail" if bad else "warn" if unknown else "ok"
        return status, f"{len(cells)} fields, {unknown} unknown, {len(bad)} invalid"

    def s_recon():
        spec, cells = sheet_holder["spec"], sheet_holder["cells"]
        snaps = forms.load_snapshots(app_dir / "snapshots")
        rows = forms.recon(cells, snaps)
        with (app_dir / "recon.tsv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, list(forms.ReconRow.__dataclass_fields__), delimiter="\t")
            w.writeheader()
            w.writerows(asdict(r) for r in rows)
        cfg = yaml.safe_load((app_dir / "application.yaml").read_text()) or {}
        qs = forms.questionnaire(cells, {**spec.get("groups", {}), **cfg.get("prompts", {})})
        (app_dir / "OVERVIEW.md").write_text(forms.overview(spec, cells, rows, qs, app))
        (app_dir / "QUESTIONNAIRE.md").write_text(forms.questionnaire_md(qs, app))
        sheet_holder.update(rows=rows, snaps=snaps)
        c = {s: sum(r.status == s for r in rows) for s in ("match", "mismatch", "missing", "not-captured", "blocked")}
        status = (
            "fail" if c["mismatch"] or c["missing"] else "warn" if c["not-captured"] or c["blocked"] or qs else "ok"
        )
        return (
            status,
            f"{c['match']} match, {c['mismatch'] + c['missing']} differ, {c['not-captured']} unchecked, {len(qs)} open question(s)",
        )

    def s_review():
        spec, cells, rows, snaps = (sheet_holder[k] for k in ("spec", "cells", "rows", "snaps"))
        photo = next((p for p in (app_dir / "photo.jpg", data / "photo" / "ds160.jpg") if p.exists()), None)
        doc = review.render_html(spec, cells, rows, snaps, profile_holder["p"].value, app, photo, mask=mask)
        out = app_dir / "review.html"
        out.write_text(doc)
        if not pdf:
            return "ok", str(out)
        review.to_pdf(out, app_dir / "review.pdf")
        return "ok", f"{out.name} + review.pdf"

    def s_preflight():
        from . import preflight

        findings = preflight.run(profile_holder["p"], sheet_holder["cells"], sheet_holder["rows"])
        (app_dir / "PREFLIGHT.md").write_text(preflight.to_markdown(findings, app))
        n = {k: sum(f.status == k for f in findings) for k in ("pass", "fail", "warn", "manual")}
        status = "fail" if n["fail"] else "warn" if n["warn"] or n["manual"] else "ok"
        return status, f"{n['pass']} pass, {n['fail']} fail, {n['warn']} warn, {n['manual']} to eyeball → PREFLIGHT.md"

    stage("raw integrity", s_raw) and stage("digest", s_digest)
    if stage("validate profile", s_validate) and stage("build sheet", s_sheet):
        if stage("recon vs CEAC", s_recon):
            stage("preflight checks", s_preflight)
            stage("review document", s_review)
    return stages
