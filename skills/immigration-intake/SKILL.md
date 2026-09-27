---
name: immigration-intake
description: Turn a person's immigration documents (passport, visas, I-20, I-94, EAD, I-797, W-2, offer letters, diplomas, IDs) into the backhome fact profile — every value with confidence and a source-of-truth pointer — and keep it validated. Use when the user shares or updates personal documents, asks to "organize my immigration info", or when a form-filling agent hits a missing fact.
---

# Immigration intake (backhome)

Pipeline: **raw → digest → facts → validate**. Commands run from the repo root.

1. `uv run backhome ingest <dir-or-file>...` — copies into `raw/` (sha256 manifest, never overwrites; files the
   user drops into `raw/inbox/` are registered too). Source folders are read-only: never move/edit originals.
2. `uv run backhome digest` — text per page into `data/digest/`; `data/digest/INDEX.tsv` lists files with
   `needs-vision` (scans/photos): open those with the Read tool (images/PDF pages) and read them yourself.
3. Write facts into `data/profile/<namespace>.yaml`:
   `field: {value: ..., confidence: <level>, source: "raw/<path>#p<page>", note: "..."}`.
   Confidence: **verified** (official doc + independent confirmation: 2nd doc, checksum, CEAC echo) ·
   **high** (text-extracted from an official doc) · **medium** (visual/OCR read, or computed) ·
   **user** (user said so) · **low** (inference) · **assumed** (default with no evidence; must be confirmed).
   `null` = unknown (never guess); `__NA__` = does not apply. Names/addresses in UPPERCASE as on the passport.
4. `uv run backhome validate` — must report 0 errors (PRC ID checksum, MRZ check digits, DOB/sex/expiry
   cross-checks, travel-history ordering, source grammar). `--all` lists every fact needing review.
5. Anything still unknown goes to the questionnaire (`backhome recon <APP>` writes `QUESTIONNAIRE.md`);
   the user answers in chat or with documents; persist with `backhome answer`.

Privacy: `raw/` and `data/` are gitignored and must never be committed, pushed, or pasted into shared places.
