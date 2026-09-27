---
name: ds160-autofill
description: Fill a DS-160 (US nonimmigrant visa application, ceac.state.gov) in the user's real Chrome from the backhome profile, page by page, with a snapshot + recon + overview after every section, and a questionnaire whenever data is missing. Use when the user asks to continue/fill/check their DS-160, or mentions CEAC, an application ID like AA00XXXXXX, or visa application pages. Never signs or submits.
---

# DS-160 autofill (backhome)

Repo: the backhome checkout (commands run from its root). Data: `data/profile/*.yaml` (facts with
confidence + source), `data/applications/<APP_ID>/` (application.yaml, snapshots/, sheet.tsv, recon.tsv,
OVERVIEW.md, QUESTIONNAIRE.md). Spec: `src/backhome/forms/ds160/spec.yaml`.

## Hard rules
- **Never** click *Sign* / *Submit* / *Sign and Submit Application*; never solve the captcha. Those are the user's.
- The captcha appears on retrieve/start. Ask the user to retrieve the app **inside the Claude tab group**
  (a CEAC session is bound to its tab; deep links in a new tab bounce to `Default.aspx`).
- Only enter values that exist in the sheet (`backhome sheet <APP>`). Unknown → questionnaire, not a guess.
- CEAC times out after 20 min idle; if you will be away longer, Save first.

## The loop (one section at a time)
1. `uv run backhome sheet <APP>` → expected CEAC value for every element of the current page.
   Stop if a cell on this page is `<UNKNOWN>`: run step 6 instead.
2. Fill the page (Claude in Chrome `javascript_tool` to set values; see *CEAC quirks*).
3. Click **Next** with a real mouse click (`find` → `computer.left_click` with the ref).
   If the page re-renders with "Please correct all areas in error", read the errors and fix.
4. Go back to the page (sidebar) and snapshot it: run `src/backhome/ceac/snapshot.js` as
   `window.__snap = (<file contents>)(); window.__snap.length`, then read `window.__snap.slice(i, i+900)`
   until done (tool output truncates ~1k chars). Save verbatim to
   `data/applications/<APP>/snapshots/<node>.tsv` (node = the `#node=` header).
5. `uv run backhome recon <APP>` → must print no MISMATCH/MISSING for this page. Fix and repeat if it does.
   Then tell the user the section overview (the row from OVERVIEW.md + anything `needs review`).
6. Blocked (value unknown) → show the relevant questions from `QUESTIONNAIRE.md` and ask the user to either
   reply in chat or drop documents into `raw/inbox/`. Persist every answer immediately:
   `uv run backhome answer <path> <value> [--typed] [--source user:YYYY-MM-DD]`; for dropped files run
   `uv run backhome ingest && uv run backhome digest`, read them, and write facts with `source: raw/<path>`.
   Then continue at step 1.
7. For pages marked `ids_verified: false` in the spec, snapshot the page first, replace `TBD_*` ids with the
   real ones (keep the `from:` mapping), and commit the spec change — that is how the spec learns.

## Photo (optional, only when the user asks)
1. Look at the image (Read tool), note three y pixel rows in the source: top of hair, eye line, bottom of chin.
2. `uv run backhome photo <img> --hair Y --eyes Y --chin Y --out data/photo/ds160.jpg` → must print "compliant".
3. CEAC "Upload Your Photo" redirects to identix.state.gov: the user must allow that site in the extension.
   Use `file_upload` on the file input (never click it), then accept the tool's result page only if it passes.

## Finish
`uv run backhome run <APP>` → give the user `review.pdf` and the verdict line. Review and Sign stay with the user.

## CEAC quirks (learned the hard way)
- `element.click()` on Save/Next is ignored → always a real `computer.left_click`.
- "Add Another" links and many Yes/No radios `__doPostBack`; values typed before a postback survive it.
  Set No-radios that postback via `.checked = true` (no new fields to reveal) to save round trips.
- Date dropdown option values differ per page (`6` vs `06`, `5` vs `05` vs `MAY`): the spec's `day`/`month`
  formats encode what each page uses; select by option **text** when unsure and read it back.
- Setting a `<select>` programmatically can clear a sibling textbox (social media id) → type with real keys.
- `navigate` is blocked by the "Leave site?" guard on dirty pages; the sidebar links still work (real click).
  Sidebar coordinates: `src/backhome/ceac/nav.js`; scale by screenshot width / `innerWidth`.
- Sections unlock sequentially; you cannot skip past an incomplete page.
- A `<select>` that reveals more fields (e.g. Primary Occupation) does **not** react to JS `change`,
  `onchange()` or `__doPostBack`: set the value, then real-click **Save** — the page re-renders with the fields.
- "Do Not Know"/NA checkboxes set via `.checked = true` are **not persisted**; real-click them. Recon catches this.
- Unchecking an NA box re-renders its textbox: re-`find` the textbox before typing.
- Security & Background parts 1-5 are only Yes/No radios: once the user confirmed "all No", tick every visible
  `*_1` radio, then real-click Next; snapshot each part.
- The tool's output filter blocks results that look like `KEY=VALUE` lists or contain `__doPostBack` hrefs:
  emit JSON / `a : b` pairs and never print `href`s.
- The last section's Next goes to PHOTO: use **Save** there and stop. Photo, Review, Sign are the user's.
