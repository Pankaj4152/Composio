# Generated data

This directory will contain generated research and verification artifacts. Pass outputs remain separate so the initial agent predictions are never overwritten by retries or human corrections.

- `pass1/`: frozen first-pass records
- `pass2/`: frozen records after automated verification and targeted retry
- `logs/`: retrieval, extraction, validation, and retry artifacts
- `audit/`: representative and challenge-set human audit records
- `final.json`: final normalized dataset, generated later
- `analysis.json`: computed findings, generated later
