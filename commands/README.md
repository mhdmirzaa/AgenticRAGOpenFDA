# Claude Code — Commands (all formats)

This project ships three ways to drive Claude Code. Use **one**:

- **Format A — Master kickoff prompt:** paste once, Claude runs the whole plan with checkpoints. Best if you want momentum.
- **Format B — Phase-by-phase prompts:** paste one per milestone. Best for control and safe fallback points.
- **Format C — Superpowers slash-command flow:** leverages the bundled process skills explicitly. Best if you trust the Superpowers workflow to self-drive.

All three assume the `.claude/skills/` directory (Superpowers + the 5 domain skills) is in the project root, and `docs/PRD.md` is present.

---

## FORMAT A — Master kickoff prompt

> Paste this as your first message to Claude Code in the project directory.

```
You are building MaiStorage, an Agentic RAG system. The full spec is in docs/PRD.md — read it first and treat it as the source of truth.

Skills: this repo has .claude/skills/ containing the Superpowers process skills AND five domain skills: rag-agentic, rag-eval-goldenset, fastapi-streaming, nextjs-chat-ui, llm-provider. Use sp-using-superpowers as your process router, and pull the relevant domain skill at each phase.

Hard constraints (from the PRD, do not violate):
- Near-$0, provider-agnostic LLM via LLM_PROVIDER (default gemini free tier; ollama offline fallback), Chroma. Total spend < $1.
- Stack: FastAPI + LangGraph backend, Next.js + TypeScript frontend, Chroma vector DB, provider-agnostic LLM layer.
- The agent must grade its own chunks, re-retrieve (cap 3 iterations), and REFUSE rather than hallucinate.
- Every answer carries valid citations OR is an explicit refusal.
- Retrieval quality must be measurable on a committed golden set (Hit@k, MRR).

Process:
1. Use sp-brainstorming ONLY if something in the PRD is ambiguous — otherwise proceed.
2. Use sp-writing-plans to turn the PRD milestones (M1–M8) into an executable plan. Show me the plan and STOP for my approval before building.
3. Use sp-executing-plans + sp-test-driven-development to build milestone by milestone.
4. After EACH milestone, run sp-verification-before-completion and report: what works, what's tested, what's next. STOP for my go-ahead before the next milestone.
5. Build order is the PRD's de-risked order: M1 infra → M2 ingestion → M3 baseline RAG+streaming → M4 citations → M5 golden set+metrics → M6 agentic loop → M7 hybrid+rerank → M8 polish+trace. Do NOT reorder — M3 must be demo-safe before adding the loop.

Corpus: generate the synthetic company-handbook corpus described in the PRD (leave policy, public holidays, product specs, FAQ, with at least one multi-hop fact and content for unanswerable questions).

Start with step 2: read docs/PRD.md and the domain skills, then produce the plan and stop for my approval.
```

---

## FORMAT B — Phase-by-phase prompts

See `commands/phases.md` for one prompt per milestone (M1–M8), each with its own checkpoint.

---

## FORMAT C — Superpowers slash-command flow

See `commands/superpowers-flow.md` for the explicit brainstorm→plan→execute→verify sequence.
