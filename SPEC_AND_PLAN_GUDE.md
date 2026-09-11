# SPEC.md & PLAN.md — Best Practices Guide

Based on: GitHub Spec Kit, Addy Osmani, Spec-Coding, OpenSpec, Allegro Tech, intent-driven.dev, Roy Gabriel, Gunther Popp, OpenAI Codex ExecPlans, GSD Build.

---

## 📋 SPEC.md — Specification (What & Why)

### Purpose
A **testable contract** between stakeholders, engineers, and QA. Describes *observable behavior*, not implementation.

### Mandatory Sections

| Section | Content | Rules |
|---------|---------|-------|
| **Title + Metadata** | Version, status (Draft/Review/Approved), authors, reviewers, links to PRD/ADR | Status must be "Approved" before implementation starts |
| **Context / Problem** | User problem, business justification, metrics, current state, constraints | 2-4 paragraphs max. No solution proposals. |
| **Functional Requirements (FR)** | Atomic, testable, RFC 2119 keywords (`MUST`/`SHOULD`/`MAY`), numbered FR-1, FR-2… | One behavior per FR. Observable by external tester. |
| **Non-Functional (NFR)** | Measurable thresholds: latency p95, RPS, availability, security | "Fast" → "p95 < 200ms". Every NFR needs a metric. |
| **Acceptance Criteria (AC)** | Given/When/Then format. Each AC references ≥1 FR/NFR. | Machine-testable. No subjective language. |
| **Edge Cases / Error Scenarios** | Per external dependency: failure modes, boundaries, concurrency | Cover: empty input, null, timeout, 4xx/5xx, race conditions. |
| **API Contracts** | HTTP method+path, request/response (TypeScript-style), headers, error codes | Define success AND error responses (400,401,403,404,409,429,500). |
| **Data Models** | Tables/schemas with constraints, indexes, soft/hard delete | Every entity in FRs must have a model. Constraints match FRs. |
| **Out of Scope** | Explicitly rejected/discussed items with reasons | "Not now" is not a reason. Link future specs if deferred. |

### Key Principles

1. **What, not How** — Spec describes behavior; implementation details belong in code/design docs.
2. **Testability** — Every statement must be verifiable without reading code.
3. **RFC 2119** — Use `MUST`/`SHALL` (hard), `SHOULD` (strong rec), `MAY` (optional) in UPPERCASE.
4. **Atomic Requirements** — One behavior = one FR. Split "and also" clauses.
5. **Living Document** — Update when design decisions are made during implementation.
6. **Right-Size** — 1-3 pages per feature. If longer → split into sub-specs.
7. **Human Reviewable** — If you skim thinking "AI got it right", it's too large.

### Anti-Patterns ❌

- Implementation details in requirements ("calls method X")
- Subjective criteria ("fast", "user-friendly")
- Missing Non-Goals → scope creep
- Edge cases as afterthought
- Spec diverges from code (spec-implementation drift)

---

## 📅 PLAN.md — Implementation Plan (How & When)

### Purpose
An **executable plan** for AI agents or humans. Breaks spec into sequential, verifiable steps.

### Mandatory Sections

| Section | Content |
|---------|---------|
| **Overview + Goals/Non-Goals** | 1-2 sentences + explicit boundaries |
| **Constraints** | Hard rules: no new deps, backward compat, style guide, reference files |
| **References** | Repo-relative paths to reference implementations (not wiki links) |
| **Phases** | Dependency order. Each: tasks + verification command + expected output |
| **Definition of Done** | Machine-checkable: tests pass, typecheck, lint, no TODOs, docs updated |
| **Risks / Open Questions** | Specific risks with mitigations |
| **Progress Tracking** | Checkboxes + verification commands per step |

### Phase Template

```markdown
### Phase N: <Name>
- [ ] Task — exact file/function to create/modify
- **Verify:** `pytest tests/xyz -v` → exit 0, 3 new tests pass
- **Out of scope:** Do not touch file X
```

### Key Principles

1. **Executable** — Agent can run step without clarification.
2. **Verification Gates** — Every step ends with `command → expected output`.
3. **Hard Boundaries** — Explicit Out of Scope + STOP conditions.
4. **Self-Contained** — All context in file: paths, conventions, commands.
5. **Right-Sized Phases**:
   - Small (hours–2 days): one `PLAN.md`
   - Medium (1–2 weeks): one `PLAN.md` with explicit phases
   - Large (multi-week): `plan/phase-1a.md`, `plan/phase-1b.md`, etc.
6. **Version-Controlled** — Commit before implementation starts.
7. **Checkpoint Commits** — Commit after each step, not at the end.

### Anti-Patterns ❌

- Mixing "what" and "how"
- Phase touches 30+ files → split
- Verification = "verify it works" (must be a command)
- Plan goes stale → agent must update PLAN.md during execution
- No constraints → agent invents defaults

---

## 🔗 SPEC ↔ PLAN Relationship

```
SPEC.md (What/Why)          PLAN.md (How/When)
─────────────────────       ─────────────────────
FR/NFR/AC          ───maps to───>  Phases implementing each FR
API Contracts      ───maps to───>  Files to create/modify + contract tests
Data Models        ───maps to───>  Migration scripts + model files
Edge Cases         ───maps to───>  Error handling tasks + negative tests
Out of Scope       ───maps to───>  Explicit "do not touch" in plan
```

### Spec-Driven Development Workflow

```
1. SPECIFY   → Write SPEC.md (collaborative, review, approve)
2. PLAN      → Generate PLAN.md from SPEC (agent or human)
3. IMPLEMENT → Execute phases sequentially with checkpoint commits
4. VALIDATE  → Tests + agent review + manual demo
```

---

## ✅ Readiness Checklists

### SPEC.md Ready for Review?

- [ ] Every section filled (or "N/A — [reason]")
- [ ] All requirements use FR-N, NFR-N numbering
- [ ] RFC 2119 keywords are UPPERCASE
- [ ] Every AC references ≥1 FR/NFR
- [ ] Every AC uses Given/When/Then
- [ ] Edge cases cover each external dependency failure
- [ ] API contracts define success AND error responses
- [ ] Data models include all entities from FRs
- [ ] Out of Scope lists discussed/rejected items with reasons
- [ ] No placeholder text remains
- [ ] Context includes evidence (metrics, tickets, research)
- [ ] Status = "In Review" (not "Draft")

### PLAN.md Ready for Execution?

- [ ] Goals + Non-Goals explicit
- [ ] Constraints listed (style, deps, compat, reference files)
- [ ] References point to actual repo files with paths
- [ ] Phases in dependency order
- [ ] Every phase has verification command + expected output
- [ ] Definition of Done is machine-checkable
- [ ] STOP conditions defined (drift, failed verification, out-of-scope)
- [ ] Current state excerpts inlined for context
- [ ] Test plan specifies new tests to write + pattern to follow
- [ ] Plan committed to git before implementation starts

---

## 📏 Sizing Guidelines

| Feature Size | SPEC.md | PLAN.md |
|--------------|---------|---------|
| Small (hours–2 days) | 1 page | 1 file, flat steps |
| Medium (1–2 weeks) | 2–3 pages | 1 file, explicit phases |
| Large (multi-week) | Multiple sub-specs | `plan/` directory with multiple files |

**Rule of thumb:** If spec > 3 pages or plan phase > 20 files → decompose.

---

## 🛠 Tooling Integration

### For AI Agents
- Feed SPEC.md as context for planning
- Feed only relevant PLAN.md phase for implementation
- Use Extended TOC (summarized spec) for large features
- Three-tier boundaries: Always / Ask First / Never

### For CI/CD
- Validate SPEC.md structure in PR checks
- Require SPEC.md approval before PLAN.md creation
- Verify PLAN.md phases pass gates before merge
- Track spec-implementation drift (automated checks)

---

## 📚 References

- [GitHub Spec Kit](https://github.com/github/spec-kit) — Four-stage SDD workflow
- [Addy Osmani: Good Specs for AI Agents](https://addyosmani.com/blog/good-spec/)
- [Spec-Coding: Technical Spec Template](https://spec-coding.dev/blog/how-to-write-technical-spec-template-guide)
- [OpenSpec: Writing Good Specs](https://openspec.dev/docs/writing-specs)
- [Allegro Tech: SDD Best Practices](https://blog.allegro.tech/2026/06/spec-driven-development-best-practices.html)
- [intent-driven.dev: SDD Best Practices](https://intent-driven.dev/knowledge/best-practices/)
- [Roy Gabriel: LLM Development Guide - Planning](https://roygabriel.dev/blog/llm-development-guide/02-planning-artifacts/)
- [Gunther Popp: Implementation Plans](https://guntherpopp.de/en/blog/best-practices-implementation-plan)
- [OpenAI Codex: ExecPlans](https://developers.openai.com/cookbook/articles/codex_exec_plans)
- [GSD Build: PLAN.md Format](https://deepwiki.com/gsd-build/get-shit-done/7.1-plan.md-format)

---

## 🎯 Quick Templates

### Minimal SPEC.md (Small Feature)
```markdown
# Spec: <Feature>
**Status:** Approved | **Version:** 1.0

## Context
<Problem + business justification in 2-3 sentences>

## Functional Requirements
- FR-1: The system MUST <observable behavior>
- FR-2: The system MUST NOT <prohibited behavior>

## Non-Functional
- NFR-1: p95 latency < 200ms
- NFR-2: Error rate < 0.1%

## Acceptance Criteria
- AC-1 (FR-1): Given <state>, When <action>, Then <observable result>

## Edge Cases
- EC-1: <dependency> timeout → Return 503, retry after 30s

## API Contract
POST /api/xyz → 201 { ... } | 400 { ... } | 500 { ... }

## Data Model
<table with constraints>

## Out of Scope
- <Item> — <reason>
```

### Minimal PLAN.md (Small Feature)
```markdown
# Plan: <Feature>
**Spec:** SPEC.md | **Status:** Approved

## Goals
- <Goal 1>

## Non-Goals
- <Explicit out of scope>

## Constraints
- Follow `src/lib/patterns.ts` style
- No new dependencies

## References
- `src/api/handlers.ts:40-60` — reference handler pattern
- `tests/api/handlers.test.ts` — test pattern

## Phase 1: Implementation
- [ ] Create `src/feature/xyz.ts` with function `doXyz()`
- **Verify:** `pnpm typecheck` → exit 0

## Phase 2: Tests
- [ ] Add tests in `tests/feature/xyz.test.ts` (happy path + EC-1)
- **Verify:** `pnpm test tests/feature/xyz.test.ts` → 3 pass

## Definition of Done
- [ ] `pnpm typecheck` exit 0
- [ ] `pnpm test` exit 0
- [ ] No files outside scope modified
- [ ] Docs updated if needed
```

---

## 🔄 Maintenance

- **Update SPEC.md** when: design decision made, requirement changed, edge case discovered
- **Update PLAN.md** when: task completed differently, new dependency found, phase split/merged
- **Commit both** with implementation commits
- **Review quarterly** for drift (spec vs code vs plan)

*Last updated: 2026-09-10*