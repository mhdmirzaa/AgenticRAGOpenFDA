# Token & Usage Monitoring

Covers all three things you asked to monitor: **Claude Code usage** (5-hour / weekly limits), **API token & cost spend**, and **context-window usage** per session. Everything here is real and verified — built-in commands, a bundled skill, and named GitHub tools with their install commands.

---

## 1. Context-window usage (bundled skill)

`.claude/skills/session-tracker/` — the real **Session-Tracker** skill (El-Bach/Session-Tracker), bundled into this kit. It estimates tokens and context-window memory for the current chat, live, **no API needed**. Ask "how much context is left" / "how many tokens" and it produces a dashboard.

Two things to know:
- **It's estimation-based** (author states ±15–25% margin). For exact numbers use the API/CLI tools below.
- **It's personalized to its author** — the SKILL.md hardcodes owner "Bach" and Beirut/EEST peak hours. To generalize: edit `session-tracker/SKILL.md`, remove the owner line and swap the "Peak Hours (Beirut)" section for your own timezone (or delete it).

Upstream: https://github.com/El-Bach/Session-Tracker

---

## 2. Claude Code usage — built-in commands (most reliable)

No install needed. Inside Claude Code:
- `/usage` — subscription usage against your 5-hour and weekly limits.
- `/status` — current session/account status.
- `/cost` — spend for API-key users.

Per Anthropic's docs these are the authoritative source for subscription limits; community tools fill the historical/real-time gaps.

---

## 3. API token & cost spend — CLI tools (verified)

Read Claude Code's local JSONL logs (`~/.claude/projects/`), nothing leaves your machine:

- **ccusage** — `npx ccusage` — fast local CLI for tokens + estimated cost across many agent CLIs. Site: https://ccusage.com
- **Claude-Code-Usage-Monitor** (Maciek-roboblog) — real-time terminal dashboard with burn-rate predictions and time-to-limit. https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor
- **claude-usage** (phuryn) — local web/VS Code dashboard of usage, costs, session history. https://github.com/phuryn/claude-usage

Menu-bar / desktop apps (run beside Claude Code, opt-in): `aqua5230/usage`, `soulduse/ai-token-monitor`, `mm7894215/TokenTracker`.

---

## 4. For API-provider spend (Gemini/OpenAI/etc.)

The tools above track Claude Code. For your RAG app's own LLM calls (the `llm-provider` layer), watch spend in the provider's own console:
- Gemini: Google AI Studio / Cloud billing (free tier has daily quotas — no card).
- OpenAI: platform.openai.com usage dashboard.
- Groq: Groq console.

Because this project's total volume is tiny (< $1), provider-console monitoring plus a spend cap is plenty.

---

## Recommendation
- **During the build:** keep `ccusage` or Claude-Code-Usage-Monitor open in a side pane — early warning on the 5-hour window matters most during long agentic runs.
- **In-chat quick check:** trigger the bundled `session-tracker` skill.
- **Authoritative limits:** `/usage` in Claude Code.
