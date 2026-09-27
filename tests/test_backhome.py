"""Tests run against the synthetic applicant in examples/ (never against real data)."""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import pytest
import yaml

from backhome import docs, forms
from backhome.cli import FORMS_DIR
from backhome.model import Confidence, Profile
from backhome.validators import check_profile, mrz_check_digit, parse_mrz_line2, run

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "data"
SPEC = FORMS_DIR / "ds160" / "spec.yaml"


@pytest.fixture
def home(tmp_path: Path) -> Path:
    shutil.copytree(EXAMPLE, tmp_path / "data")
    return tmp_path


@pytest.fixture
def profile(home: Path) -> Profile:
    return Profile(home / "data" / "profile").mount("app", home / "data/applications/DEMO0000001/application.yaml")


def _edit(home: Path, rel: str, fn) -> None:
    p = home / "data" / "profile" / rel
    d = yaml.safe_load(p.read_text())
    fn(d)
    p.write_text(yaml.safe_dump(d, allow_unicode=True))


# ── validators ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "name,value,ok",
    [
        ("prc_id", "110105199003071239", True),
        ("prc_id", "110105199003071238", False),  # bad checksum
        ("prc_id", "11010519900307123", False),  # too short
        ("cn_passport", "EA1234567", True),
        ("cn_passport", "E12345678", True),
        ("cn_passport", "12345678", False),
        ("us_visa_foil", "A1234567", True),
        ("uscis_receipt", "IOE0123456789", True),
        ("uscis_receipt", "IOE012345678", False),
        ("ssn", "123-45-6789", True),
        ("ssn", "666-12-3456", False),
        ("i94", "123456789A1", True),
        ("us_zip", "95134", True),
        ("us_zip", "9513", False),
        ("ceac_name", "MARY-ANN O'NEIL", True),
        ("ceac_name", "Li", False),  # CEAC wants upper case
        ("ceac_address", "100 MAIN ST APT 2", True),
        ("ceac_address", "X" * 41, False),  # CEAC max 40
        ("telecode", "2621", True),
        ("past_date", dt.date(2999, 1, 1), False),
    ],
)
def test_field_validators(name, value, ok):
    assert (run(name, value) is None) is ok


def test_mrz_roundtrip():
    line = "E123456782CHN9003071M3302141<<<<<<<<<<<<<<00"
    m = parse_mrz_line2(line)
    assert m["errors"] == [] and m["number"] == "E12345678" and m["dob"] == "900307"
    assert parse_mrz_line2(line[:9] + "9" + line[10:])["errors"]  # corrupted check digit is caught
    assert mrz_check_digit("<" * 14) == "0"


def test_example_profile_is_clean(profile):
    assert [i for i in check_profile(profile) if i.level == "error"] == []


def test_cross_field_checks_catch_inconsistency(home):
    _edit(
        home,
        "identity.yaml",
        lambda d: d.__setitem__("date_of_birth", {"value": "1991-03-07", "confidence": "high", "source": "raw/x.pdf"}),
    )
    errors = [str(i) for i in check_profile(Profile(home / "data/profile")) if i.level == "error"]
    assert any("embedded birth date" in e for e in errors)  # PRC ID digits disagree
    assert any("MRZ birth date" in e for e in errors)  # MRZ disagrees


def test_telecode_count_mismatch(home):
    _edit(
        home,
        "identity.yaml",
        lambda d: d["name"].__setitem__(
            "telecode_given", {"value": "24942494", "confidence": "high", "source": "derived:x"}
        ),
    )
    assert any("telecode_given" in i.path for i in check_profile(Profile(home / "data/profile")) if i.level == "error")


# ── model ───────────────────────────────────────────────────────────────
def test_fact_provenance(profile):
    f = profile.get("identity.passports.current.number")
    assert (f.value, f.confidence, f.source) == ("E12345678", Confidence.VERIFIED, "raw/passport.pdf#p1")
    plain = profile.get("identity.place_of_birth.city")  # plain scalar inherits _meta
    assert plain.confidence == Confidence.MEDIUM and plain.source == "raw/passport.pdf#p1"
    assert profile.get("identity.passports.current.mrz[1]").confidence == Confidence.MEDIUM  # inherited into list
    assert profile.get("nope.nothing") is None


def test_answers_overlay_wins_and_persists(home):
    p = Profile(home / "data/profile")
    p.answer("family.father.surname", "LI", source="user:2026-09-27")
    again = Profile(home / "data/profile")
    f = again.get("family.father.surname")
    assert (f.value, f.confidence, f.source) == ("LI", Confidence.USER, "user:2026-09-27")
    again.answer("family.mother", {"given_names": "FANG", "date_of_birth": dt.date(1965, 1, 2)})
    m = Profile(home / "data/profile").get("family.mother.date_of_birth")  # prefix answer covers children
    assert m.value == dt.date(1965, 1, 2) and m.confidence == Confidence.USER
    with pytest.raises(ValueError):
        again.answer("family.father.surname", "LI", source="my memory")  # not a valid source reference


# ── forms: sheet / recon / questionnaire ────────────────────────────────
def test_spec_loads_and_ids_are_unique():
    spec = forms.load_spec(SPEC)
    assert spec["pages"][0]["node"] == "Personal1"


def test_sheet_formats(profile):
    cells = {(c.page, c.id): c for c in forms.build_sheet(forms.load_spec(SPEC), profile)}
    assert cells[("Personal1", "ddlDOBDay")].expected == "07"  # num2
    assert cells[("Personal1", "ddlDOBMonth")].expected == "MAR"  # MMM
    assert cells[("Personal1", "ddlAPP_POB_CNTRY")].expected == "CHIN"  # mapped select
    assert cells[("Personal1", "rblTelecodeQuestion")].expected == "Y"
    assert cells[("Personal2", "cbexAPP_SSN_NA")].expected == "1"  # Does Not Apply ticked
    assert cells[("Personal2", "tbxAPP_SSN1")].expected == ""
    assert cells[("PptVisa", "ddlPPT_ISSUED_DTEMonth")].expected == "02"
    assert cells[("Relatives", "tbxFATHER_SURNAME")].blocking  # unknown stays unknown
    assert cells[("Relatives", "tbxMOTHER_SURNAME")].expected == "WANG"


def test_recon_statuses(profile, home):
    spec = forms.load_spec(SPEC)
    cells = forms.build_sheet(spec, profile)
    snap = home / "data/applications/DEMO0000001/snapshots/Personal1.tsv"
    snap.write_text(snap.read_text().replace("BEIJING", "BEIJNG", 1))  # a typo made on the live form
    snaps = forms.load_snapshots(snap.parent)
    by = {(r.page, r.id): r.status for r in forms.recon(cells, snaps)}
    assert by[("Personal1", "tbxAPP_SURNAME")] == "match"
    assert by[("Personal1", "tbxAPP_POB_CITY")] == "mismatch"  # BEIJNG typo in the snapshot
    assert by[("Personal2", "ddlAPP_NATL")] == "not-captured"
    assert by[("Relatives", "tbxFATHER_SURNAME")] == "blocked"


def test_questionnaire_groups_and_orders(profile):
    spec = forms.load_spec(SPEC)
    qs = forms.questionnaire(forms.build_sheet(spec, profile), spec["groups"])
    father = next(q for q in qs if q.path == "family.father")
    assert father.kind == "missing" and len(father.items) == 4  # 4 inputs -> 1 question
    kinds = [q.kind for q in qs]
    assert kinds == sorted(kinds, key=lambda k: k != "missing")  # missing before confirm
    history = next(q for q in qs if q.path == "declarations.history")
    assert history.kind == "missing"  # one unknown member makes the whole group blocking
    assert any("lost a passport" in it and it.endswith(": N") for it in history.items)  # assumed member shown


def test_overview_masks_sensitive(profile):
    spec = forms.load_spec(SPEC)
    cells = forms.build_sheet(spec, profile)
    md = forms.overview(spec, cells, forms.recon(cells, {}), [], "DEMO")
    assert "110105199003071239" not in md and "11••••••••••••••39" in md


# ── docs: ingest / verify / digest ──────────────────────────────────────
def test_ingest_idempotent_and_tamper_evident(tmp_path):
    src = tmp_path / "src"
    (src / "ID").mkdir(parents=True)
    (src / "ID" / "a.txt").write_text("passport E12345678")
    raw = tmp_path / "raw"
    assert docs.ingest([src], raw)["copied"] == 1
    assert docs.ingest([src], raw)["unchanged"] == 1
    (src / "ID" / "a.txt").write_text("changed upstream")
    assert docs.ingest([src], raw)["conflict"] == 1  # kept side by side, never overwritten
    (raw / "inbox" / "hukou.txt").write_text("father: LI GANG")
    assert docs.ingest([], raw)["registered"] == 1  # user drop picked up
    assert docs.verify(raw) == []
    (raw / "ID" / "a.txt").write_text("tampered")
    assert docs.verify(raw) == ["modified: ID/a.txt"]


def test_digest_text(tmp_path):
    raw = tmp_path / "raw"
    (raw / "inbox").mkdir(parents=True)
    (raw / "inbox" / "note.txt").write_text("mother: WANG FANG 1965-01-02")
    index = docs.digest(raw, tmp_path / "digest")
    assert index[0]["status"] == "text"
    assert "WANG FANG" in (tmp_path / "digest" / "inbox" / "note.txt.txt").read_text()


# ── photo ───────────────────────────────────────────────────────────────
def test_photo_crop_geometry_meets_rules():
    from backhome.photo import EYES_FROM_BOTTOM, HEAD_RANGE, plan_crop

    c = plan_crop(2104, 2275, hair=353, eyes=994, chin=1672)
    head, eyes = c.ratios(353, 994, 1672)
    assert c.side <= 2104 and c.top + c.side <= 2275
    assert HEAD_RANGE[0] <= head <= HEAD_RANGE[1] and EYES_FROM_BOTTOM[0] <= eyes <= EYES_FROM_BOTTOM[1]
    with pytest.raises(ValueError):
        plan_crop(500, 500, hair=10, eyes=300, chin=490)  # head fills the frame: cannot reach <= 69%


def test_photo_render_and_check(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    from backhome.photo import check, plan_crop, render

    src = tmp_path / "in.jpg"
    Image.new("RGB", (1500, 1800), (240, 240, 236)).save(src)
    c = plan_crop(1500, 1800, hair=500, eyes=780, chin=1300)
    info = render(src, c, tmp_path / "out.jpg", size=900)
    assert info["bytes"] <= 240 * 1024
    assert check(tmp_path / "out.jpg", 500, 780, 1300, c) == []


# ── pipeline + review ───────────────────────────────────────────────────
def test_pipeline_on_example(home):
    from backhome.pipeline import run

    stages = {s.name: s for s in run(home, "DEMO0000001", SPEC, pdf=False)}
    assert stages["raw integrity"].status == "skip"  # no documents in the example
    assert stages["validate profile"].status in ("ok", "warn")
    assert stages["recon vs CEAC"].status == "warn"  # unchecked pages + open questions, no mismatch
    html = (home / "data/applications/DEMO0000001/review.html").read_text()
    assert "MING LI" in html and "V&lt;USALI&lt;&lt;MING" in html and "<script" not in html


# ── CEAC review export + preflight ──────────────────────────────────────
def test_ceac_review_coverage_detects_drift(profile, tmp_path):
    from backhome import ceac_review

    spec = forms.load_spec(SPEC)
    cells = forms.build_sheet(spec, profile)
    page = tmp_path / "ReviewPersonal.tsv"
    rows = "\n".join(
        [
            "#node=ReviewPersonal",
            "#title=Non-Immigrant Visa - Review Personal",
            "## Personal Information",
            "Name Provided\tLI, MING",
            "Full Name in Native Alphabet\t李明",
            "Telecode Name\t2621, 2494",
            "Sex\tMALE",
            "Marital Status\tSINGLE",
            "Date of Birth\t07 MARCH 1990, Edit Address and Phone Information",
            "Country/Region of Birth\tBEIJING, BEIJING, CHINA",
            "National Identification Number\t110105199003071239",
            "## Passport",
            "Passport/Travel Document Number\tE12345678",
            "Issuance Date\t15 FEBRUARY 2023",
            "Expiration Date\t14 FEBRUARY 2033",
            "City where issued\tBEIJING",
        ]
    )
    page.write_text(rows)
    pages = ceac_review.load(tmp_path)
    assert pages["ReviewPersonal"].sections[0][1][-3][1] == "07 MARCH 1990"  # trailing Edit link stripped
    cov = {c.node: c for c in ceac_review.coverage(pages, cells, {})}["ReviewPersonal"]
    assert cov.checked > 5 and not [m for m in cov.missing if m[1] in ("Surnames", "Passport Number", "Date of Birth")]
    page.write_text(rows.replace("E12345678", "E12345679"))  # CEAC holds a different passport number
    cov = {c.node: c for c in ceac_review.coverage(ceac_review.load(tmp_path), cells, {})}["ReviewPersonal"]
    assert any(label == "Passport Number" for _, label, _ in cov.missing)
    assert "CEAC review export" in ceac_review.render(ceac_review.load(tmp_path), [cov], "DEMO")


def test_preflight_rules_run_on_example(profile):
    from backhome import preflight

    spec = forms.load_spec(SPEC)
    cells = forms.build_sheet(spec, profile)
    findings = {f.rule: f for f in preflight.run(profile, cells, forms.recon(cells, {}))}
    assert len([r for r in findings if r.startswith("P")]) == 22
    assert findings["P02"].status == "pass"  # LI / MING matches the example MRZ
    assert findings["P11"].status == "pass"
    assert findings["P22"].status == "fail"  # nothing reconciled against CEAC in the example
    assert all(f.status in ("pass", "warn", "fail", "manual", "skip") for f in findings.values())
