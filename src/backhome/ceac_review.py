"""CEAC Review section → one printable document + a coverage recon.

Input: `data/applications/<APP>/ceac_review/<Node>.tsv`, written from `ceac/review_extract.js` (one per CEAC
Review page: `#node=`, `## Section`, `label<TAB>value`). This is the application exactly as CEAC will submit it.

Coverage recon: every expected value in our sheet must appear in the text of the matching Review page (dates,
dropdown display names and codes are all accepted spellings). Anything missing means the form holds something
other than what we believe — fix before signing.
"""

from __future__ import annotations

import datetime as dt
import html
import re
from dataclasses import dataclass
from pathlib import Path

from .forms import Cell
from .review import CSS

# CEAC Review page -> the form pages it summarises
REVIEW_PAGES: dict[str, list[str]] = {
    "ReviewPersonal": ["Personal1", "Personal2", "AddressPhone", "PptVisa"],
    "ReviewTravel": ["Travel", "TravelCompanions", "PreviousUSTravel"],
    "ReviewUSContact": ["USContact"],
    "ReviewFamily": ["Relatives"],
    "ReviewWorkEducation": ["WorkEducation1", "WorkEducation2", "WorkEducation3"],
    "ReviewSecurity": [f"SecurityandBackground{i}" for i in range(1, 6)],
    "ReviewTemporaryWork": ["TemporaryWork"],
    "ReviewLocation": [],
}


@dataclass
class ReviewPage:
    node: str
    title: str
    sections: list[tuple[str, list[tuple[str, str]]]]

    @property
    def text(self) -> str:
        return "\n".join(f"{k}\t{v}" for _, rows in self.sections for k, v in rows).upper()


def read_page(path: Path) -> ReviewPage:
    meta, sections = {}, [("", [])]
    for line in path.read_text().splitlines():
        if line.startswith("#") and not line.startswith("## "):
            k, _, v = line[1:].partition("=")
            meta[k] = v
        elif line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif "\t" in line:
            k, _, v = line.partition("\t")
            v = re.sub(r",\s*Edit .*$", "", v)  # the extractor may glue a trailing "Edit … Information" link
            sections[-1][1].append((k.strip(), v.strip()))
    return ReviewPage(meta.get("node", path.stem), meta.get("title", path.stem), [s for s in sections if s[1]])


def load(folder: Path) -> dict[str, ReviewPage]:
    return {p.stem: read_page(p) for p in sorted(Path(folder).glob("*.tsv"))}


def _spellings(c: Cell, snapshot: dict) -> set[str]:
    out = {s.upper() for s in (c.human, c.expected) if s}
    shown = snapshot.get(c.id, {}).get("display")
    if shown:
        out.add(shown.upper())
    for s in list(out):
        try:
            d = dt.date.fromisoformat(s[:10])
            out |= {d.strftime("%d %B %Y").upper(), d.strftime("%d %b %Y").upper()}
        except ValueError:
            pass
    return out


@dataclass
class Coverage:
    node: str
    checked: int
    missing: list[tuple[str, str, str]]  # (page, label, expected)


def coverage(pages: dict[str, ReviewPage], cells: list[Cell], snapshots: dict[str, dict]) -> list[Coverage]:
    out = []
    for node, form_pages in REVIEW_PAGES.items():
        if node not in pages:
            continue
        text = re.sub(r"\s+", " ", pages[node].text)
        checked, missing = 0, []
        for c in cells:
            if c.page not in form_pages or not c.expected or c.expected in ("Y", "N", "0", "1"):
                continue
            if len(c.expected) <= 2 and c.expected.isdigit():  # day/month dropdown parts are covered by the date
                continue
            checked += 1
            snap = snapshots.get(c.page, {}).get("values", {})
            if not any(re.sub(r"\s+", " ", s) in text for s in _spellings(c, snap)):
                missing.append((c.page, c.label or c.id, c.human or c.expected))
        out.append(Coverage(node, checked, missing))
    return out


def render(pages: dict[str, ReviewPage], cov: list[Coverage], app_id: str, photo_b64: str | None = None) -> str:
    esc = html.escape
    cov_by = {c.node: c for c in cov}
    nav, secs = [], []
    order = [n for n in REVIEW_PAGES if n in pages] + [n for n in pages if n not in REVIEW_PAGES]
    for node in order:
        pg = pages[node]
        cv = cov_by.get(node)
        flag = bool(cv and cv.missing)
        title = pg.title.replace("Non-Immigrant Visa - Review ", "").replace("Nonimmigrant Visa - Review ", "")
        nav.append(
            f'<a href="#{node.lower()}" class="{"flag" if flag else ""}"><span>{esc(title)}</span>'
            f'<span class="n">{sum(len(r) for _, r in pg.sections)}</span></a>'
        )
        note = ""
        if cv:
            note = (
                f"{cv.checked} of our answers found on this page."
                if not cv.missing
                else f"{len(cv.missing)} of {cv.checked} answers not found: "
                + "; ".join(f"{esc(lbl)} = {esc(v)}" for _, lbl, v in cv.missing[:6])
            )
        body = "".join(
            f"<h3>{esc(name)}</h3>" * bool(name)
            + "<table><tbody>"
            + "".join(f'<tr><td class="q">{esc(k)}</td><td class="a">{esc(v)}</td></tr>' for k, v in rows)
            + "</tbody></table>"
            for name, rows in pg.sections
        )
        secs.append(
            f'<section id="{node.lower()}"><h2>{esc(title)}</h2>'
            f'<p class="sub{" bad" if flag else ""}">{note}</p>{body}</section>'
        )
    missing_total = sum(len(c.missing) for c in cov)
    got = sum(1 for n in REVIEW_PAGES if n in pages)
    verdict = (
        f"All {len(REVIEW_PAGES)} CEAC review pages captured; every answer we expect is on them."
        if got == len(REVIEW_PAGES) and not missing_total
        else f"{got} of {len(REVIEW_PAGES)} review pages captured, {missing_total} expected answer(s) not found."
    )
    img = f'<img alt="Application photo" src="data:image/jpeg;base64,{photo_b64}">' if photo_b64 else ""
    now = dt.datetime.now().strftime("%d %b %Y, %H:%M")
    extra = "h3{font-size:15px;margin:18px 0 4px;color:var(--ink-2)} .sub.bad{color:var(--bad)} td.q{width:46%}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>CEAC review {esc(app_id)}</title>
<style>{CSS}{extra}</style></head><body><div class="wrap"><nav aria-label="Review pages">{"".join(nav)}</nav><main>
<header class="{"foil" if img else "foil nophoto"}">{img}<div><h1>CEAC review export</h1>
<p class="who">Application {esc(app_id)} exactly as ceac.state.gov will submit it, captured {now}.
This copy has not been signed or submitted.</p>
<p class="verdict {"ok" if got == len(REVIEW_PAGES) and not missing_total else "bad"}">{esc(verdict)}</p></div></header>
{"".join(secs)}
<footer>Captured page by page from the CEAC Review section with <code>review_extract.js</code>, then checked
against the answers backhome filled. Sign and submit only on ceac.state.gov.</footer></main></div></body></html>"""
