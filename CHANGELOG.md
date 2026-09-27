# Changelog

## 0.2.0 — 2026-09-27
- `ds160 run`: one-command pipeline (raw integrity → digest → validate → sheet → recon → review) with per-stage status.
- `ds160 review`: printable final-review document (HTML + PDF via headless Chrome), `--mask` for sensitive ids.
- `ds160 photo`: DS-160 photo crop/encode/verify from three landmarks; HEIC input.
- DS-160 spec covers all 18 CEAC sections with live-captured element ids; nested and scalar list items.
- Answers overlay: longest-prefix match; list items honour item-level answers.
- Packaging (`ds160-autofiller`), CI (ruff, pytest on 3.11–3.13, demo pipeline, build), bilingual README.

## 0.1.0 — 2026-09-27
- Fact model with confidence + source of truth, validators (PRC ID, MRZ, cross-field), ingest/digest, sheet,
  recon, questionnaire, overview; Claude Code skills; synthetic example applicant.
