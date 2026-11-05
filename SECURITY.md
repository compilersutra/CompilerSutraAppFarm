# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes (alpha — best-effort) |

## Reporting a vulnerability

Do **not** open a public issue for security reports.

Email **osc@compilersutra.com** with:

- Affected component (`csfarm` CLI, recipe, Docker image, …)
- Reproduction steps
- Impact (RCE, path traversal, supply-chain fetch, …)

We aim to acknowledge within a few business days. AppFarm fetches and builds
third-party source; treat recipe URLs and build scripts as part of the trust
boundary when reviewing changes.
