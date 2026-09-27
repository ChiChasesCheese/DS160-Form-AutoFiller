"""Stage 1-2 of the pipeline: ingest source documents into raw/, digest them into searchable text.

raw/ is an immutable, content-addressed copy of the user's documents (never edit files there):
    raw/MANIFEST.tsv   path  sha256  bytes  origin  ingested_at
    raw/inbox/         drop zone for new files the user provides (picked up by the next ingest)

data/digest/ holds per-document text so agents can grep instead of re-reading binaries:
    data/digest/<raw path>.txt   '=== page N ===' separated text
    data/digest/INDEX.tsv        path  kind  pages  chars  status
status: text | ocr | needs-vision (image or scanned PDF: an agent must look at it) | error:<msg>
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import shutil
import subprocess
from pathlib import Path

SKIP = {".DS_Store", ".localized", "MANIFEST.tsv"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".heic", ".tif", ".tiff"}
MIN_TEXT_CHARS = 40  # below this a PDF page set is treated as scanned


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(root: Path):
    if root.is_file():
        yield root, Path(root.name)
        return
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name not in SKIP and not p.name.startswith(("~$", ".~")):
            yield p, p.relative_to(root)


def load_manifest(raw: Path) -> dict[str, dict]:
    m = raw / "MANIFEST.tsv"
    if not m.exists():
        return {}
    with m.open() as f:
        return {r["path"]: r for r in csv.DictReader(f, delimiter="\t")}


def write_manifest(raw: Path, rows: dict[str, dict]) -> None:
    with (raw / "MANIFEST.tsv").open("w", newline="") as f:
        w = csv.DictWriter(f, ["path", "sha256", "bytes", "origin", "ingested_at"], delimiter="\t")
        w.writeheader()
        for k in sorted(rows):
            w.writerow(rows[k])


def ingest(sources: list[Path], raw: Path) -> dict[str, int]:
    """Copy sources (files or directories) into raw/. Directory contents land at raw/ root.

    Idempotent: identical content is skipped; a changed file at the same path is kept side by side
    as `<stem>.<sha8><suffix>` so evidence is never overwritten.
    """
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "inbox").mkdir(exist_ok=True)
    manifest = load_manifest(raw)
    now = dt.datetime.now().isoformat(timespec="seconds")
    stats = {"copied": 0, "unchanged": 0, "conflict": 0, "registered": 0}
    for src in sources:
        for path, rel in _files(Path(src).expanduser()):
            digest = sha256(path)
            dest = raw / rel
            if dest.exists():
                if sha256(dest) == digest:
                    stats["unchanged"] += 1
                    manifest.setdefault(str(rel), _row(rel, digest, path, now))
                    continue
                dest = dest.with_name(f"{dest.stem}.{digest[:8]}{dest.suffix}")
                stats["conflict"] += 1
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            manifest[str(dest.relative_to(raw))] = _row(dest.relative_to(raw), digest, path, now)
            stats["copied"] += 1
    # register files dropped directly into raw/ (e.g. raw/inbox/) that the manifest doesn't know yet
    for path, rel in _files(raw):
        if str(rel) not in manifest:
            manifest[str(rel)] = _row(rel, sha256(path), "user-drop", now)
            stats["registered"] += 1
    write_manifest(raw, manifest)
    return stats


def _row(rel: Path, digest: str, origin: Path | str, now: str) -> dict:
    size = origin.stat().st_size if isinstance(origin, Path) else 0
    return {"path": str(rel), "sha256": digest, "bytes": size, "origin": str(origin), "ingested_at": now}


def verify(raw: Path) -> list[str]:
    """Return manifest problems: missing files or content drift (raw/ must be immutable)."""
    problems = []
    for rel, row in load_manifest(raw).items():
        p = raw / rel
        if not p.exists():
            problems.append(f"missing: {rel}")
        elif sha256(p) != row["sha256"]:
            problems.append(f"modified: {rel}")
    return problems


# ── digest ──────────────────────────────────────────────────────────────
def _pdf_text(path: Path) -> tuple[list[str], str | None]:
    from pypdf import PdfReader

    try:
        r = PdfReader(str(path))
        if r.is_encrypted:
            r.decrypt("")
        return [(pg.extract_text() or "").strip() for pg in r.pages], None
    except Exception as e:  # noqa: BLE001 — record, never crash the batch
        return [], f"error:{type(e).__name__}"


def _ocr(path: Path) -> str | None:
    if not shutil.which("tesseract"):
        return None
    try:
        out = subprocess.run(
            ["tesseract", str(path), "-", "-l", "eng+chi_sim"], capture_output=True, text=True, timeout=120
        )
        if out.returncode != 0:  # chi_sim traineddata may be absent
            out = subprocess.run(
                ["tesseract", str(path), "-", "-l", "eng"], capture_output=True, text=True, timeout=120
            )
        return out.stdout.strip() or None
    except subprocess.TimeoutExpired:
        return None


def _docx_text(path: Path) -> str:
    import re
    import zipfile

    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml).strip()


def digest(raw: Path, out: Path, ocr: bool = False) -> list[dict]:
    import logging

    logging.getLogger("pypdf").setLevel(logging.ERROR)  # font-encoding chatter, not actionable
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for path, rel in _files(raw):
        suffix = path.suffix.lower()
        row = {"path": str(rel), "kind": suffix.lstrip("."), "pages": 0, "chars": 0, "status": "skipped"}
        text = None
        if suffix == ".pdf":
            pages, error = _pdf_text(path)
            row["pages"] = len(pages)
            if error:
                row["status"] = error
            else:
                text = "\n".join(f"=== page {i} ===\n{t}" for i, t in enumerate(pages, 1))
                row["status"] = "text" if sum(map(len, pages)) >= MIN_TEXT_CHARS else "needs-vision"
        elif suffix in IMAGE_EXT:
            row["pages"] = 1
            text = _ocr(path) if ocr else None
            row["status"] = "ocr" if text else "needs-vision"
        elif suffix in {".docx", ".docm"}:
            try:
                text, row["status"] = _docx_text(path), "text"
            except Exception as e:  # noqa: BLE001
                row["status"] = f"error:{type(e).__name__}"
        elif suffix in {".txt", ".md", ".csv", ".yaml", ".json"}:
            text, row["status"] = path.read_text(errors="replace"), "text"
        if text:
            row["chars"] = len(text)
            dest = out / f"{rel}.txt"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
        index.append(row)
    with (out / "INDEX.tsv").open("w", newline="") as f:
        w = csv.DictWriter(f, ["path", "kind", "pages", "chars", "status"], delimiter="\t")
        w.writeheader()
        w.writerows(index)
    return index
