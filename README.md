# backhome

**Agent-native immigration paperwork.** Keep your documents as immutable evidence, turn them into facts that
each carry a *confidence* and a *source of truth*, compile any form (DS-160 first) into an expected-value
sheet, let an agent fill the real website, then **reconcile** what the website actually holds against the sheet.

```
raw/ (your PDFs, scans)  ──ingest──▶  MANIFEST.tsv (sha256, immutable)
        │ digest                                   ▲ user drops files in raw/inbox/
        ▼                                          │
data/digest/*.txt ──agent reads──▶ data/profile/*.yaml   facts: {value, confidence, source}
                                          │ validate  (checksums, MRZ, cross-field)
                                          ▼
 forms/ds160/spec.yaml ──▶ sheet.tsv ──agent fills CEAC in Chrome──▶ snapshots/<page>.tsv
                                          │ recon
                                          ▼
                     OVERVIEW.md  (per section ✅/❌/⛔, confidence, source)
                     QUESTIONNAIRE.md  (what's missing or assumed → ask the human)
```

## Why
Visa forms punish small inconsistencies (a date in one form that disagrees with another). backhome makes every
answer traceable: *where did this value come from, how sure are we, and does the live form still hold it?*

## Quick start
```bash
uv sync && uv run pytest -q
BACKHOME_HOME=examples uv run backhome validate               # synthetic applicant LI MING
BACKHOME_HOME=examples uv run backhome recon DEMO0000001      # one deliberate mismatch, many open questions
cat examples/data/applications/DEMO0000001/OVERVIEW.md
```
With your own documents:
```bash
uv run backhome ingest ~/Documents/immigration      # → raw/ (gitignored)
uv run backhome digest                              # → data/digest/, INDEX.tsv flags scans that need vision
# ask your agent (Claude Code) to follow skills/immigration-intake to write data/profile/*.yaml
uv run backhome validate
mkdir -p data/applications/AA00XXXXXX && cp examples/data/applications/DEMO0000001/application.yaml data/applications/AA00XXXXXX/
# then follow skills/ds160-autofill with Claude in Chrome
```

## Data model
| confidence | meaning |
|---|---|
| `verified` | official document **and** an independent confirmation (second document, checksum/MRZ, CEAC echo) |
| `high` | text-extracted from an official document |
| `medium` | visual/OCR read, or computed from documents |
| `user` | stated by the user; no document |
| `low` | inference from indirect evidence |
| `assumed` | agent default with no evidence — must be confirmed before submission |

Sources: `raw/<path>#p<page>` · `user:YYYY-MM-DD` · `ceac:<page>` · `derived:<how>`. `null` = unknown, `__NA__` = does not apply.

## Validation
Field validators (PRC ID GB 11643 checksum, passport/visa/I-94/USCIS receipt/SSN formats, CEAC charset and
length limits) and profile cross-checks (MRZ check digits vs. passport fields, ID-embedded birth date and sex,
issue < expiry, passport ≥ 6 months, travel-history ordering, telecode count, source grammar).

## Using it as Claude Code skills
Symlink the skills so any Claude Code session can use them:
```bash
ln -s "$PWD/skills/ds160-autofill" ~/.claude/skills/ds160-autofill
ln -s "$PWD/skills/immigration-intake" ~/.claude/skills/immigration-intake
```

## Extending to other forms
Add `src/backhome/forms/<form>/spec.yaml` (pages → fields with `from:` paths, `type`, `check`, `map`, `na`,
`when`, `group`, `ask`) and a snapshot script for that site. The sheet/recon/questionnaire machinery is form-agnostic.

## Privacy
`raw/` and `data/` are in `.gitignore` and never leave your machine. The repo contains only code, specs,
skills and the synthetic `examples/`. Agents never solve captchas and never sign or submit.

MIT license.
