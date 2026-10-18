## MUST rules

- Always use Traditional Chinese to respond to user prompts, unless explicitly asked to use another language.

## Workflow Orchestration

### 1. Brainstorming Default

- **Use brainstorming skill** for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, **STOP and re-brainstorm immediately** - don't keep pushing
- Use brainstorming skill for verification steps, not just building

### 2. Subagent Strategy

- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop

- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project
- Remember user's preferences in `tasks/preferences.md` and suggest improved solutions to them for similar tasks

### 4. Verification Before Done

- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)

- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing

- When given a bug report: **just fix it**. Don't ask for hand-holding
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

---

## Task Management

1. **Brainstorming Skill First**: Use it for starting any non-trivial task; the result is a design document under `docs/superpowers/specs/`, committed.
2. **Track on GitHub**: Open a GitHub issue for the brainstormed item, linking the design document. This is the parent issue.
3. **Grill**: Run `/grill-me` on the design until no open questions remain, then update the parent issue (and the design document) with the outcomes.
4. **Tickets**: Run `/to-tickets` to break the parent issue into development sub-issues, with native GitHub `blocked_by` dependencies.
5. **Implement**: Run `/implement` on each ticket in dependency order (any ticket whose blockers are all closed).
6. **Explain Changes**: High-level summary at each step
7. **Document Results**: Add review section to `tasks/todo.md`
8. **Capture Lessons**: Update `tasks/lessons.md` after corrections

`openspec/` holds v1 history only; new work does not use OpenSpec (`opsx:*`).

### Public repository

This repository is **public**. Never commit secrets (API keys, OAuth tokens, `CLAUDE_CODE_OAUTH_TOKEN`, openab auth keys), home-host addresses or Tailscale names, or reference voice recordings and their transcripts. Keep them in host-local config outside the repo (e.g. `~/.buddy-host/`).

---

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.

- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.
- **TDD Mindset**: Red-green-refactor. Write tests first, then implement. Refactor for elegance.

---

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues (`wm4n/ai-tour-guide`) via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context (`CONTEXT.md` + `docs/adr/` at the repo root, created lazily). See `docs/agents/domain.md`.
