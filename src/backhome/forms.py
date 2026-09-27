"""Stage 3-5: form spec + profile -> sheet (expected value per field) -> recon against live snapshots.

Spec (YAML, see forms/ds160/spec.yaml) = ordered pages; each page lists fields:

    - id: tbxAPP_SURNAME            # CEAC element id without the ASP.NET prefix
      label: Surnames
      from: identity.name.surname   # profile path (or `const:` / `derive:`)
      type: text                    # text|select|yesno|checkbox|date|split|list   (default text)
      check: ceac_name              # validator name(s) from validators.REGISTRY
      map: {M: M, F: F}             # profile value -> CEAC option code (select)
      na: cbexAPP_SSN_NA            # "Does Not Apply" checkbox ticked when the value is null/NA
      when: app.previous_visa       # only include when this path is truthy
      sensitive: true               # masked in overview/questionnaire
      ask: "父亲的拼音姓名？"          # questionnaire prompt when the value is missing or assumed

Sheet cell = one CEAC element: page, id, label, expected (CEAC value), human, confidence, source, error, ask, path.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .model import NA, Confidence, Fact, Profile
from .validators import run as run_validator

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


@dataclass
class Cell:
    page: str
    id: str
    label: str
    expected: str | None  # value CEAC should hold; None = unknown (blocking)
    human: str = ""
    confidence: str = ""
    source: str = ""
    error: str = ""  # validator message, if any
    ask: str = ""
    path: str = ""
    sensitive: bool = False
    group: str = ""  # questionnaire/overview grouping key (spec `group:`, list item, or path)

    @property
    def blocking(self) -> bool:
        return self.expected is None

    @property
    def needs_review(self) -> bool:
        return self.confidence in (Confidence.ASSUMED.value, Confidence.LOW.value)


# ── spec ────────────────────────────────────────────────────────────────
def load_spec(path: Path) -> dict:
    spec = yaml.safe_load(Path(path).read_text())
    seen: set[tuple[str, str]] = set()
    for page in spec["pages"]:
        for f in page.get("fields", []):
            for fid in _ids(f):
                key = (page["node"], fid)
                if key in seen:
                    raise ValueError(f"duplicate field id {fid} on page {page['node']}")
                seen.add(key)
    return spec


def _ids(f: dict) -> list[str]:
    if f.get("type") == "date":
        return list(f["ids"])
    if f.get("type") == "list":
        return [sub["id"] for sub in f["item"]]
    if f.get("type") == "split":
        return list(f["ids"]) + ([f["na"]] if f.get("na") else [])
    return [f["id"]] + ([f["na"]] if f.get("na") else [])


# ── value formatting ────────────────────────────────────────────────────
def _as_date(v: Any) -> dt.date | None:
    if v in (None, "", NA):
        return None
    return v if isinstance(v, dt.date) else dt.date.fromisoformat(str(v))


def _fmt_day(d: dt.date, fmt: str) -> str:
    return f"{d.day:02d}" if fmt == "num2" else str(d.day)


def _fmt_month(d: dt.date, fmt: str) -> str:
    return {"MMM": MONTHS[d.month - 1], "num2": f"{d.month:02d}"}.get(fmt, str(d.month))


def _to_ceac(f: dict, value: Any) -> str:
    t = f.get("type", "text")
    if t == "yesno":
        if isinstance(value, bool):
            return "Y" if value else "N"
        return str(value).upper()[:1]
    if t == "checkbox":
        return "1" if value else "0"
    if t == "select":
        m = f.get("map")
        return str(m.get(value, value)) if m else str(value)
    s = str(value)
    return s if f.get("keep_case") else s.upper()


# ── resolution ──────────────────────────────────────────────────────────
def _resolve(f: dict, p: Profile, ctx: dict | None) -> Fact | None:
    if "const" in f:
        return Fact(f["const"], Confidence(f.get("confidence", "high")), f.get("source", "derived:form rule"))
    key = f.get("from")
    if key is None:
        return None
    if ctx is not None:  # inside a list item: relative key into the item dict
        item, parent = ctx["item"], ctx["fact"]
        v = item if key == "." else _dig(item, key)  # "." = the item itself (list of scalars)
        own = item if isinstance(item, dict) else {}
        conf = Confidence(own.get("confidence", parent.confidence.value))
        return Fact(v, conf, own.get("source", parent.source))
    return p.get(key)


def _dig(node: Any, dotted: str) -> Any:
    for k in dotted.split("."):
        node = node.get(k) if isinstance(node, dict) else None
    return node


def _truthy(p: Profile, path: str) -> bool:
    neg = path.startswith("!")
    v = p.value(path.lstrip("!"))
    ok = bool(v) and v != NA and str(v).upper() not in ("N", "NO", "FALSE")
    return not ok if neg else ok


def build_sheet(spec: dict, p: Profile) -> list[Cell]:
    cells: list[Cell] = []
    for page in spec["pages"]:
        node = page["node"]
        if page.get("when") and not _truthy(p, page["when"]):
            continue
        for f in page.get("fields", []):
            if f.get("when") and not _truthy(p, f["when"]):
                continue
            cells.extend(_cells(node, f, p, ctx=None))
    return cells


def _cells(node: str, f: dict, p: Profile, ctx: dict | None) -> Iterator[Cell]:
    t = f.get("type", "text")
    if t == "list":
        yield from _list_cells(node, f, p)
        return
    fact = _resolve(f, p, ctx)
    base = dict(
        page=node,
        label=f.get("label", ""),
        ask=f.get("ask", ""),
        path=f.get("from", ""),
        sensitive=bool(f.get("sensitive")),
        group=f.get("group", ""),
    )
    idx = ctx["i"] if ctx else 0
    fid = lambda s: s.format(i=idx)  # noqa: E731
    if fact is not None:
        base.update(confidence=fact.confidence.value, source=fact.source)
    value = fact.value if fact is not None else None
    if value is None and not f.get("required", True):
        return

    if t == "date":
        d = _as_date(value)
        day_id, mon_id, yr_id = (fid(i) for i in f["ids"])
        if d is None:
            for cid in (day_id, mon_id, yr_id):
                yield Cell(id=cid, expected=None, **base)
            return
        human = d.isoformat()
        err = run_validator(f["check"], d) if f.get("check") else None
        yield Cell(id=day_id, expected=_fmt_day(d, f.get("day", "num")), human=human, error=err or "", **base)
        yield Cell(id=mon_id, expected=_fmt_month(d, f.get("month", "num")), human=human, **base)
        yield Cell(id=yr_id, expected=str(d.year), human=human, **base)
        return

    if t == "split":  # one value spread over several inputs, e.g. "123-45-6789" -> 123 | 45 | 6789
        if f.get("na"):
            yield Cell(id=fid(f["na"]), expected=None if value is None else ("1" if value == NA else "0"), **base)
        parts = None if value in (None, NA) else str(value).split(f.get("sep", "-"))
        err = "" if parts is None else _check(f, value)
        for j, cid in enumerate(f["ids"]):
            exp = None if value is None else ("" if parts is None else parts[j])
            yield Cell(id=fid(cid), expected=exp, human="" if parts is None else str(value), error=err, **base)
        return

    if f.get("na"):
        is_na = value == NA
        if value is None:  # unknown ≠ does-not-apply; stays blocking
            yield Cell(id=fid(f["id"]), expected=None, **base)
            return
        yield Cell(id=fid(f["na"]), expected="1" if is_na else "0", human="Does Not Apply" if is_na else "", **base)
        yield Cell(
            id=fid(f["id"]),
            expected="" if is_na else _to_ceac(f, value),
            human="" if is_na else str(value),
            error="" if is_na else _check(f, value),
            **base,
        )
        return

    if value is None:
        yield Cell(id=fid(f["id"]), expected=None, **base)
        return
    yield Cell(id=fid(f["id"]), expected=_to_ceac(f, value), human=_human(value), error=_check(f, value), **base)


def _list_cells(node: str, f: dict, p: Profile) -> Iterator[Cell]:
    fact = p.get(f["from"])
    items = (fact.value if fact and fact.known else None) or []
    if fact is None or not fact.known:
        yield Cell(
            page=node,
            id=f["item"][0]["id"].format(i=0),
            label=f.get("label", ""),
            expected=None,
            ask=f.get("ask", ""),
            path=f["from"],
        )
        return
    for i, _ in enumerate(items[: f.get("max", 99)]):
        item_fact = p.get(f"{f['from']}[{i}]")  # honours item-level answers overlay
        ctx = {"i": i, "item": item_fact.value, "fact": item_fact}
        for sub in f["item"]:
            sub = {**sub, "label": f"{f.get('label', '')} #{i + 1} {sub.get('label', '')}".strip()}
            for c in _cells(node, sub, p, ctx):
                c.path = f"{f['from']}[{i}].{sub.get('from', '')}"
                c.group = c.group or f"{f['from']}[{i}]"
                c.ask = c.ask or f.get("ask", "")
                yield c


def _check(f: dict, value: Any) -> str:
    checks = f.get("check") or []
    for name in [checks] if isinstance(checks, str) else checks:
        target = _to_ceac(f, value) if name.startswith("ceac_") else value
        if err := run_validator(name, target):
            return err
    return ""


def _human(v: Any) -> str:
    if isinstance(v, bool):
        return "Yes" if v else "No"
    return str(v)


# ── persistence ─────────────────────────────────────────────────────────
CELL_FIELDS = [f.name for f in Cell.__dataclass_fields__.values()]


def write_sheet(cells: list[Cell], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, CELL_FIELDS, delimiter="\t")
        w.writeheader()
        for c in cells:
            row = asdict(c)
            row["expected"] = "<UNKNOWN>" if c.expected is None else c.expected
            w.writerow(row)


# ── snapshots & recon ───────────────────────────────────────────────────
def read_snapshot(path: Path) -> dict:
    """Parse a snapshot.js TSV: '#key=value' headers then 'id<TAB>value<TAB>display' rows."""
    meta, values = {}, {}
    for line in Path(path).read_text().splitlines():
        if line.startswith("#"):
            k, _, v = line[1:].partition("=")
            meta[k] = v
        elif line.strip():
            parts = line.split("\t") + ["", ""]
            values[parts[0]] = {"value": parts[1], "display": parts[2]}
    return {"meta": meta, "values": values}


def _norm(v: str) -> str:
    return re.sub(r"\s+", " ", (v or "").strip()).upper()


def _same(expected: str, actual: str) -> bool:
    if _norm(expected) == _norm(actual):
        return True
    if expected.isdigit() and actual.isdigit():  # day/month dropdowns: "6" vs "06"
        return int(expected) == int(actual)
    return False


@dataclass
class ReconRow:
    page: str
    id: str
    label: str
    status: str  # match | mismatch | missing | not-captured | blocked | unspecced
    expected: str
    actual: str
    confidence: str
    source: str


def recon(cells: list[Cell], snapshots: dict[str, dict]) -> list[ReconRow]:
    rows: list[ReconRow] = []
    spec_ids: dict[str, set] = {}
    for c in cells:
        spec_ids.setdefault(c.page, set()).add(c.id)
        snap = snapshots.get(c.page)
        exp = "" if c.expected is None else c.expected
        if c.expected is None:
            status, actual = "blocked", (snap["values"].get(c.id, {}).get("value", "") if snap else "")
        elif snap is None:
            status, actual = "not-captured", ""
        elif c.id not in snap["values"]:
            status, actual = "missing", ""
        else:
            actual = snap["values"][c.id]["value"]
            status = "match" if _same(exp, actual) else "mismatch"
        rows.append(ReconRow(c.page, c.id, c.label, status, exp, actual, c.confidence, c.source))
    for page, snap in snapshots.items():  # fields on the live page that the spec doesn't know = spec drift
        for fid, v in snap["values"].items():
            if fid not in spec_ids.get(page, set()) and v["value"] not in ("", "0"):
                rows.append(ReconRow(page, fid, "", "unspecced", "", v["value"], "", ""))
    return rows


def load_snapshots(folder: Path) -> dict[str, dict]:
    return {f.stem: read_snapshot(f) for f in sorted(Path(folder).glob("*.tsv"))}


# ── questionnaire ───────────────────────────────────────────────────────
@dataclass
class Question:
    qid: str
    path: str
    prompt: str
    pages: list[str] = field(default_factory=list)
    kind: str = "missing"  # missing | confirm
    items: list[str] = field(default_factory=list)
    confidence: str = ""
    source: str = ""


def questionnaire(cells: list[Cell], groups: dict[str, str] | None = None) -> list[Question]:
    groups = groups or {}
    by_key: dict[str, Question] = {}
    for c in cells:
        if not (c.blocking or c.needs_review):
            continue
        key = c.group or c.path or f"{c.page}.{c.id}"
        q = by_key.get(key)
        if q is None:
            q = by_key[key] = Question(
                qid="",
                path=c.path or key,
                prompt=groups.get(key) or c.ask or c.label or c.id,
                kind="missing" if c.blocking else "confirm",
                confidence=c.confidence,
                source=c.source,
            )
        if c.blocking:
            q.kind = "missing"
        if c.page not in q.pages:
            q.pages.append(c.page)
        item = f"{c.label}: " + ("?" if c.blocking else ("•••" if c.sensitive else c.human or c.expected or ""))
        if c.label and item not in q.items:
            q.items.append(item)
        if c.group:
            q.path = c.group
    qs = [q for q in by_key.values() if q.kind == "missing"] + [q for q in by_key.values() if q.kind == "confirm"]
    for i, q in enumerate(qs, 1):
        q.qid = f"Q{i}"
    return qs


# ── overview (human report) ─────────────────────────────────────────────
ICON = {"match": "✅", "mismatch": "❌", "missing": "⚠️", "not-captured": "·", "blocked": "⛔", "unspecced": "❔"}


def _mask(c: Cell, v: str) -> str:
    if not (c.sensitive and v):
        return v
    return "•" * len(v) if len(v) <= 4 else v[:2] + "•" * (len(v) - 4) + v[-2:]


WORST = ["mismatch", "missing", "blocked", "not-captured", "match"]


def _logical(pairs: list[tuple[Cell, ReconRow]]) -> list[tuple[Cell, str, list[ReconRow]]]:
    """Collapse the CEAC cells of one logical field (date parts, SSN parts, NA box) into one row."""
    rows: dict[tuple, tuple[Cell, list[ReconRow]]] = {}
    for c, r in pairs:
        key = (c.label, c.path)
        if key not in rows:
            rows[key] = (c, [])
        rows[key][1].append(r)
        if c.human and not rows[key][0].human:
            rows[key] = (c, rows[key][1])
    out = []
    for c, rs in rows.values():
        status = min((r.status for r in rs), key=lambda s: WORST.index(s) if s in WORST else 0)
        out.append((c, status, rs))
    return out


def overview(spec: dict, cells: list[Cell], rows: list[ReconRow], qs: list[Question], app_id: str) -> str:
    by_page: dict[str, list[tuple[Cell, ReconRow]]] = {}
    for c, r in zip(cells, rows):
        by_page.setdefault(c.page, []).append((c, r))
    extra = [r for r in rows[len(cells) :]]
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    out = [
        f"# {spec['form'].upper()} {app_id} — overview",
        "",
        f"_Generated {now} by `backhome overview`. Never edit by hand; regenerate._",
        "",
        "Legend: ✅ CEAC matches sheet · ❌ mismatch · ⚠️ field absent on live page · ⛔ value unknown (see questionnaire) · "
        "· page not captured yet. Confidence: verified > high > medium ≈ user > low > assumed.",
        "",
        "| # | Section | Status | Fields | ✅ | ❌ | ⛔ | needs review |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for n, page in enumerate(spec["pages"], 1):
        pairs = by_page.get(page["node"], [])
        if not pairs:
            continue
        st = [r.status for _, r in pairs]
        review = sum(c.needs_review for c, _ in pairs)
        done = all(s == "match" for s in st)
        status = (
            "✅ done"
            if done and not review
            else "🟡 done, review"
            if done
            else ("⛔ blocked" if "blocked" in st else "❌ fix" if "mismatch" in st or "missing" in st else "· todo")
        )
        out.append(
            f"| {n} | {page['title']} | {status} | {len(pairs)} | {st.count('match')} | "
            f"{st.count('mismatch') + st.count('missing')} | {st.count('blocked')} | {review} |"
        )
    for page in spec["pages"]:
        pairs = by_page.get(page["node"], [])
        if not pairs:
            continue
        out += [
            "",
            f"## {page['title']}  (`{page['node']}`)",
            "",
            "| | Field | Value | Confidence | Source of truth |",
            "|---|---|---|---|---|",
        ]
        for c, status, rs in _logical(pairs):
            val = "⛔ unknown" if c.blocking else _mask(c, c.human or c.expected or "")
            for r in rs:
                if r.status == "mismatch":
                    val += f" (CEAC has `{_mask(c, r.actual)}`)"
            conf = f"**{c.confidence}**" if c.needs_review else c.confidence
            out.append(f"| {ICON[status]} | {c.label or c.id} | {val} | {conf} | `{c.source}` |")
    if extra:
        out += ["", "## Spec drift (on the live page, not in the spec)", ""]
        out += [f"- `{r.page}.{r.id}` = `{r.actual}`" for r in extra]
    if qs:
        out += ["", f"## Open questions ({len(qs)}) — see QUESTIONNAIRE.md", ""]
        out += [f"- **{q.qid}** [{q.kind}] {q.prompt.splitlines()[0][:90]} → `{q.path}`" for q in qs]
    return "\n".join(out) + "\n"


def questionnaire_md(qs: list[Question], app_id: str) -> str:
    lines = [
        f"# Questionnaire — {app_id}",
        "",
        "Answer any way you like; the agent persists each answer with its source:",
        "",
        "1. **Reply in chat** — e.g. `Q1: ZHANG WEI, 1970-03-12, No`",
        "2. **Drop a document** into `raw/inbox/` (户口本, birth certificate, old passport, …) and say so",
        "3. **CLI** — `backhome answer <path> <value>`",
        "",
        "`missing` = the form cannot proceed without it. `confirm` = the agent filled a default; say *ok* or correct it.",
        "",
    ]
    for q in qs:
        lines += [
            f"### {q.qid} · {q.prompt}",
            "",
            f"- key: `{q.path}` · pages: {', '.join(q.pages)} · kind: **{q.kind}**"
            + (f" · now: confidence {q.confidence}, source `{q.source}`" if q.kind == "confirm" else ""),
        ]
        if len(q.items) > 1 or q.kind == "confirm":
            lines += [f"  - {it}" for it in q.items]
        lines += ["- answer: ", ""]
    return "\n".join(lines)
