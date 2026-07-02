# 📊 session-tracker — Claude Skill

A Claude skill that estimates token usage and context window memory for your current chat session — in real time, without needing the API.

Know when to start a new chat. Know when peak hours are draining your budget faster. Never get surprised by a usage limit again.

---

## 🚀 Installation

### Recommended — Claude.ai (browser)

1. Download this repo as a ZIP
2. Go to **claude.ai → Sidebar → Customize → Skills → Upload a Skill**
3. Upload the ZIP

Done. Claude will now run the session tracker whenever you ask.

### Or — Clone into Claude Code skills directory

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/El-bach/session-tracker.git ~/.claude/skills/session-tracker
```

---

## 🔥 The Problem This Solves

Claude Pro runs on a **5-hour rolling token window**. Most users have no idea how fast they're burning through it — until Claude stops responding.

The context window is separate: a 200,000-token memory limit that silently fills up as conversations grow. When it's full, Claude starts "forgetting" your earlier messages.

Neither limit is shown to you in real time. This skill fixes that.

---

## 🎯 How to Use

Just say any of these in your Claude conversation:

```
session status
```
```
how much have I used?
```
```
how much context is left?
```
```
am I close to the limit?
```
```
session budget
```
```
how many tokens so far?
```

Arabic triggers also work:
```
كم استخدمت؟
كم باقي؟
```

---

## 📋 What You Get

A full dashboard, generated instantly:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 SESSION USAGE DASHBOARD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SESSION OVERVIEW
  Turns completed:     4 exchanges
  Uploads:             report.pdf (~9,000 tokens)
  Project active:      No

TOKEN BREAKDOWN
  System prompt:       ~3,000 tokens
  Conversation:        ~18,400 tokens
  Uploads:             ~9,000 tokens
  ──────────────────────────────
  TOTAL THIS SESSION:  ~30,400 tokens

CONTEXT WINDOW (Memory)
  Used:    ~30,400 / 200,000 tokens  (15.2%)
  [███░░░░░░░░░░░░░░░░░] 15.2%
  Remaining: ~169,600 tokens
  ≈ room for ~105 more medium exchanges

SESSION BUDGET (5-hour rolling window)
  Estimated load:  Light
  Budget used:     ~20% of typical Pro session
  [████░░░░░░░░░░░░░░░░] 20%

⏰ PEAK HOURS CHECK
  ⚠️ You are in peak hours — budget burns faster right now

💡 RECOMMENDATIONS
  1. Session is still light — continue normally.
  2. Uploaded PDF stays in context for the whole session.
     Don't re-upload — reference it by name.
  3. You're in peak hours. Heavy tasks are better after off-peak.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🧠 What It Tracks

| Metric | What it means |
|---|---|
| **System prompt tokens** | Baseline overhead every session carries (your memory profile, instructions, etc.) |
| **Conversation tokens** | Cumulative cost of all turns — both your messages and Claude's replies |
| **Upload tokens** | PDFs, images, docs added to context |
| **Context window %** | How full Claude's 200k-token memory is |
| **Session budget %** | Approximate % of your 5-hour rolling window consumed |
| **Peak hours flag** | Whether you're in the window where Anthropic throttles limits faster |

---

## ⚙️ How It Works

Claude has no native token counter exposed to users. This skill reconstructs usage by:

1. **Counting every turn** in the current conversation
2. **Estimating tokens** using known tokenization ratios (English: ~1 token / 0.75 words, Arabic: ~1 token / 0.55 words, code: ~1 token / 3.5 chars)
3. **Adding baseline overhead** for system prompts and memory profiles
4. **Flagging peak hours** based on Anthropic's published throttle window (5am–11am PT / 3pm–9pm Beirut EEST)
5. **Generating actionable recommendations** based on load thresholds

**Accuracy:** ±15–25%. Good enough to make smart decisions. Not a substitute for the API's exact token counter.

---

## 📊 Token Estimation Reference

| Content type | Ratio |
|---|---|
| English prose | ~1 token per 0.75 words |
| Arabic text | ~1 token per 0.55 words |
| Code | ~1 token per 3.5 characters |
| PDF (10 pages) | ~8,000–15,000 tokens |
| Image upload | ~1,500 tokens flat |

---

## ⏰ Peak Hours (Anthropic throttle window)

Anthropic reduces the effective 5-hour session capacity during:

- **5:00 AM – 11:00 AM PT** (US Pacific)
- **1:00 PM – 7:00 PM GMT**
- **3:00 PM – 9:00 PM Beirut (EEST)**
- **4:00 PM – 10:00 PM Dubai (GST)**

During these hours, heavy tasks burn your budget faster. The weekly total stays the same — it's just distributed differently.

---

## 💡 Tips to Stretch Your Budget

1. **Start new chats for new topics** — every message re-sends the full history. A 40-turn conversation is expensive by turn 40.
2. **Use Projects for repeated files** — caching kicks in after the first query, dropping cost by 60–80%.
3. **Don't re-upload files** — once uploaded, reference by name. Re-uploading adds the same tokens again.
4. **Batch your prompts** — instead of 5 short messages, combine into 1. Same output, lower context overhead.
5. **Run heavy tasks off-peak** — before 3pm or after 9pm Beirut for full session value.

---

## 📁 Repo Structure

```
session-tracker/
├── SKILL.md       ← The skill Claude reads and executes
├── README.md      ← This file
└── LICENSE        ← MIT
```

---

## License

MIT — free to use, modify, and share.
