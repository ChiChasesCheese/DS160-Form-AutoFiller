"""Field validators (referenced by name from form specs) and cross-field profile checks.

A validator takes a value and returns None when valid, else a short error message.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Any, Callable

from .model import NA, SOURCE_RE, Confidence, Profile

Validator = Callable[[Any], "str | None"]
REGISTRY: dict[str, Validator] = {}


def validator(name: str):
    def deco(fn: Validator) -> Validator:
        REGISTRY[name] = fn
        return fn

    return deco


def _regex(name: str, pattern: str, hint: str) -> None:
    rx = re.compile(pattern)
    REGISTRY[name] = lambda v: None if v is not None and rx.fullmatch(str(v)) else f"{hint} (got {v!r})"


# ── simple format validators ────────────────────────────────────────────
_regex("cn_passport", r"E[A-HJ-NP-Z]?\d{7,8}|G\d{8}", "PRC passport: E+7-8 digits (optionally E+letter) or G+8 digits")
_regex("us_visa_foil", r"[A-Z]?\d{7,8}", "visa foil number: 8 chars in red, e.g. A1234567")
_regex("sevis_id", r"N\d{10}", "SEVIS ID: N + 10 digits")
_regex("i94", r"\d{9}[A-Z0-9]\d", "I-94 admission number: 11 chars")
_regex("uscis_receipt", r"(EAC|WAC|LIN|SRC|NBC|MSC|IOE|YSC|TSC|VSC|CSC)\d{10}", "USCIS receipt: 3 letters + 10 digits")
_regex("us_zip", r"\d{5}(-\d{4})?", "US ZIP: 12345 or 12345-6789")
_regex("email", r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", "email address")
_regex("phone_digits", r"\d{7,15}", "phone: digits only, 7-15 (CEAC strips punctuation)")
_regex("telecode", r"\d{4}( ?\d{4})*", "Chinese commercial code: 4 digits per character")
_regex("ceac_name", r"[A-Z][A-Z '\-]*", "CEAC name: UPPERCASE letters, space, hyphen, apostrophe")
_regex("ceac_address", r"[A-Z0-9][A-Z0-9 #&'(),./\-]{0,39}", "CEAC address line: <=40 chars, A-Z 0-9 # & ' ( ) , . / -")
_regex("yes_no", r"[YN]", "Y or N")
_regex("driver_license", r"[A-Z0-9]{4,20}", "driver license: alphanumeric, no spaces")


@validator("ssn")
def _ssn(v: Any) -> str | None:
    m = re.fullmatch(r"(\d{3})-?(\d{2})-?(\d{4})", str(v or ""))
    if not m:
        return f"SSN: 123-45-6789 (got {v!r})"
    a, g, s = m.groups()
    if a in ("000", "666") or a.startswith("9") or g == "00" or s == "0000":
        return "SSN: invalid area/group/serial"
    return None


PRC_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]


@validator("prc_id")
def _prc_id(v: Any) -> str | None:
    s = str(v or "").upper()
    if not re.fullmatch(r"\d{17}[\dX]", s):
        return f"PRC ID: 17 digits + digit/X (got {v!r})"
    check = "10X98765432"[sum(int(c) * w for c, w in zip(s, PRC_WEIGHTS)) % 11]
    return None if s[-1] == check else f"PRC ID checksum: expected last char {check}"


@validator("date")
def _date(v: Any) -> str | None:
    if isinstance(v, dt.date):
        return None
    try:
        dt.date.fromisoformat(str(v))
        return None
    except ValueError:
        return f"date must be ISO YYYY-MM-DD (got {v!r})"


@validator("past_date")
def _past(v: Any) -> str | None:
    return _date(v) or (None if _as_date(v) <= dt.date.today() else "date is in the future")


def _as_date(v: Any) -> dt.date:
    return v if isinstance(v, dt.date) else dt.date.fromisoformat(str(v))


# ── ICAO 9303 MRZ (TD3 passport) ────────────────────────────────────────
def mrz_check_digit(s: str) -> str:
    val = {**{str(i): i for i in range(10)}, **{chr(65 + i): 10 + i for i in range(26)}, "<": 0}
    return str(sum(val[c] * (7, 3, 1)[i % 3] for i, c in enumerate(s)) % 10)


def parse_mrz_line2(line: str) -> dict:
    """Return the fields of MRZ line 2 plus a list of failed check digits."""
    line = line.strip()
    if len(line) != 44:
        return {"errors": [f"MRZ line 2 must be 44 chars (got {len(line)})"]}
    f = {
        "number": line[0:9].rstrip("<"), "nationality": line[10:13],
        "dob": line[13:19], "sex": line[20], "expiry": line[21:27],
    }
    errors = []
    for name, data, cd in (("number", line[0:9], line[9]), ("dob", line[13:19], line[19]), ("expiry", line[21:27], line[27])):
        if mrz_check_digit(data) != cd:
            errors.append(f"MRZ {name} check digit mismatch")
    composite = line[0:10] + line[13:20] + line[21:43]
    if mrz_check_digit(composite) != line[43]:
        errors.append("MRZ composite check digit mismatch")
    f["errors"] = errors
    return f


def _yymmdd(d: dt.date) -> str:
    return d.strftime("%y%m%d")


# ── profile-level checks ────────────────────────────────────────────────
@dataclass
class Issue:
    level: str  # error | warn
    path: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.level.upper():5}] {self.path}: {self.msg}"


def check_profile(p: Profile, today: dt.date | None = None) -> list[Issue]:
    today = today or dt.date.today()
    issues: list[Issue] = []
    err = lambda path, msg: issues.append(Issue("error", path, msg))  # noqa: E731
    warn = lambda path, msg: issues.append(Issue("warn", path, msg))  # noqa: E731

    # provenance hygiene: every explicit source must parse; assumed/low facts are surfaced
    for path, fact in p.walk():
        if not SOURCE_RE.match(fact.source):
            warn(path, f"source reference not in grammar: {fact.source!r}")
        if fact.known and fact.confidence.needs_review:
            warn(path, f"confidence={fact.confidence.value}; confirm before submission")

    dob = p.value("identity.date_of_birth")
    sex = p.value("identity.sex")
    rid = p.value("identity.prc_national_id.number")
    if rid and rid != NA:
        if e := _prc_id(rid):
            err("identity.prc_national_id.number", e)
        elif dob and str(rid)[6:14] != _as_date(dob).strftime("%Y%m%d"):
            err("identity.prc_national_id.number", f"embedded birth date {str(rid)[6:14]} != date_of_birth {dob}")
        elif sex and ("M" if int(str(rid)[16]) % 2 else "F") != sex:
            err("identity.prc_national_id.number", "17th digit parity disagrees with sex")

    pp = "identity.passports.current"
    num, iss, exp = p.value(f"{pp}.number"), p.value(f"{pp}.issue_date"), p.value(f"{pp}.expiry_date")
    if num and (e := REGISTRY["cn_passport"](num)):
        err(f"{pp}.number", e)
    if iss and exp and _as_date(iss) >= _as_date(exp):
        err(pp, "issue_date must precede expiry_date")
    if exp and _as_date(exp) < today + dt.timedelta(days=183):
        warn(f"{pp}.expiry_date", "passport expires within 6 months")
    mrz = p.value(f"{pp}.mrz")
    if isinstance(mrz, list) and len(mrz) == 2:
        m = parse_mrz_line2(mrz[1])
        for e in m["errors"]:
            err(f"{pp}.mrz", e)
        if not m["errors"]:
            if num and m["number"] != num:
                err(f"{pp}.mrz", f"MRZ number {m['number']} != {num}")
            if dob and m["dob"] != _yymmdd(_as_date(dob)):
                err(f"{pp}.mrz", "MRZ birth date != identity.date_of_birth")
            if exp and m["expiry"] != _yymmdd(_as_date(exp)):
                err(f"{pp}.mrz", "MRZ expiry != expiry_date")
            if sex and m["sex"] != sex:
                err(f"{pp}.mrz", "MRZ sex != identity.sex")

    for part, native in (("surname", p.value("identity.name.native_surname")), ("given", p.value("identity.name.native_given"))):
        tele = p.value(f"identity.name.telecode_{part}")
        if native and tele:
            n_codes = len(str(tele).replace(" ", "")) // 4
            if n_codes != len(str(native)):
                err(f"identity.name.telecode_{part}", f"{len(str(native))} character(s) but {n_codes} code(s)")

    ssn = p.value("identity.us_ids.ssn")
    if ssn and ssn != NA and (e := _ssn(ssn)):
        err("identity.us_ids.ssn", e)

    for i, v in enumerate(p.value("us_immigration.visas", []) or []):
        base = f"us_immigration.visas[{i}]"
        if v.get("foil_number") and (e := REGISTRY["us_visa_foil"](v["foil_number"])):
            err(f"{base}.foil_number", e)
        if v.get("issue_date") and v.get("expiry_date") and _as_date(v["issue_date"]) >= _as_date(v["expiry_date"]):
            err(base, "visa issue_date must precede expiry_date")

    # travel history must alternate arrival/departure in date order
    hist = p.value("us_immigration.travel_history", []) or []
    for a, b in zip(hist, hist[1:]):
        if _as_date(a["date"]) > _as_date(b["date"]):
            err("us_immigration.travel_history", f"not sorted at {b['date']}")
        if a["type"] == b["type"]:
            warn("us_immigration.travel_history", f"two consecutive {a['type']} records ({a['date']}, {b['date']}) — missing record?")
    return issues


def run(name: str, value: Any) -> str | None:
    if name not in REGISTRY:
        return f"unknown validator {name!r}"
    return REGISTRY[name](value)


__all__ = ["REGISTRY", "Issue", "check_profile", "run", "parse_mrz_line2", "mrz_check_digit", "Confidence"]
