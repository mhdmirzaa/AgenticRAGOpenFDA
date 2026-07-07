# Design system — "Monograph"

The visual identity for the FDA drug-information assistant. It replaces the earlier
soft-green "Verdant" health-assistant look with a deliberate, subject-grounded identity:
**an official drug monograph rendered as a live clinical instrument.** Trustworthy, exact,
a little scientific — never cutesy.

The product is renamed **Formulary** — a real pharmacy term for the curated, authoritative
drug reference a clinician actually consults. The name states the point of view.

---

## The subject (what we designed from)

Not "a friendly health chatbot." The real subject is the **pharmacopoeia / drug monograph**:
official FDA labels, section-by-section reference prose, clinical precision, analytical
instruments, dosage tables, the ℞ mark. Every choice below is derived from that world.

**Signature (the one memorable thing):** the right-hand evidence panel is presented as a
**live clinical-reference instrument** — the agent's reasoning shown as an exact, ordered
*assay log* (safety → route → scope → search → grade → decide → answer), and the graded
chunks styled as **monograph citations** (drug + section rendered as a `[DOXYCYCLINE ·
CONTRAINDICATIONS]` reference tag, with a serious assay verdict). A single cyan "instrument
live" signal animates only while the agent is reading. Everything else stays quiet.

---

## Tokens

### Palette (6 named roles — not soft-green, not the three AI defaults)

| Role | Light | Dark | Why this, for THIS subject |
|---|---|---|---|
| **paper** (page/surface) | `#E8EDF3` page · `#FFFFFF` card | `#0B131E` page · `#121D2B` card | A cool, clean off-white — reference paper under clinical light. Explicitly **not cream** (cream + serif is AI-default #1). |
| **ink** (text/structure) | `#14212E` → muted `#48586B` → border `#D3DBE4` | `#E7ECF3` → muted `#93A2B4` → border `#243447` | A deep **navy-slate**, not pure black — the printed ink of an official reference. Authority without harshness. |
| **cobalt** (accent / interactive) | `#2743C0` · hover `#1E349B` | `#7C93F5` text · `#3A55D6` fill | One confident accent, used with restraint (primary action, links, citation chips, PASS). Reads as **fountain-pen / official-document ink**, deliberately deeper and more ultramarine than generic SaaS blue. |
| **cyan** (instrument-live signal) | `#0FB5C9` | `#2CD0E4` | The **analytical-instrument readout** color (spectrometer / oscilloscope trace). Appears **only** in the evidence panel and **only while live** — the single bold spark. |
| **caution** (refusal / insufficient evidence) | text `#9A5B00` · bg `#FBF2DF` | text `#E0B064` · bg `rgba(224,176,100,.12)` | A **serious amber** — the drug-caution triangle / amber prescription bottle. Signals "declined for lack of evidence," never alarm. |
| **danger** (blocked / FAIL) | `#C6302B` · text `#B3241F` · bg `#FBE9E8` | text `#F0908B` · bg `rgba(198,48,43,.14)` | A **clinical red**, not neon — safety-blocked states and rejected evidence. Serious, legible, non-panic. |

Two accents, strictly separated by role: **cobalt = brand/interactive everywhere**;
**cyan = the live instrument only**. That separation is what makes the panel feel like an
instrument rather than a themed page.

### Typography — the IBM Plex superfamily (engineered, clinical, not default-system)

Chosen because Plex is *purpose-built and mechanical* — it reads as scientific reference,
and pointedly avoids both the generic system-font look and the AI-default high-contrast serif.

- **IBM Plex Sans** — UI, headings, wordmark. Precise humanist grotesk with real personality.
- **IBM Plex Serif** — the **answer prose only**. Long cited clinical text reads like a printed
  monograph, not a chat bubble. (This is a *body* serif on cool paper — not the cream-background
  high-contrast display serif of AI-default #1.)
- **IBM Plex Mono** — the **reference-data layer**: chunk ids, drug/section tags, the stage/assay
  log, metrics, corpus count. Monospace *is* the texture of reference data; it reads as
  intentional, not decorative.

Type scale is deliberate: mono labels are **uppercase with +0.06em tracking** (instrument
labels); the wordmark is Plex Sans 600 with tight tracking; answer prose is Plex Serif at a
comfortable reading measure.

### Structure, radius, motion

- **Radius:** small and precise — `4 / 6 / 10px` (`--radius-*`). Off the friendly `rounded-2xl`
  soft look, but not zero-radius (that's AI-default #3, the broadsheet). Precise, not harsh.
- **Rules over shadows:** the instrument reads through **hairline ink rules and tick marks**,
  with only faint cool shadows on raised cards.
- **Motion:** tokenized (`--motion-fast 120ms / --motion 200ms / --motion-slow 380ms`). One
  orchestrated moment — the cyan "reading" scan on the live panel; a precise per-stage step.
  Fully disabled under `prefers-reduced-motion` (states stay legible without it).

### Layout

Keep the split view (it's genuinely good): **conversation left, instrument right.** The left is
quiet ink-on-paper reading; the right is the signature instrument. On mobile the panel stacks
below the conversation and keeps the same instrument identity.

```
┌───────────────────────────────────────────────┬────────────────────────────┐
│  ℞ FORMULARY            corpus · 2,935 chunks  │  ASSAY ▸ live ●            │  ← instrument header
│  ───────────────────────────────────────────  │  ────────────────────────  │
│  ⚕ Informational only — not medical advice     │  01 SAFETY      ✓ clear    │
│                                                │  02 ROUTE       ✓          │
│  ┌─ you ────────────────────────────────────┐ │  03 SCOPE  ▸ doxycycline   │  ← Scope stage (preserved)
│  │ warnings for ibuprofen?                   │ │  04 SEARCH      ✓ 8 found  │
│  └───────────────────────────────────────────┘ │  05 GRADE       4 / 8      │
│  ┌─ answer (Plex Serif monograph) ──────────┐  │  ────────────────────────  │
│  │ Ibuprofen may increase risk of … [1][2]  │  │  MONOGRAPH CITATIONS       │
│  └───────────────────────────────────────────┘ │  ┌ IBUPROFEN ───── ✓ PASS ┐│
│                                                │  │ [·WARNINGS]  …text…  ↗  ││
│  [ Ask about a drug's warnings, dosage … ] Ask │  └────────────────────────┘│
└───────────────────────────────────────────────┴────────────────────────────┘
```

---

## Critique vs. the AI-generic defaults (done before building)

Worked through "what would the generic answer be?" and moved off each axis:

- **Default #1 — cream + high-contrast serif + terracotta (~#D97757):** avoided. Base is a
  **cool** clinical off-white (`#E8EDF3`), not cream; the accent is **cobalt ink**, not
  terracotta; the serif is a **body** face for monograph prose on cool paper, not a warm
  display serif. No `#D9xxxx` warm-clay anywhere.
- **Default #2 — near-black + one acid accent:** avoided. Light-first, ink-navy (not black);
  the accents are a disciplined cobalt + a role-restricted cyan, neither an acid-green/vermilion
  "hero" color.
- **Default #3 — broadsheet hairlines + zero radius + dense columns:** partially borrowed the
  *honesty* of rules (fitting for an instrument) but kept **precise 4–10px radii** (not zero)
  and generous reading measure (not dense newspaper columns).
- **The old soft-green health tell (`#6dad8b` sage):** fully removed from tokens, components,
  and copy. The leaf 🌿 mark and "Verdant" name are gone; the mark is now a precise **℞**
  logotype.

**One risk taken (justified):** the evidence panel as a *live instrument* with a cyan assay
signal and a monospace log — more opinionated than a neutral "sources" list, but it's the
truest expression of the subject and the thing the product will be remembered by.

**Self-critique accessory cut:** the decorative streaming "pill" cursor and per-node rainbow
trace colors are dropped in favor of a single precise mono caret and one ink/cobalt trace scale —
less color noise, more instrument.

---

## Roadmap note (out of scope here)

This is the web app (Next.js + TypeScript / React — the primary stack). If a mobile client is
added later it would be **React Native / Flutter** (the mobile stack); the token values above
(hex, type roles, radii, motion) are framework-agnostic and would port directly.
