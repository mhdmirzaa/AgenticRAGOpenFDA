# Design system — "Leaflet" (warm medical hub)

The visual identity for the FDA drug-information assistant. It replaces the earlier
clinical cobalt "Monograph" look with a warm, human **medical hub / health
companion**: fresh emerald green on clean white, editorial-yet-friendly type, soft
generous shapes. Trustworthy but approachable — the feeling of a polished consumer
health app, not a sterile clinical tool and not corporate SaaS.

**Name — Leaflet.** A *patient information leaflet* is the exact real-world artifact
this product is built on (the printed drug information in every medicine box), and
"leaf" carries the fresh-green, growing, natural warmth of the identity. It's short,
human, and on-domain. (Rename in one place: the `BRAND` constant in `page.tsx` —
the developer can swap it freely.)

---

## The subject (what we designed from)

Not a clinical instrument this time — a **health companion**. The world is a friendly
pharmacy/health app: the medicine leaflet, the reassuring green of wellbeing, generous
white space that lets information breathe, soft rounded cards you want to touch. Warm
but still exact: every answer is grounded and cited.

**Signature moment (kept, restyled):** the right-hand **live evidence panel** — the
agent's reasoning shown as a friendly, animated "how we found this" trail (Safety →
Scope → Search → Grade → Decide), with graded chunks as soft PASS/FILTERED cards and
the preserved **Scope: <drug>** stage. Paired with a new **hub landing** (a warm
dashboard home) as the first hero moment.

---

## Tokens

### Palette (6 named roles — emerald + white, NOT blue, NOT the old soft-green)

| Role | Light | Dark | Why this, for THIS subject |
|---|---|---|---|
| **emerald** (hero / actions) | `#12a877` (500) · `#0b8e63` hover · `#e8f8f0` tint | `#2eb582` text · `#12a877` fill | The confident, **fresh saturated emerald** — used with intention on hero moments, primary actions, and accents. Vibrant wellbeing green, deliberately more saturated and self-assured than the old timid mint, and pointedly **not** the overused SaaS cobalt. |
| **paper** (bg / surface) | `#f4faf6` page · `#ffffff` card · `#eef6f1` sunken | `#0d1512` page · `#141d19` card | Clean **white / mint-white** with lots of breathing room — the calm, airy ground the green pops against. |
| **ink** (text) | `#161b18` → muted `#657069` → border `#d5ded9` | `#eef3f0` → muted `#94a49b` → border `#26302b` | A **warm green-neutral charcoal**, not cold slate and not pure black — readable and human. |
| **caution** (refusal / declined) | text `#a86a10` · bg `#fdf3e3` | text `#e6b45c` · bg `rgba(230,180,92,.12)` | A **serious warm amber** — the "not enough evidence" decline. Warm, never alarmist. |
| **danger** (blocked / FAIL) | `#dc2626` · text `#c01f1f` · bg `#fdecec` | text `#f08d8d` · bg `rgba(220,38,38,.14)` | A **clear, serious red** for safety-blocked states and filtered-out evidence. |
| **honey** (accent detail) | `#f4b740` | `#f4b740` | A tiny warm secondary used sparingly (streaming spark, small highlights) so the palette feels human, not mono-green. |

### Typography — editorial display + friendly body (not AI-safe geometric)

- **Fraunces** — display / headings / the wordmark. A soft, warm **editorial serif** with
  real "old-style" personality (opsz + soft terminals). It gives the hub a human,
  characterful voice — the opposite of a safe geometric default.
- **Plus Jakarta Sans** — body / UI. A friendly, modern, softly-rounded sans that reads as
  a polished consumer health app; highly legible for dense label text.
- **DM Mono** — the technical layer (chunk ids, drug/section tags, corpus/metrics). Warm,
  rounded mono — reads as intentional data, not decoration.

Set with intent: Fraunces at display sizes for warmth, Jakarta for calm reading, mono
labels in small caps with light tracking.

### Shape, radius, motion

- **Radius:** soft and generous — `10 / 14 / 18 / 24px` (`rounded-lg … rounded-3xl`).
  Friendly, approachable, consumer-app — a clear break from the precise 4–10px clinical
  radii of the old look.
- **Shadows:** soft, green-tinted, layered — cards feel liftable, not flat.
- **Motion:** gentle tokenized transitions; the evidence trail animates step-by-step (a
  soft emerald pulse while live). Fully disabled under `prefers-reduced-motion`.

### Layout

Two states, one smooth transition:
1. **Hub landing** (no conversation yet) — a warm dashboard: branded header, a one-line
   invitation, a hero **ask** bar, soft **stat tiles** (drugs indexed · growing daily ·
   chunks), friendly **quick-action tiles** (New session / Sync labels / Grow corpus),
   inviting **example-question cards**, and the warmly-styled disclaimer.
2. **Split-view workspace** (once asked) — conversation left (streaming, citation chips,
   history, input), the live **evidence panel** right. The hub folds away into the
   workspace on the first question.

```
HUB LANDING                                   WORKSPACE (after first question)
┌───────────────────────────────────┐        ┌──────────────────┬───────────────┐
│  🌿 Leaflet      health companion  │        │ conversation      │ ● live trail  │
│  Ask about any FDA-labeled drug —  │        │ ┌ you ──────────┐ │ 01 Safety  ✓  │
│  see exactly how the answer's found│        │ └───────────────┘ │ 02 Scope ▸ dox│
│  ┌ ask… ───────────────── [Ask] ┐  │        │ ┌ answer (Frau) ┐ │ 03 Search  ✓  │
│  └──────────────────────────────┘  │        │ │ …[1][2]       │ │ 04 Grade 4/8  │
│  ┌ 312 ┐ ┌ daily ┐ ┌ 2,935 ┐      │        │ └───────────────┘ │ ─────────────  │
│  │drugs│ │ grows │ │chunks │      │        │ [ ask a follow-up]│ ┌ PASS card ┐  │
│  └─────┘ └───────┘ └───────┘      │        └──────────────────┴───────────────┘
│  Try: warnings · dosage · interact │
│  ⚕ Informational only — not advice │
└───────────────────────────────────┘
```

---

## Critique vs. the AI-generic defaults (done before building)

- **Default #1 — cream + high-contrast serif + terracotta:** avoided. Ground is
  **white/mint** (not cream), accent is **emerald** (not terracotta); the serif is a soft
  *editorial* Fraunces used warmly, not a high-contrast Didone.
- **Default #2 — near-black + acid accent:** avoided (light, airy, green-not-acid).
- **Default #3 — corporate cobalt-blue SaaS:** explicitly rejected — the old Monograph
  cobalt is fully replaced; **no blue** as the identity color.
- **The old timid soft-green (`#6dad8b`):** replaced by a **more saturated, confident**
  emerald (`#12a877`) used deliberately against generous white space.

**One bold place:** the emerald hero (hub + primary actions + the live trail's pulse).
Everything else stays calm and white-spaced. **Accessory cut:** dropped the heavy
per-node trace colors and the mono "instrument" chrome — the warmth comes from type,
green, and soft cards, not decoration.

## Roadmap note (out of scope)

Web app (Next.js + TypeScript). A future mobile client would be React Native / Flutter
(the developer's mobile stack); these framework-agnostic tokens (hex, type roles, radii)
port directly.
