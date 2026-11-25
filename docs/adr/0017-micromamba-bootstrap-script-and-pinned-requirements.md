# ADR 0017: Provide setup_and_run.sh (micromamba) and pin all requirements exactly

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

Users need a reproducible environment. Commits b167b83 (2026-11-04, "Pin Python requirements to running versions (VulnOps 20261104)") and 98f2fbd (2026-11-05, requests 2.33.0 for CVE-2026-25645) were made by the VulnOps flow and merged via PRs 1 and 2.

## Decision

`setup_and_run.sh` creates/reuses a micromamba env (default `tars-ai`, Python 3.12), upgrades pip, installs requirements.txt, runs a non-fatal OMLX reachability/model-listing preflight, then launches `main.py` with the resolved flags. requirements.txt pins exact versions (openai, langchain-core, sounddevice, soundfile, numpy, rich, pyyaml, pytest) plus `requests==2.33.0` as a transitive-dependency floor for the CVE.

## Consequences

### Positive

- Reproducible installs; preflight warns about missing models before the first chat.
- Known CVE floor recorded in the file.

### Negative

- pytest is in the runtime requirements file.
- Exact pins need manual or automated bumps (A-009).
- Script requires micromamba.

## Alternatives considered

venv + plain pip; not chosen per script comments, rationale undocumented.

## Evidence

setup_and_run.sh; requirements.txt; commits b167b83, 98f2fbd, merges 126ea98, c41074a.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
