# Security & privacy

This tool handles passports, national IDs and SSNs. Design rules:

- **Local only.** Documents (`raw/`) and facts (`data/`) never leave your machine; both are gitignored and CI
  fails if they are tracked. There is no telemetry and no server component.
- **Immutable evidence.** `raw/` is content-addressed (sha256 manifest); `ds160 verify-raw` detects tampering.
- **Human in the loop.** Agents never solve captchas, never sign or submit, and only upload a photo after you
  grant the browser extension access to identix.state.gov.
- **Share safely.** Use `ds160 review APP --mask` before sharing a review; OVERVIEW.md masks sensitive ids.

Found a problem? Please open a private security advisory on GitHub rather than a public issue.
