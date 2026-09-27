# Contributing

```bash
uv sync --all-extras
make lint test demo
```

- **Never commit personal data.** `raw/` and `data/` are gitignored and CI rejects them. Tests use only the
  fictional applicant in `examples/`; keep new fixtures synthetic (valid checksums, fake names).
- **CEAC changed?** Snapshot the page with `src/backhome/ceac/snapshot.js`, update
  `src/backhome/forms/ds160/spec.yaml`, run `ds160 recon` against your snapshot, and note the change in
  `CHANGELOG.md`. Add quirks to `skills/ds160-autofill/SKILL.md`.
- **New form?** Add `src/backhome/forms/<form>/spec.yaml`; the sheet/recon/questionnaire/review machinery is
  form-agnostic. Include a synthetic example application and a test.
- Style: `ruff format` + `ruff check` (config in `pyproject.toml`). Keep functions small and pure where possible.
