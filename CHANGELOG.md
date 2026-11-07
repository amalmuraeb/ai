# Changelog

All notable changes to JOB-AGENT are documented in this file.

The project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-07

### Added

- Initial public, source-available release of JOB-AGENT.
- HigherEdJobs acquisition through Microsoft Edge, Playwright, and the Chrome
  DevTools Protocol.
- Deterministic pre-LLM provisioning for user preferences, posting age,
  employment type, salary, institution orientation, role, and focus area.
- Structured Ollama analysis for job fit, focus areas, required skills, and
  final recommendations.
- Separate transactional report channels for remote and non-remote jobs.
- Permanent integer job sequences for non-remote jobs and `r`-prefixed
  sequences for remote jobs.
- External private profile and applied/closed-job history outside the Git
  repository.
- Document-requirement discovery and application-readiness reporting.
- Isolated Phase 3–5 and Phase 6 execution modes.
- Transactional report staging, validation, rollback, and publication.
- Deterministic regression suite using saved HTML fixtures and test doubles.
- PolyForm Noncommercial 1.0.0 licensing with a separate commercial-licensing
  path.
- Semantic application versioning through `python -m src.main --version` and
  report-level `software_version` metadata.

### Known limitations

- Production execution requires Windows-hosted Microsoft Edge and Ollama with
  Python running in WSL2.
- HigherEdJobs is the only implemented job-board source.
- Application preparation and submission remain manual user activities.

[Unreleased]: https://github.com/amalmuraeb/ai/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/amalmuraeb/ai/releases/tag/v1.0.0
