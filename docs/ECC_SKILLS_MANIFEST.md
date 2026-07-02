# ECC Skills — what was copied and from where

33 skills were curated from **Everything Claude Code** (affaan-m/everything-claude-code)
and copied into `.claude/skills/`. They are a **subset**, chosen for this project's stack
(JS/TS · Next.js · React Native · Flutter) and the RAG build. This is a skills-only copy —
NOT the full ECC plugin (no ECC agents/hooks/commands/rules/MCP configs). For the full
system, still do the plugin install in docs/SKILLS_SETUP.md.

Source repo: https://github.com/affaan-m/everything-claude-code (license: see ECC_SKILLS_LICENSE)

## Your stack
react-patterns, react-testing, react-performance, react-native-patterns,
nextjs-turbopack, dart-flutter-patterns, flutter-dart-code-review,
frontend-patterns, frontend-design-direction, vite-patterns, bun-runtime

## Backend / Python / RAG
fastapi-patterns, python-patterns, python-testing, iterative-retrieval,
eval-harness, prompt-optimizer, cost-aware-llm-pipeline, context-budget,
token-budget-advisor, mcp-server-patterns, agent-eval, search-first

## Process / quality (complements Superpowers)
tdd-workflow, verification-loop, security-scan, security-review,
error-handling, git-workflow, docker-patterns, deployment-patterns,
code-tour, coding-standards

## Caveats (skills-only copy)
- **search-first** references ECC's "researcher agent" which is NOT included here.
  The workflow guidance still applies; it just can't auto-dispatch that agent without
  the full ECC plugin.
- A few skills (git-workflow, docker-patterns, tdd-workflow) contain example paths like
  `.git/hooks/...` or `scripts/...` — these are ILLUSTRATIONS inside the skill, not missing
  dependencies. They work standalone.

## Overlap with Superpowers — pick one owner per task
tdd-workflow (ECC) vs sp-test-driven-development (Superpowers);
verification-loop (ECC) vs sp-verification-before-completion;
security-review/security-scan (ECC) vs project-security-audit (kit);
code review: sy-code-review-expert (kit) vs ECC review skills.
Name the one you want in your prompt so they don't double-fire. Suggested default:
keep Superpowers as the process spine; use these ECC skills for stack-specific depth.
