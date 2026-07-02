# START HERE — MaiStorage build with Claude Code

Everything you need is in this folder. Follow these steps in order.

---

## Step 1 — Open the right folder
Open **this `maistorage/` folder** as your project in Claude Code
(terminal: `cd maistorage` then `claude`, or open the folder in the desktop/VS Code app).
The `.claude/skills/` folder must be at the project root so skills auto-load.

## Step 2 — Install prerequisites
- **Node.js** (Next.js frontend)
- **Python 3.11+** (backend)
- **LLM provider** — default is Gemini free tier: get an API key from Google AI Studio (no card).
  Offline alternative: install **Ollama**, then `ollama pull llama3.1:8b && ollama pull nomic-embed-text`.
- Copy `.env.example` → `.env` and fill in your key / set `LLM_PROVIDER`.

## Step 3 — (Optional) add the full ECC plugin
A curated 33-skill ECC subset is already bundled. For the full plugin, in Claude Code:
```
/plugin marketplace add affaan-m/everything-claude-code
/plugin install everything-claude-code@everything-claude-code
```
Then sanity-check: ask Claude Code *"List the skills you can see in .claude/skills."*
You should see `sp-*` (Superpowers), the domain skills, and the ECC subset.

## Step 4 — Paste the ORIENTATION PROMPT (loads context, no build yet)

```
Read STRUCTURE.md, docs/PRD.md, and .claude/skills/sp-using-superpowers/SKILL.md.

This project is MaiStorage — an Agentic RAG system. The file tree is already scaffolded with
stub files, each with a docstring naming its skill and milestone. Do NOT recreate the layout —
fill in the stubs.

Constraints (from the PRD, do not violate):
- Provider-agnostic LLM via LLM_PROVIDER (default gemini; ollama offline fallback). Near-$0.
- Stack: FastAPI + LangGraph backend, Next.js + TypeScript frontend, Chroma vector DB.
- The agent grades its own chunks, re-retrieves (cap 3), and REFUSES rather than hallucinate.
- Every answer carries valid citations OR is an explicit refusal.
- Retrieval must be measurable on the golden set.

Process: use Superpowers as the spine (plan → TDD → verify). When ECC or domain skills overlap
with Superpowers (e.g. tdd-workflow vs sp-test-driven-development), use the Superpowers one
unless I say otherwise.

Confirm you've read these and understood the constraints. Then STOP — don't build yet.
I'll give you the first milestone next.
```

Wait for confirmation.

## Step 5 — Build milestone by milestone
Open `commands/phases.md`. Paste the **M1** block. When it finishes and reports, review + run
its tests, then paste **M2** … through **M8**. Don't skip the checkpoints — they're your safety net.

Build order (demo-safe from M3 onward):
M1 infra → M2 ingestion → **M3 baseline RAG+streaming** → M4 citations → M5 golden set+metrics
→ M6 agentic loop → M7 hybrid+rerank → M8 polish+trace.

---

## What you paste vs. what auto-loads
- **You paste:** the orientation prompt (Step 4) + the phase blocks M1–M8 (Step 5). That's it.
- **Auto-loads:** the 59 skills in `.claude/skills/` — Claude Code pulls the right one per milestone
  on its own. You never manually feed it a skill.

## Alternatives to Step 4–5
- `commands/README.md` — Format A: one master kickoff prompt (more momentum, fewer checkpoints).
- `commands/superpowers-flow.md` — Format C: let the Superpowers process skills self-drive.

## Reference (read as needed)
- `STRUCTURE.md` — file tree → skill/milestone map
- `docs/PRD.md` — the spec
- `docs/SKILLS_SETUP.md` — ECC + Superpowers coexistence
- `docs/TOKEN_MONITORING.md` — usage/cost/context tracking
- `docs/ECC_SKILLS_MANIFEST.md` — which ECC skills were bundled + caveats
