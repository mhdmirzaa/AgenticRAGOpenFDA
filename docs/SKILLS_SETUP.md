# Skills Setup — ECC + Superpowers together

Your project uses two skill layers that run alongside each other.

## Layer 1 — This kit (project-level, `.claude/skills/`)
Already present when you unzip the kit:
- **Superpowers (14 `sp-` skills)** — the process spine: brainstorm → plan → execute → TDD → verify → review. Router: `sp-using-superpowers`.
- **Curated additions (6)** — `sy-code-review-expert`, `mp-codebase-design`, `mp-handoff`, `sy-skill-forge`, `caveman`, `project-security-audit`.
- **5 domain skills (this project)** — `rag-agentic`, `rag-eval-goldenset`, `fastapi-streaming`, `nextjs-chat-ui`, `llm-provider`.

## Layer 2 — Everything Claude Code (ECC), installed as a plugin
```
/plugin marketplace add affaan-m/everything-claude-code
/plugin install everything-claude-code@everything-claude-code
```
Pulls ECC's agents, skills, hooks, and commands. Note: Claude Code plugins can't auto-distribute **rules** — copy any ECC rules you want manually per its README.

Repo: https://github.com/affaan-m/everything-claude-code

## Division of labor (avoid overlap conflicts)
Both cover planning, TDD, code review, and security. To prevent double-firing:

- **Superpowers owns the process spine** for building MaiStorage (plan → TDD → verify → review) — your commands already reference it.
- **ECC supplies breadth** Superpowers lacks: language/framework skills (backend/frontend/Next.js patterns), security scanning (`/security-scan`, AgentShield), continuous-learning/memory, specialized agents.
- **One owner per overlapping area.** Pick Superpowers' `sp-test-driven-development` OR ECC's TDD agent — not both on the same task. Same for code review and security. Name the one you want in the prompt.

Rule of thumb: **Superpowers = how we march the milestones; ECC = extra domain firepower + production hardening pulled in as needed.**

## Context budget warning
Loading too many skills/MCPs at once shrinks usable context (ECC's docs cite 200k → 70k). Mitigations:
- Skills load **on demand** — availability ≠ active context. Having them installed is fine.
- Don't enable every ECC MCP at once; use `disabledMcpServers` for unused ones.
- If context feels tight, disable ECC agents/MCPs you aren't using for the current milestone.

## Quick sanity check after install
- `/plugin` — confirm ECC shows installed.
- Ask Claude Code to list which skills it sees; confirm both `sp-using-superpowers` (kit) and ECC skills appear.
- Run one milestone prompt (Format B, M1) and confirm the process spine is Superpowers, with ECC available but not double-driving.
