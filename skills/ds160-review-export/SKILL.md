---
name: ds160-review-export
description: Export the complete DS-160 as CEAC will submit it — walk every page of the CEAC Review section in the user's Chrome, capture it, reconcile it against the backhome sheet, run the pre-submission checklist (community "refusal points" + consistency rules), and produce ceac_review.pdf + PREFLIGHT.md. Use when the user asks to print/export/review the whole DS-160, check it before submitting, or "stop right before submission". Never signs or submits.
---

# DS-160 review export (backhome)

Commands run from the repo root. APP = application id (e.g. AA00XXXXXX).

## Hard rules
- Stop at **Review ▸ Location** / the SIGN tab. Never click "Sign and Submit Application", never solve captchas.
- Never press CEAC's own **Print** button: it opens the OS print dialog, which freezes browser automation.
- Do not POST page content anywhere but the backhome loopback receiver (and only after `/ping` answers
  `backhome-receiver`). Default path is the chunked read below, which needs no network at all.

## Steps
1. **Session.** CEAC session is bound to a tab. If there is none: open `https://ceac.state.gov/GenNIV/Default.aspx`
   in the Claude tab group; the user selects the location and types the captcha, clicks *Retrieve an Application*;
   you fill Application ID, first 5 letters of surname, birth year, security answer (see `application.yaml`).
2. **Enter Review.** Click the REVIEW tab (or the sidebar "Personal/Address/Phone/Passport").
3. **Capture each page** (8 pages: ReviewPersonal, ReviewTravel, ReviewUSContact, ReviewFamily,
   ReviewWorkEducation, ReviewSecurity, ReviewTemporaryWork, ReviewLocation). One `browser_batch` per page:
   - real-click the page's **Next** button (coordinates from JS: `input[type=submit]` whose value starts with
     `Next`, `scrollIntoView`, scale by screenshot width / `innerWidth`; `find` also works but costs a model call);
   - `window.__rev = (<src/backhome/ceac/review_extract.js>)(); window.__rev.length`;
   - read `window.__rev.slice(i, i+900)` until exhausted (tool output truncates ~1 kB);
   - write the text verbatim to `data/applications/<APP>/ceac_review/<node>.tsv` (node = `#node=` header).
4. **Reconcile + print:** `uv run backhome ceac-review <APP>` → per page "found N/N answers"; anything missing
   means CEAC holds something else — go back to the form page, fix, re-snapshot, re-capture.
5. **Checklist:** `uv run backhome run <APP>` → `PREFLIGHT.md`. Every ❌ must be fixed; every 👀 is shown to the
   user as a question (use the questionnaire flow: reply in chat or drop files in `raw/inbox/`, persist with
   `backhome answer`).
6. **Hand over:** give the user `ceac_review.pdf`, `review.pdf`, `PREFLIGHT.md`; tell them the next click
   (Sign) is theirs, then update the appointment barcode if they rebooked (新预约系统预约后不能换表).
