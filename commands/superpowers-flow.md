# Format C — Superpowers slash-command flow

This drives the build through the bundled Superpowers process skills explicitly, so the agent self-manages planning, TDD, verification, and review. Use this if you want the process skills doing the heavy lifting rather than steering each phase yourself.

The Superpowers skills don't use literal `/slash` commands — they're invoked by naming them. `sp-using-superpowers` is the router. The sequence below mirrors their intended workflow.

---

## Step 0 — Prime the agent
```
Read .claude/skills/sp-using-superpowers/SKILL.md and docs/PRD.md. From now on, follow the Superpowers workflow: brainstorm (only if needed) → write plan → execute plan with TDD → verify before completion → code review. The five domain skills (rag-agentic, rag-eval-goldenset, fastapi-streaming, nextjs-chat-ui, llm-provider) provide the technical patterns — pull them as each milestone requires. Confirm you've loaded the router and understood the constraints (near-$0 provider-agnostic LLM via LLM_PROVIDER with default gemini + ollama fallback, LangGraph+Chroma, FastAPI+Next.js, grade+refuse+cite, measurable retrieval).
```

## Step 1 — Plan (sp-writing-plans)
```
Invoke sp-writing-plans. Turn docs/PRD.md milestones M1–M8 into an executable, TDD-oriented plan. Preserve the de-risked order (M3 demo-safe before the agent loop). For each milestone name the domain skill it depends on and the tests that define "done". Present the plan and STOP for my approval — do not start building.
```

## Step 2 — Execute (sp-executing-plans + sp-test-driven-development)
```
Invoke sp-executing-plans with sp-test-driven-development. Execute the approved plan milestone by milestone. For each: write the failing test first, implement to green, then run sp-verification-before-completion before moving on. Pause at each milestone boundary for my go-ahead. Never mark a milestone done without passing tests (no false "it's done").
```

## Step 3 — Parallelize the independent stretch (optional)
```
If ahead of schedule after M6, invoke sp-dispatching-parallel-agents to run M7 (hybrid+rerank optimization) and M8's frontend trace panel in parallel, since they're independent. Merge and re-verify.
```

## Step 4 — Review (sy-code-review-expert)
```
Invoke sy-code-review-expert on the full git diff before final delivery. Focus on: retrieval correctness, the iteration cap, citation validation, refusal path, no blocking calls on the async path, and no accidental cloud/API calls. Apply the removal-plan for anything flagged. Then run project-security-audit (read-only) for a final pass.
```

## Step 5 — Handoff (mp-handoff)
```
Invoke mp-handoff to compress the session into docs/HANDOFF.md: architecture, how to run, test/eval commands, known limitations, and the exact demo script + demo-safe questions. This is what you (or a teammate) present from.
```

---

### Why this order works
- `sp-writing-plans` forces a spec→plan step so the agent doesn't wander.
- `sp-test-driven-development` makes "retrieves chunks correctly" a test, not a claim.
- `sp-verification-before-completion` blocks the classic false-done at each milestone.
- `sy-code-review-expert` + `project-security-audit` catch the RAG-specific footguns (ungraded chunks reaching generation, uncapped loops, hallucinated citations).
- `mp-handoff` gives you the presentation artifact for the 15–20 min demo.
