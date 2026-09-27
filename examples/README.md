# Example data (synthetic)

A fictional applicant, **LI MING**, used by the test-suite and for trying the tool without real documents.
Every identifier is fake but *valid* (PRC ID checksum, passport MRZ check digits), so `backhome validate` passes.

```bash
BACKHOME_HOME=examples uv run backhome validate
BACKHOME_HOME=examples uv run backhome recon DEMO0000001   # shows one deliberate mismatch (BEIJNG)
```
