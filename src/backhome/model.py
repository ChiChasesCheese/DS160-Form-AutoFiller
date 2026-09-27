"""Fact model: every personal value carries a confidence and a source-of-truth reference.

Profile layout (a directory of YAML files, one namespace per file stem):

    identity.yaml     -> identity.name.surname, identity.passports.current.number, ...
    answers.yaml      -> overlay written by `backhome answer`; wins over every other file

A leaf is either a plain scalar (inherits the file's `_meta` defaults) or an explicit fact:

    number: {value: E12345678, confidence: high, source: "raw/ID/passport.pdf#p1"}

Source reference grammar (checked by `validate`):
    raw/<path>[#p<page>]   an ingested document (the preferred source of truth)
    user:<YYYY-MM-DD>      stated by the user in chat / questionnaire
    ceac:<node>            read back from a CEAC page snapshot
    derived:<how>          computed from other facts (say how)
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

import yaml


class Confidence(str, Enum):
    VERIFIED = "verified"  # official document AND independently confirmed (2nd doc, CEAC echo, user)
    HIGH = "high"  # text-extracted from an official document
    MEDIUM = "medium"  # visual/OCR read, or computed from documents
    USER = "user"  # stated by the user, no document behind it
    LOW = "low"  # inference from indirect evidence
    ASSUMED = "assumed"  # agent default with no evidence — must be confirmed before submission

    @property
    def needs_review(self) -> bool:
        return self in (Confidence.LOW, Confidence.ASSUMED)


FACT_KEYS = {"value", "confidence", "source", "note"}
SOURCE_RE = re.compile(r"^(raw/[^#]+(#p\d+(-\d+)?)?|user:\d{4}-\d{2}-\d{2}|ceac:\w+|derived:.+)$")
ANSWERS_FILE = "answers.yaml"
NA = "__NA__"  # explicit "Does Not Apply" (distinct from null = unknown)


@dataclass(frozen=True)
class Fact:
    value: Any
    confidence: Confidence
    source: str
    note: str | None = None

    @property
    def known(self) -> bool:
        return self.value is not None

    def to_yaml(self) -> dict:
        d = {"value": self.value, "confidence": self.confidence.value, "source": self.source}
        if self.note:
            d["note"] = self.note
        return d


def is_fact_node(node: Any) -> bool:
    return isinstance(node, dict) and {"value", "source"} <= set(node) and set(node) <= FACT_KEYS


def _split(path: str) -> list[str | int]:
    parts: list[str | int] = []
    for tok in re.split(r"\.|\[(\d+)\]", path):
        if tok is None or tok == "":
            continue
        parts.append(int(tok) if tok.isdigit() else tok)
    return parts


def _join(parts: list[str | int]) -> str:
    out = ""
    for p in parts:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else p)
    return out


class Profile:
    """Read-only view over a profile directory with an answers overlay."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.docs: dict[str, Any] = {}
        self.meta: dict[str, dict] = {}
        for f in sorted(self.root.glob("*.yaml")):
            if f.name == ANSWERS_FILE:
                continue
            data = yaml.safe_load(f.read_text()) or {}
            self.meta[f.stem] = data.pop("_meta", {}) if isinstance(data, dict) else {}
            self.docs[f.stem] = data
        answers = self.root / ANSWERS_FILE
        self.answers: dict[str, dict] = (yaml.safe_load(answers.read_text()) or {}) if answers.exists() else {}

    def mount(self, ns: str, path: Path) -> "Profile":
        """Attach an extra YAML file as namespace `ns` (e.g. an application's own facts as `app`)."""
        data = yaml.safe_load(Path(path).read_text()) or {}
        self.meta[ns] = data.pop("_meta", {})
        self.docs[ns] = data
        return self

    # ── lookup ──────────────────────────────────────────────────────────
    def get(self, path: str) -> Fact | None:
        parts = _split(path)
        # answers overlay: the longest answered prefix wins (answering `app.us_contact` covers its children)
        for n in range(len(parts), 0, -1):
            key = _join(parts[:n])
            if key in self.answers:
                return self._descend(self.answers[key], parts[n:], ns=None, start=0)
        return self._descend(self.docs, parts, ns=str(parts[0]), start=1)

    def _descend(self, node: Any, parts: list, ns: str | None, start: int) -> Fact | None:
        inherited: Fact | None = self._provenance(node, None) if start == 0 else None
        if start == 0 and parts and is_fact_node(node):
            node = node["value"]
        for i, p in enumerate(parts):
            if i >= start:
                inherited = self._provenance(node, inherited)
                if is_fact_node(node):
                    node = node["value"]
            if isinstance(node, dict) and p in node:
                node = node[p]
            elif isinstance(node, list) and isinstance(p, int) and p < len(node):
                node = node[p]
            else:
                return None
        if is_fact_node(node) or inherited is None:
            return self._fact(node, ns=ns)
        return Fact(node, inherited.confidence, inherited.source, inherited.note)

    @staticmethod
    def _provenance(node: Any, inherited: Fact | None) -> Fact | None:
        if isinstance(node, dict) and "source" in node and ("confidence" in node or is_fact_node(node)):
            return Fact(None, Confidence(node.get("confidence", "medium")), node["source"], node.get("note"))
        return inherited

    def value(self, path: str, default: Any = None) -> Any:
        f = self.get(path)
        return f.value if f and f.known else default

    def _fact(self, node: Any, ns: str | None) -> Fact:
        if is_fact_node(node):
            return Fact(node["value"], Confidence(node.get("confidence", "medium")), node["source"], node.get("note"))
        meta = self.meta.get(ns or "", {})
        return Fact(
            node,
            Confidence(meta.get("confidence", "medium")),
            meta.get("source", f"derived:profile/{ns}.yaml (no per-field source)"),
        )

    def walk(self) -> Iterator[tuple[str, Fact]]:
        """Yield every leaf fact as (dotted.path, Fact); answers overlay last."""

        def rec(node: Any, path: str, ns: str, inh: Fact | None):
            if is_fact_node(node):
                inh = self._provenance(node, inh)
                if not isinstance(node["value"], (dict, list)) or not node["value"]:
                    yield path, self._fact(node, ns)
                    return
                node = node["value"]
            if not isinstance(node, (dict, list)):
                yield path, (Fact(node, inh.confidence, inh.source, inh.note) if inh else self._fact(node, ns))
            elif isinstance(node, dict):
                inh = self._provenance(node, inh)
                for k, v in node.items():
                    if k not in FACT_KEYS or not ("source" in node and "confidence" in node):
                        yield from rec(v, f"{path}.{k}", ns, inh)
            else:
                for i, v in enumerate(node):
                    yield from rec(v, f"{path}[{i}]", ns, inh)

        def shadowed(path: str) -> bool:  # overridden by an answer on itself or an ancestor
            return any(path == k or path.startswith((k + ".", k + "[")) for k in self.answers)

        for ns, doc in self.docs.items():
            yield from ((p, f) for p, f in rec(doc, ns, ns, None) if not shadowed(p))
        for path, node in self.answers.items():
            yield path, self._fact(node, None)

    # ── mutation (answers overlay only; profile files are edited by humans/agents) ──
    def answer(self, path: str, value: Any, source: str | None = None,
               confidence: Confidence = Confidence.USER, note: str | None = None) -> Fact:
        src = source or f"user:{dt.date.today().isoformat()}"
        if not SOURCE_RE.match(src):
            raise ValueError(f"bad source reference: {src!r}")
        fact = Fact(value, confidence, src, note)
        self.answers[path] = fact.to_yaml()
        (self.root / ANSWERS_FILE).write_text(
            "# Answers overlay (written by `backhome answer`). Wins over every other profile file.\n"
            + yaml.safe_dump(dict(sorted(self.answers.items())), allow_unicode=True, sort_keys=False)
        )
        return fact
