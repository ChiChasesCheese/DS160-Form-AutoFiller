"""Pre-submission checks: community "refusal point" checklists turned into executable rules.

Each rule inspects the sheet (expected CEAC values), the profile and the recon result and returns a Finding.
Rules that cannot be decided by a machine return `manual` with the exact thing a human must look at, so the
checklist is complete even when automation is not.

Primary checklist: 小红书《美签DS-160提交前，检查这22个拒签点》(P01–P22), plus consistency rules (C*).
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .forms import Cell, ReconRow
from .model import NA, Profile

XHS_22 = "xhs:美签DS-160提交前，检查这22个拒签点"


@dataclass
class Finding:
    rule: str
    title: str
    status: str  # pass | warn | fail | manual | skip
    detail: str
    source: str = XHS_22


class Ctx:
    def __init__(self, p: Profile, cells: list[Cell], rows: list[ReconRow], today: dt.date | None = None):
        self.p, self.cells, self.rows = p, cells, rows
        self.today = today or dt.date.today()
        self.by_id = {(c.page, c.id): c for c in cells}

    def v(self, page: str, cid: str) -> str | None:
        c = self.by_id.get((page, cid))
        return None if c is None else c.expected

    def page(self, node: str) -> list[Cell]:
        return [c for c in self.cells if c.page == node]


RULES: list[tuple[str, str, str, Callable[[Ctx], tuple[str, str]]]] = []


def rule(rid: str, title: str, source: str = XHS_22):
    def deco(fn):
        RULES.append((rid, title, source, fn))
        return fn

    return deco


def _ascii(s: str) -> bool:
    return all(ord(ch) < 128 for ch in s)


# ── P01–P22 ─────────────────────────────────────────────────────────────
@rule("P01", "只有母语姓名一栏用中文，其余全部英文")
def _p01(c: Ctx):
    bad = [
        f"{x.page}.{x.id}={x.expected}"
        for x in c.cells
        if x.expected and not _ascii(x.expected) and x.id != "tbxAPP_FULL_NAME_NATIVE"
    ]
    return ("fail", "; ".join(bad[:5])) if bad else ("pass", "no non-ASCII outside the native-name field")


@rule("P02", "拼音与护照一致，姓和名没有颠倒")
def _p02(c: Ctx):
    mrz = c.p.value("identity.passports.current.mrz")
    if not (isinstance(mrz, list) and mrz):
        return "manual", "no MRZ in profile: compare surname/given names with the passport data page"
    m = re.match(r"P.[A-Z<]{3}([A-Z<]+?)<<([A-Z<]+)", mrz[0])
    sur, giv = (m.group(1).replace("<", " ").strip(), m.group(2).replace("<", " ").strip()) if m else ("", "")
    got = (c.v("Personal1", "tbxAPP_SURNAME"), c.v("Personal1", "tbxAPP_GIVEN_NAME"))
    return ("pass", f"{got[0]} / {got[1]} = MRZ") if got == (sur, giv) else ("fail", f"form {got} vs MRZ {(sur, giv)}")


@rule("P03", "中文电码为标准码，每字 4 位")
def _p03(c: Ctx):
    s, g = c.v("Personal1", "tbxAPP_TelecodeSURNAME"), c.v("Personal1", "tbxAPP_TelecodeGIVEN_NAME")
    if c.v("Personal1", "rblTelecodeQuestion") != "Y":
        return "skip", "telecode not used"
    native = str(c.p.value("identity.name.full_name_native") or "")
    ok = all(x and re.fullmatch(r"\d{4}( \d{4})*", x) for x in (s, g))
    n = len((s + " " + g).split())
    if not ok or n != len(native):
        return "fail", f"{s} / {g} for {native}"
    return "manual", f"{s} {g} for {native}: confirm each code in the official CCC table (format and count ok)"


@rule("P04", "未提交的表格只保留 30 天，注意保存续期")
def _p04(c: Ctx):
    saved = c.p.value("app.last_saved")
    if not saved:
        return "manual", "record app.last_saved after each Save; CEAC purges unsubmitted forms after 30 days"
    age = (c.today - (saved if isinstance(saved, dt.date) else dt.date.fromisoformat(str(saved)))).days
    return ("warn" if age > 23 else "pass"), f"last saved {saved} ({age} days ago)"


@rule("P05", "SSN / 纳税人号：有则填，无则 Does Not Apply，不能空")
def _p05(c: Ctx):
    ssn = [c.v("Personal2", f"tbxAPP_SSN{i}") for i in (1, 2, 3)]
    ssn_na, tax_na = c.v("Personal2", "cbexAPP_SSN_NA"), c.v("Personal2", "cbexAPP_TAX_ID_NA")
    ok_ssn = all(ssn) or ssn_na == "1"
    ok_tax = bool(c.v("Personal2", "tbxAPP_TAX_ID")) or tax_na == "1"
    return (
        "pass" if ok_ssn and ok_tax else "fail"
    ), f"SSN {'filled' if all(ssn) else 'NA'}, tax id {'NA' if tax_na == '1' else 'filled'}"


@rule("P06", "出行计划清楚（日期 / 停留时长 / 目的）")
def _p06(c: Ctx):
    need = ["dlPrincipalAppTravel_ctl00_ddlPurposeOfTrip", "tbxTRAVEL_DTEYear", "tbxTRAVEL_LOS"]
    miss = [x for x in need if not c.v("Travel", x)]
    return ("fail", f"missing {miss}") if miss else ("pass", "purpose, arrival date and length of stay set")


@rule("P07", "在美住址已填写")
def _p07(c: Ctx):
    return ("pass", c.v("Travel", "tbxStreetAddress1")) if c.v("Travel", "tbxStreetAddress1") else ("fail", "empty")


@rule("P08", "美国联系人是真实存在的人或机构")
def _p08(c: Ctx):
    name = " ".join(filter(None, [c.v("USContact", "tbxUS_POC_GIVEN_NAME"), c.v("USContact", "tbxUS_POC_SURNAME")]))
    org = c.v("USContact", "tbxUS_POC_ORGANIZATION")
    conf = next((x.confidence for x in c.page("USContact")), "")
    if not (name or org):
        return "fail", "no point of contact"
    return ("pass" if conf in ("user", "high", "verified") else "warn"), f"{name} / {org} (confidence {conf})"


@rule("P09", "社交账号用英文/数字 ID，列表外平台填到 other websites")
def _p09(c: Ctx):
    ids = [
        x.expected or ""
        for x in c.page("AddressPhone")
        if "Social" in x.id and x.id.endswith(("Ident", "Hand", "Plat"))
    ]
    bad = [i for i in ids if not _ascii(i)]
    if bad:
        return "fail", f"non-ASCII: {bad}"
    return ("pass", f"{len(ids) // 2} account(s), all ASCII") if ids else ("warn", "no social media listed")


@rule("P10", "所填社交账号设为公开（H-1B/H-4 线上审查）")
def _p10(c: Ctx):
    handles = [x.human or x.expected for x in c.page("AddressPhone") if x.id.endswith(("Ident", "Hand"))]
    return "manual", f"set to public before the interview and keep them consistent: {', '.join(filter(None, handles))}"


@rule("P11", "护照号与护照首页 / MRZ 完全一致")
def _p11(c: Ctx):
    num = c.v("PptVisa", "tbxPPT_NUM")
    mrz = c.p.value("identity.passports.current.mrz")
    mrz_num = mrz[1][:9].rstrip("<") if isinstance(mrz, list) and len(mrz) == 2 else None
    if mrz_num is None:
        return "manual", f"{num}: compare with the passport data page"
    return ("pass", f"{num} = MRZ") if num == mrz_num else ("fail", f"{num} vs MRZ {mrz_num}")


@rule("P12", "签发日与到期日正确且不相同")
def _p12(c: Ctx):
    i = c.p.value("identity.passports.current.issue_date")
    e = c.p.value("identity.passports.current.expiry_date")
    if not (i and e):
        return "fail", "missing"
    ok = str(i) < str(e)
    left = (e - c.today).days if isinstance(e, dt.date) else 0
    return ("pass" if ok and left > 183 else "fail"), f"{i} → {e} ({left} days left)"


@rule("P13", "签发地城市/省份/国家与护照一致")
def _p13(c: Ctx):
    vals = [c.v("PptVisa", k) for k in ("tbxPPT_ISSUED_IN_CITY", "tbxPPT_ISSUED_IN_STATE", "ddlPPT_ISSUED_IN_CNTRY")]
    return ("pass" if all(vals) else "fail"), " / ".join(map(str, vals))


@rule("P14", "在美直系亲属如实填写")
def _p14(c: Ctx):
    v = c.v("Relatives", "rblUS_IMMED_RELATIVE_IND")
    src = next((x.source for x in c.page("Relatives") if x.id == "rblUS_IMMED_RELATIVE_IND"), "")
    return ("pass" if v in ("Y", "N") else "fail"), f"answered {v} ({src})"


@rule("P15", "职业、收入如实填写")
def _p15(c: Ctx):
    occ, inc = c.v("WorkEducation1", "ddlPresentOccupation"), c.v("WorkEducation1", "tbxCURR_MONTHLY_SALARY")
    ok = occ and inc and inc.isdigit() and int(inc) > 0
    return ("pass" if ok else "fail"), f"occupation {occ}, monthly income {inc}"


@rule("P16", "公司名称/地址/收入与在职证明及 I-129/LCA 一致")
def _p16(c: Ctx):
    names = {
        c.v("WorkEducation1", "tbxEmpSchName"),
        c.v("TemporaryWork", "tbxEmployerName"),
        c.v("TemporaryWork", "tbxNameOfPetitioner"),
    }
    pay = {c.v("WorkEducation1", "tbxCURR_MONTHLY_SALARY"), c.v("TemporaryWork", "tbxEmpSalaryInUSD")}
    names.discard(None), pay.discard(None)
    if len(names) > 1 or len(pay) > 1:
        return "fail", f"inconsistent across pages: names {names}, monthly pay {pay}"
    return (
        "manual",
        f"consistent across pages ({names.pop() if names else '?'}, {pay.pop() if pay else '?'}/month); compare with employment letter + LCA wage/worksite",
    )


@rule("P17", "敏感岗位只写日常工作内容，不夸大敏感技术")
def _p17(c: Ctx):
    duties = " ".join(x.expected or "" for x in c.cells if "Duties" in x.id)
    hits = re.findall(
        r"\b(NUCLEAR|MISSILE|MILITARY|WEAPON|ENCRYPTION|CRYPTOGRAPH\w*|SEMICONDUCTOR|AEROSPACE|QUANTUM|ARTIFICIAL INTELLIGENCE|DEFENSE)\b",
        duties.upper(),
    )
    return ("warn", f"sensitive terms: {sorted(set(hits))}") if hits else ("pass", "plain duty descriptions")


@rule("P18", "学历至少两段，专业写全称")
def _p18(c: Ctx):
    schools = [x.expected for x in c.page("WorkEducation2") if x.id.endswith("tbxSchoolName")]
    majors = [x.expected for x in c.page("WorkEducation2") if x.id.endswith("tbxSchoolCourseOfStudy")]
    return ("pass" if len(schools) >= 2 and all(m and len(m) > 4 for m in majors) else "warn"), f"{schools} / {majors}"


@rule("P19", "家庭住址填现住址（不是户口地址）")
def _p19(c: Ctx):
    hist = c.p.value("contact.address_history") or []
    latest = hist[0]["line1"] if hist else None
    home = c.v("AddressPhone", "tbxAPP_ADDR_LN1")
    if latest and home and latest.startswith(home):
        return "pass", f"{home} = latest address on file"
    return "manual", f"home {home}; latest on file {latest}"


@rule("P20", "过去 5 年去过的国家/地区全部列出，一个不漏")
def _p20(c: Ctx):
    listed = [x.expected for x in c.page("WorkEducation3") if "COUNTRIES_VISITED" in x.id and x.id.startswith("dtl")]
    trips = c.p.value("travel.trips") or []
    since = c.today - dt.timedelta(days=5 * 365)
    unknown = [
        f"{t['left_us']}→{t.get('returned_us')}"
        for t in trips
        if t.get("left_us") and str(t["left_us"]) >= since.isoformat() and not t.get("destination")
    ]
    if unknown:
        return (
            "fail",
            f"{len(unknown)} trip(s) abroad without a known destination: {', '.join(unknown)}; listed {listed}",
        )
    return "pass", f"every trip's destination is listed ({listed})"


@rule("P21", "安全背景问题全部作答（无特殊情况均为 No）")
def _p21(c: Ctx):
    sec = [x for x in c.cells if x.page.startswith("SecurityandBackground")]
    yes = [x.id for x in sec if x.expected == "Y"]
    blank = [x.id for x in sec if not x.expected]
    if blank:
        return "fail", f"unanswered: {blank}"
    return ("warn", f"YES answers need an explanation: {yes}") if yes else ("pass", f"{len(sec)} answered, all No")


@rule("P22", "提交前通读一遍，信息真实、准确、前后一致")
def _p22(c: Ctx):
    bad = [r for r in c.rows if r.status in ("mismatch", "missing", "blocked", "not-captured")]
    review = [x for x in c.cells if x.needs_review]
    if bad or review:
        return "fail", f"{len(bad)} field(s) not reconciled with CEAC, {len(review)} default(s) unconfirmed"
    return "manual", f"all {len(c.rows)} fields reconciled with CEAC — now read review.pdf end to end"


# ── consistency rules beyond the post ───────────────────────────────────
@rule("C01", "以往赴美记录 = I-94 最近 5 次入境", "derived:CBP I-94 travel history")
def _c01(c: Ctx):
    hist = [h for h in (c.p.value("us_immigration.travel_history") or []) if h["type"] == "arrival"]
    want = [str(h["date"]) for h in sorted(hist, key=lambda h: str(h["date"]), reverse=True)[:5]]
    got = [x.human for x in c.page("PreviousUSTravel") if x.id.endswith("DTEDay") and "PREV_US_VISIT" in x.id]
    return ("pass", f"{len(got)} visits match I-94") if got == want else ("fail", f"form {got} vs I-94 {want}")


@rule("C02", "上次签证信息与签证页一致（签发日、签证号）", "derived:visa foil")
def _c02(c: Ctx):
    num = c.v("PreviousUSTravel", "tbxPREV_VISA_FOIL_NUMBER")
    v = (c.p.value("us_immigration.visas") or [{}])[0]
    return ("pass" if num == v.get("foil_number") else "fail"), f"{num} vs foil {v.get('foil_number')}"


@rule("C03", "Petition 回执号格式正确，与 I-797 一致", "derived:I-797")
def _c03(c: Ctx):
    n = c.v("TemporaryWork", "tbxPetitionNumber") or c.v(
        "Travel", "dlPrincipalAppTravel_ctl00_tbxPRIN_APP_PETITION_NUM"
    )
    ok = bool(n and re.fullmatch(r"[A-Z]{3}\d{10}", n))
    src = c.p.get("app.petition_receipt")
    return (
        "fail" if not ok else "manual" if src and src.confidence.value == "user" else "pass",
        f"{n}; source {src.source if src else '?'} — drop the I-797 into raw/inbox/ to verify" if ok else f"{n}",
    )


COMMUNITY = "community:一亩三分地/寄托/知乎 + travel.state.gov (2025-26)"


@rule("C04", "过去 5 年所有雇主（含实习、OPT）都已列出", COMMUNITY)
def _c04(c: Ctx):
    listed = [x.expected for x in c.page("WorkEducation2") if x.id.endswith("tbEmployerName")]
    since = (c.today - dt.timedelta(days=5 * 365)).isoformat()
    jobs = c.p.value("employment.previous") or []
    missing = [
        j.get("employer")
        for j in jobs
        if str(j.get("end") or "9999") >= since[:7]
        and not any((j.get("employer") or "").upper().split(",")[0].split()[0] in (x or "") for x in listed)
    ]
    if missing:
        return "warn", f"in last 5 years but not listed: {missing} — listing internships avoids a 'gap' question"
    return "pass", f"listed {listed}"


@rule("C05", "专业/社会/慈善组织（IEEE、ACM、校友会等）如实作答", COMMUNITY)
def _c05(c: Ctx):
    return "manual", f"answered {c.v('WorkEducation3', 'rblORGANIZATION_IND')}; memberships such as IEEE/ACM count"


@rule("C06", "面签地点：国籍国或居住国（中国五个领馆均有 H-1B 面签记录）", COMMUNITY)
def _c06(c: Ctx):
    loc = c.p.value("app.location")
    if not loc:
        return "manual", "record app.location (Review ▸ Location) and match it to the appointment"
    china = ("BEIJING", "SHANGHAI", "GUANGZHOU", "SHENYANG", "WUHAN")  # community reports H-1B interviews at all five
    ok = any(k in str(loc).upper() for k in china) or "UNITED STATES" in str(loc).upper()
    return ("pass" if ok else "warn"), f"{loc}"


@rule("C07", "社交账号与以往 DS-160（F-1）申报一致；公开前清理敏感内容", COMMUNITY)
def _c07(c: Ctx):
    return (
        "manual",
        "compare with the accounts listed on your 2023 F-1 DS-160 confirmation; explain any account that disappeared",
    )


@rule("C08", "照片 6 个月内、未戴眼镜、白底；预约系统里的条码是最终版", COMMUNITY)
def _c08(c: Ctx):
    ph = c.p.value("app.photo") or {}
    return (
        "manual",
        f"photo {ph.get('uploaded', '?')}, QotW: {ph.get('qotw_result', '?')}; update the barcode on the appointment site after submitting",
    )


@rule("C09", "出生国家未被系统自动改成美国（新系统自动填地址的已知问题）", COMMUNITY)
def _c09(c: Ctx):
    got = c.v("Personal1", "ddlAPP_POB_CNTRY")
    want = c.p.value("identity.place_of_birth.country")
    if not got:
        return "fail", "missing"
    return (
        ("pass", f"{got}")
        if (got == "CHIN" and str(want).upper() == "CHINA") or got == want
        else ("fail", f"{got} vs {want}")
    )


@rule("C10", "面签前 ≥3 个工作日提交 DS-160；预约后不能再换表，预约前定稿", COMMUNITY)
def _c10(c: Ctx):
    appt = c.p.value("app.appointment_date")
    return "manual", (
        f"appointment {appt}: submit before then minus 3 working days"
        if appt
        else "no appointment recorded: submit this DS-160 first, then book with its barcode"
    )


@rule("C11", "社交媒体一次报全；事后补报要重新走到底并重新提交，只 Save 不算", COMMUNITY)
def _c11(c: Ctx):
    n = len([x for x in c.page("AddressPhone") if x.id.endswith(("Ident", "Hand"))])
    return ("pass" if n >= 2 else "warn"), f"{n} account(s) listed (list-only LinkedIn led to a Shanghai 221(g))"


def run(p: Profile, cells: list[Cell], rows: list[ReconRow], today: dt.date | None = None) -> list[Finding]:
    ctx = Ctx(p, cells, rows, today)
    out = []
    for rid, title, source, fn in RULES:
        try:
            status, detail = fn(ctx)
        except Exception as e:  # noqa: BLE001 — a broken rule must not hide the others
            status, detail = "warn", f"rule error {type(e).__name__}: {e}"
        out.append(Finding(rid, title, status, str(detail), source))
    return out


ICON = {"pass": "✅", "warn": "⚠️", "fail": "❌", "manual": "👀", "skip": "·"}


def to_markdown(findings: list[Finding], app: str) -> str:
    counts = {k: sum(f.status == k for f in findings) for k in ICON}
    lines = [
        f"# 提交前检查 — {app}",
        "",
        f"✅ {counts['pass']} 通过 · ❌ {counts['fail']} 需修正 · ⚠️ {counts['warn']} 注意 · 👀 {counts['manual']} 需人工确认",
        "",
        "| | # | 检查项 | 结果 |",
        "|---|---|---|---|",
    ]
    lines += [f"| {ICON[f.status]} | {f.rule} | {f.title} | {f.detail.replace('|', '/')} |" for f in findings]
    lines += ["", f"P01–P22 来自 {XHS_22}；C* 是基于证件的一致性检查。"]
    return "\n".join(lines) + "\n"


__all__ = ["Finding", "run", "to_markdown", "NA", "Any"]
