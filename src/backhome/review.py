"""Final-review document: every answer as CEAC holds it, with confidence + source, printable to PDF.

Design: a single left-aligned document styled after visa-foil security paper — the one loud element is the
machine-readable strip under the applicant block; everything else is a quiet, print-first checklist.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import shutil
import subprocess
from pathlib import Path

from .forms import Cell, ReconRow, _logical

CONF_DOTS = {"verified": 4, "high": 3, "user": 3, "medium": 2, "low": 1, "assumed": 1}
CONF_TEXT = {
    "verified": "Verified — document plus an independent check",
    "high": "From an official document",
    "user": "You told us",
    "medium": "Read from a scan or computed",
    "low": "Inferred",
    "assumed": "Default — please confirm",
}
VISA_NAMES = {"H1B-H1B": "H-1B specialty occupation", "F1-F1": "F-1 student", "B1-B2": "B-1/B-2 visitor"}
STATUS_TEXT = {
    "match": "On CEAC",
    "mismatch": "Differs on CEAC",
    "missing": "Missing on CEAC",
    "blocked": "Unknown",
    "not-captured": "Not checked yet",
}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@500&display=swap');
:root{--paper:#EEF3F1;--sheet:#FBFCFB;--ink:#1D2B53;--ink-2:#4A5677;--rule:#C9D5D1;--ok:#1F6F5C;--warn:#9A6B12;--bad:#B3261E}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--paper:#0F1626;--sheet:#152036;--ink:#E4EAF5;--ink-2:#A7B3CC;--rule:#2B3A57;--ok:#5FC2A6;--warn:#E0B25A;--bad:#F08A80}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 'Public Sans',system-ui,sans-serif;
  background-image:repeating-radial-gradient(circle at 120% -20%,transparent 0 22px,rgba(29,43,83,.035) 22px 23px)}
.wrap{display:grid;grid-template-columns:230px minmax(0,1fr);gap:40px;max-width:1180px;margin:0 auto;padding:40px 24px 80px}
nav{position:sticky;top:24px;align-self:start;font-size:14px}
nav a{display:flex;justify-content:space-between;gap:8px;color:var(--ink-2);text-decoration:none;padding:6px 10px;border-left:2px solid var(--rule)}
nav a:hover,nav a:focus-visible{color:var(--ink);border-left-color:var(--ink);outline:none}
nav a .n{font-variant-numeric:tabular-nums}
nav a.flag{color:var(--bad);border-left-color:var(--bad)}
main{background:var(--sheet);border:1px solid var(--rule);border-radius:4px;padding:48px 56px;min-width:0;overflow-wrap:break-word}
header.foil>div{min-width:0}
header.foil.nophoto{grid-template-columns:minmax(0,1fr)}
header.foil{display:grid;grid-template-columns:132px minmax(0,1fr);gap:28px;align-items:start;padding-bottom:28px}
header.foil img{width:132px;height:132px;object-fit:cover;border:1px solid var(--rule);border-radius:2px}
h1{font-size:34px;line-height:1.15;font-weight:800;letter-spacing:-.01em;margin:0 0 6px}
.who{color:var(--ink-2);margin:0 0 18px;max-width:60ch}
.verdict{font-size:19px;font-weight:600;margin:0}
.verdict.ok{color:var(--ok)} .verdict.bad{color:var(--bad)}
.mrz{grid-column:1/-1;margin-top:8px;padding:14px 16px;background:var(--paper);border:1px solid var(--rule);
  font:500 15px/1.45 'IBM Plex Mono',ui-monospace,monospace;letter-spacing:.14em;white-space:pre;overflow-x:auto;min-width:0;max-width:100%}
.legend{display:flex;flex-wrap:wrap;gap:6px 22px;font-size:13px;color:var(--ink-2);margin:4px 0 36px}
section{margin-top:40px}
h2{font-size:21px;font-weight:700;margin:0 0 4px}
.sub{font-size:14px;color:var(--ink-2);margin:0 0 12px}
table{width:100%;border-collapse:collapse;font-size:15px;table-layout:fixed}
thead{display:table-header-group}
th.q{width:34%}th.c{width:96px;white-space:nowrap}th.s{width:24%}
th{text-align:left;font-weight:600;font-size:13px;color:var(--ink-2);padding:6px 10px 6px 0;border-bottom:1px solid var(--ink)}
td{padding:9px 10px 9px 0;border-bottom:1px solid var(--rule);vertical-align:top}
td.q{color:var(--ink-2)} td.a{font-weight:600;overflow-wrap:break-word} td.c{white-space:nowrap}
td.s{font-size:12.5px;color:var(--ink-2);overflow-wrap:break-word}
.dots{letter-spacing:2px;color:var(--ok)} .dots.lo{color:var(--warn)}
tr.bad td.a{color:var(--bad)} .note{display:block;font-weight:400;font-size:13px;color:var(--bad)}
code{font:500 12px 'IBM Plex Mono',ui-monospace,monospace}
footer{margin-top:48px;padding-top:16px;border-top:1px solid var(--rule);font-size:13px;color:var(--ink-2);max-width:72ch}
@media screen and (max-width:860px){.wrap{grid-template-columns:minmax(0,1fr);padding:16px}nav{display:none}main{padding:24px 16px}
  header.foil{grid-template-columns:72px minmax(0,1fr);gap:14px}header.foil img{width:72px;height:72px}h1{font-size:26px}
  td.s,th.s{display:none}th.q{width:44%}th.c{width:84px}.dots{letter-spacing:0;font-size:12px}.mrz{font-size:10.5px;letter-spacing:.02em;padding:10px}.legend{font-size:12px}}
@media (prefers-reduced-motion:no-preference){.mrz{animation:print .9s steps(44) both}@keyframes print{from{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0)}}}
@page{size:Letter;margin:14mm 14mm 16mm}
@media print{:root{--paper:#fff;--sheet:#fff}body{background:#fff;font-size:11pt}.wrap{display:block;padding:0;max-width:none}
  nav{display:none}main{border:0;padding:0}section{margin-top:28px}h2,.sub{break-after:avoid}tr{break-inside:avoid}
  .mrz{animation:none;font-size:9.5pt;letter-spacing:.08em}td.s{font-size:8pt}th.q{width:32%}th.s{width:26%}
  header.foil{grid-template-columns:96px minmax(0,1fr)}header.foil img{width:96px;height:96px}}
"""


ISO3 = {"CHINA": "CHN", "USA": "USA", "UNITED STATES": "USA", "INDIA": "IND", "JAPAN": "JPN", "KOREA": "KOR"}


def _short_source(src: str) -> str:
    """raw/dir/Long file name.pdf#p1 -> Long file name.pdf p1 (full path stays in the tooltip)."""
    if src.startswith("raw/"):
        path, _, page = src[4:].partition("#")
        name = path.rsplit("/", 1)[-1]
        name = name if len(name) <= 34 else name[:22] + "…" + name[-10:]
        return f"{name} {page}".strip()
    return src if len(src) <= 40 else src[:38] + "…"


def _mrz_like(p_value, app_id: str) -> str:
    """Two 44-char lines in the visa MRZ alphabet: a recognisable signature, not a real travel document."""

    def clean(s: str) -> str:
        return "".join(c if c.isalnum() else "<" for c in str(s or "").upper())

    sur, given = clean(p_value("identity.name.surname")), clean(p_value("identity.name.given_names"))
    l1 = f"V<USA{sur}<<{given}".ljust(44, "<")[:44]
    dob = p_value("identity.date_of_birth")
    dob = dob.strftime("%y%m%d") if hasattr(dob, "strftime") else "<<<<<<"
    nat = ISO3.get(str(p_value("identity.nationality") or "").upper(), clean(p_value("identity.nationality"))[:3])
    visa = clean(str(p_value("app.purpose.visa_class") or "").split("-")[0])
    l2 = f"{clean(app_id)}<<{nat}{dob}{clean(p_value('identity.sex'))[:1]}<<{visa}".ljust(44, "<")[:44]
    return f"{l1}\n{l2}"


def _answer(c: Cell, rows: list[ReconRow], snapshot: dict) -> str:
    """What CEAC actually shows: dropdown display text beats codes; falls back to the sheet."""
    parts = []
    for r in rows:
        v = snapshot.get(r.id, {})
        shown = v.get("display") or v.get("value") or ""
        if shown and shown not in ("0", "1"):
            parts.append(shown)
    if parts in (["Y"], ["N"]):
        return "Yes" if parts == ["Y"] else "No"
    if c.expected == "" and not parts:
        return "Does not apply"
    if len(parts) == 3 and c.human and len(c.human) == 10 and c.human[4] == "-":  # a split date
        return dt.date.fromisoformat(c.human).strftime("%d %b %Y")
    return " ".join(parts) or c.human or (c.expected or "")


def render_html(
    spec: dict,
    cells: list[Cell],
    rows: list[ReconRow],
    snapshots: dict,
    profile_value,
    app_id: str,
    photo: Path | None,
    mask: bool = False,
) -> str:
    by_page: dict[str, list] = {}
    for c, r in zip(cells, rows):
        by_page.setdefault(c.page, []).append((c, r))
    total = len(cells)
    counts = {s: sum(r.status == s for r in rows[:total]) for s in STATUS_TEXT}
    review = sum(c.needs_review for c in cells)
    ready = counts["mismatch"] == counts["missing"] == counts["blocked"] == counts["not-captured"] == 0
    if ready and not review:
        verdict = f"All {counts['match']} answers match what CEAC holds. Nothing is blocking your signature."
    else:
        todo = [
            (counts["mismatch"] + counts["missing"], "differ from CEAC"),
            (counts["blocked"], "still unknown"),
            (review, "need your confirmation"),
            (counts["not-captured"], "not yet checked against CEAC"),
        ]
        parts = [f"{n} {'answer' if n == 1 else 'answers'} {what}" for n, what in todo if n]
        verdict = "Before you sign: " + ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1] + "."
    esc = html.escape
    name = f"{profile_value('identity.name.given_names') or ''} {profile_value('identity.name.surname') or ''}".strip()
    img = ""
    if photo and photo.exists():
        img = f'<img alt="Visa photo of {esc(name)}" src="data:image/jpeg;base64,{base64.b64encode(photo.read_bytes()).decode()}">'
    nav, secs = [], []
    for page in spec["pages"]:
        pairs = by_page.get(page["node"])
        if not pairs:
            continue
        snap = snapshots.get(page["node"], {}).get("values", {})
        logical = _logical(pairs)
        flagged = [c for c, st, _ in logical if st != "match" or c.needs_review]
        anchor = page["node"].lower()
        nav.append(
            f'<a href="#{anchor}" class="{"flag" if flagged else ""}"><span>{esc(page["title"])}</span>'
            f'<span class="n">{len(logical)}</span></a>'
        )
        trs = []
        for c, st, rs in logical:
            ans = _answer(c, rs, snap)
            if mask and c.sensitive and len(ans) > 4:
                ans = "•" * (len(ans) - 4) + ans[-4:]
            dots = CONF_DOTS.get(c.confidence, 0)
            note = (
                ""
                if st == "match"
                else f'<span class="note">{STATUS_TEXT.get(st, st)}'
                + (f": CEAC has {esc(rs[0].actual)}" if st == "mismatch" else "")
                + "</span>"
            )
            if c.needs_review:
                note += '<span class="note">Please confirm this default</span>'
            trs.append(
                f'<tr class="{"bad" if st != "match" else ""}"><td class="q">{esc(c.label or c.id)}</td>'
                f'<td class="a">{esc(ans)}{note}</td>'
                f'<td class="c" title="{esc(CONF_TEXT.get(c.confidence, c.confidence))}">'
                f'<span class="dots{" lo" if dots <= 1 else ""}">{"●" * dots}{"○" * (4 - dots)}</span></td>'
                f'<td class="s" title="{esc(c.source)}"><code>{esc(_short_source(c.source))}</code></td></tr>'
            )
        secs.append(
            f'<section id="{anchor}" aria-labelledby="h-{anchor}"><h2 id="h-{anchor}">{esc(page["title"])}</h2>'
            f'<p class="sub">{len(logical)} answers, {"all matching CEAC" if not flagged else f"{len(flagged)} to look at"}.</p>'
            f'<table><thead><tr><th scope="col" class="q">Question</th><th scope="col" class="a">Your answer</th>'
            f'<th scope="col" class="c">Confidence</th><th scope="col" class="s">Source of truth</th></tr></thead>'
            f"<tbody>{''.join(trs)}</tbody></table></section>"
        )
    now = dt.datetime.now().strftime("%d %b %Y, %H:%M")
    legend = "".join(
        f'<span><span class="dots{" lo" if CONF_DOTS[k] <= 1 else ""}">{"●" * CONF_DOTS[k]}'
        f"{'○' * (4 - CONF_DOTS[k])}</span> {v}</span>"
        for k, v in CONF_TEXT.items()
    )
    header_cls = "foil" if img else "foil nophoto"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>DS-160 review {esc(app_id)}</title>
<style>{CSS}</style></head><body><div class="wrap">
<nav aria-label="Sections">{"".join(nav)}</nav>
<main>
<header class="{header_cls}">{img}<div>
<h1>{esc(name)}</h1>
<p class="who">DS-160 application {esc(app_id)} for a {esc(VISA_NAMES.get(str(profile_value("app.purpose.visa_class")), str(profile_value("app.purpose.visa_class") or "")))} visa,
reviewed {now}. Read every answer below before you sign on ceac.state.gov.</p>
<p class="verdict {"ok" if ready and not review else "bad"}">{esc(verdict)}</p></div>
<div class="mrz" aria-label="Machine-readable summary">{esc(_mrz_like(profile_value, app_id))}</div></header>
<div class="legend" aria-label="Confidence scale">{legend}</div>
{"".join(secs)}
<footer>Generated by backhome from your documents in <code>raw/</code> and a live read-back of every CEAC page.
The source column says where each answer comes from. This is a review copy — only the application you sign on
ceac.state.gov counts.</footer>
</main></div></body></html>"""


def chrome_binary() -> str | None:
    for c in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "google-chrome",
        "chromium",
        "chromium-browser",
    ):
        if Path(c).exists() or shutil.which(c):
            return c
    return None


def to_pdf(html_path: Path, pdf_path: Path) -> Path:
    chrome = chrome_binary()
    if not chrome:
        raise RuntimeError("Chrome/Chromium not found; open the HTML and print to PDF manually")
    subprocess.run(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            "--virtual-time-budget=5000",
            html_path.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return pdf_path
