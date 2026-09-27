# backhome — agent notes

Personal immigration paperwork as an engineering pipeline:
**raw docs → digest → sourced facts → form sheet → fill in real Chrome → snapshot → recon → overview/questionnaire.**

## Commands (run from repo root)
```bash
uv sync                                   # install (Python ≥3.11)
uv run pytest -q                          # 33 tests, synthetic data only (examples/)
uv run backhome ingest <src>...           # copy docs into raw/ (+MANIFEST.tsv); idempotent
uv run backhome verify-raw                # raw/ untouched? (sha256)
uv run backhome digest [--ocr]            # data/digest/*.txt + INDEX.tsv (needs-vision = read it yourself)
uv run backhome validate [--all]          # 0 errors required; --all lists facts needing review
uv run backhome recon <APP_ID>            # sheet.tsv, recon.tsv, OVERVIEW.md, QUESTIONNAIRE.md
uv run backhome answer <path> <value> [--typed] [--source user:YYYY-MM-DD]
BACKHOME_HOME=examples uv run backhome recon DEMO0000001   # demo on the fake applicant
```

## Layout
- `src/backhome/model.py` — `Fact{value, confidence, source}`, `Profile` (YAML dir + `answers.yaml` overlay + `mount("app", …)`)
- `src/backhome/validators.py` — named field validators (spec `check:`) + `check_profile` cross-field checks
- `src/backhome/forms.py` — spec → `Cell`s (sheet), `recon`, `questionnaire`, `overview`
- `src/backhome/forms/ds160/spec.yaml` — CEAC element ids per page; `ids_verified: false` pages still have `TBD_*` ids
- `src/backhome/ceac/snapshot.js`, `nav.js` — run in the CEAC page via Claude in Chrome
- `skills/` — `ds160-autofill` (the fill loop), `immigration-intake` (docs → facts). Read before doing either.
- `raw/`, `data/` — **personal, gitignored**. `examples/data/` — synthetic twin used by tests.

## Rules
- Never commit/push `raw/` or `data/`; never paste SSN / national ID into shared places.
- Every new fact gets `confidence` + a `source` matching `model.SOURCE_RE` (`raw/<path>#pN`, `user:DATE`, `ceac:NODE`, `derived:…`).
- `null` = unknown → ask (questionnaire). `__NA__` = does not apply. Don't guess; `assumed` only to unblock navigation, never to submit.
- Agents never solve captchas and never click Sign/Submit on CEAC.
- When blocked on missing data: show the QUESTIONNAIRE.md questions, ask for a chat reply or files in `raw/inbox/`, persist with `backhome answer`, continue.

## Gotchas
- CEAC session is per tab; Save/Next need a real mouse click; many radios/“Add Another” postback;
  date option values differ per page (spec `day`/`month`); details in `skills/ds160-autofill/SKILL.md`.
- Claude-in-Chrome JS output truncates ~1.5k chars → stash in `window.__snap` and read in slices.
- `pypdf` needs the `crypto` extra for AES-encrypted I-20s; OCR needs `tesseract` (+`chi_sim` for Chinese).
