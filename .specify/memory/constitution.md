<!--
Sync Impact Report
Version change: 0.0.0 -> 1.0.0
Modified principles:
- I. Library-First
- II. CLI Interface
- III. Test-First (NON-NEGOTIABLE)
- IV. Integration Testing
- V. Observability, Versioning & Breaking Changes, Simplicity
Added sections:
- Architecture & Stack Constraints
- Development Workflow & Quality Gates
Removed sections:
- None
Templates requiring updates:
- .specify/templates/plan-template.md (Constitution Check gates bound to this constitution)
- .specify/templates/spec-template.md (no direct constitution coupling; verified)
- .specify/templates/tasks-template.md (tests wording aligned with constitution)
- .specify/templates/commands/ (directory missing; no command files to audit)
Deferred TODOs:
- None
-->

# Alist-MikananiRss Constitution

## Core Principles

### I. Library-First

- Every feature starts as a standalone library
- Libraries must be self-contained, independently testable, documented
- Clear purpose required - no organizational-only libraries

**Rationale**: This principle ensures that each feature is modular and reusable, making it easier to maintain and update the system.

### II. CLI Interface

- Every library exposes functionality via CLI
- Text in/out protocol: stdin/args → stdout, errors → stderr
- Support JSON + human-readable formats

**Rationale**: This principle provides a consistent and simple way to interact with each library, making it easier to use and integrate them.

### III. Test-First (NON-NEGOTIABLE)

- TDD mandatory: Tests written → User approved → Tests fail → Then implement
- Red-Green-Refactor cycle strictly enforced

**Rationale**: This principle ensures that the system is thoroughly tested and reliable, reducing the risk of bugs and errors.

### IV. Integration Testing

- Focus areas requiring integration tests: New library contract tests, Contract changes, Inter-service communication, Shared schemas

**Rationale**: This principle ensures that the system is thoroughly tested at the integration level, reducing the risk of errors and bugs.

### V. Observability, Versioning & Breaking Changes, Simplicity

- Text I/O ensures debuggability
- Structured logging required
- MAJOR.MINOR.BUILD format
- Start simple, YAGNI principles

**Rationale**: This principle ensures that the system is observable, maintainable, and easy to understand, making it easier to debug and update.

## Architecture & Stack Constraints

- Technology stack requirements
- Compliance standards
- Deployment policies
- Clear architecture documentation required

## Development Workflow & Quality Gates

- Code review requirements
- Testing gates
- Deployment approval process
- Continuous Integration and Continuous Deployment (CI/CD) pipeline

## Governance

- Constitution supersedes all other practices
- Amendments require documentation, approval, migration plan
- All PRs/reviews must verify compliance
- Complexity must be justified
- Use AGENTS.md for runtime development guidance

**Version**: 1.0.0 | **Ratified**: 2025-11-22 | **Last Amended**: 2025-11-22
