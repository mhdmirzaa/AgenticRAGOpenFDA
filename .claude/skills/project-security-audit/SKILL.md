---
name: project-security-audit
description: >-
  Performs a structured, read-only security audit of a codebase. Use this skill
  whenever the user asks to "security check", "security audit", "review for
  vulnerabilities", "find security issues", "scan for secrets", "harden", or
  "is my project secure" — even if they don't say the word "security" but ask
  about leaked keys, exposed env vars, unsafe dependencies, auth problems, or
  injection risks. Tailored for JavaScript/TypeScript, Next.js, React Native,
  and Flutter/Dart projects. The audit only reads and reports; it never edits,
  pushes, or exfiltrates code, and never sends findings anywhere.
---

# Project Security Audit

A repeatable, defensive security review for web and mobile codebases. The goal
is to surface real risks and give the developer a prioritized, actionable
report — not to make changes automatically.

## Operating rules

- **Read-only by default.** Inspect files, run analysis tools, and report.
  Do NOT edit source, change config, install dependencies without asking, or
  run anything that mutates the repo or contacts external services with project
  data.
- **Never exfiltrate.** Do not paste secrets, tokens, or private code into web
  requests, search queries, or third-party tools. If a real secret is found,
  show only a masked fragment (e.g. `sk-live-…a91`) so the user can locate it.
- **Prioritize.** Every finding gets a severity: Critical / High / Medium / Low,
  plus a concrete fix. Lead the report with Critical and High.
- **No false confidence.** Flag things to verify rather than asserting a repo is
  "secure." Absence of a finding is not proof of safety.

## Workflow

Run these phases in order. Use the helper script for the secret/pattern sweep,
then reason through the rest manually.

### 1. Map the project
Detect the stack and entry points so the audit is relevant:
- Look for `package.json`, `next.config.*`, `app/` or `pages/` (Next.js),
  `pubspec.yaml` (Flutter), `android/` + `ios/` + `metro.config.js` (React Native).
- Note the package manager (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`).
- List where secrets/config live: `.env*`, CI files, `app.config.*`.

### 2. Secrets & sensitive data
Run `scripts/scan.sh <project-dir>` for a fast pattern sweep, then manually check:
- Hardcoded API keys, tokens, private keys, passwords, connection strings.
- `.env` / `.env.local` committed to git (check `git ls-files | grep -i env`).
- `.env*` present but missing from `.gitignore`.
- **Next.js specific:** any secret read without the `NEXT_PUBLIC_` rule in mind —
  anything prefixed `NEXT_PUBLIC_` is shipped to the browser. Flag secrets that
  are exposed client-side, and server-only secrets accidentally given that prefix.
- **React Native / Flutter specific:** secrets compiled into the app bundle are
  recoverable by anyone with the binary. Flag API keys, signing material, or
  backend URLs embedded in client code; recommend moving them server-side.

### 3. Dependencies
- Run the ecosystem auditor (ask before it touches the network):
  `npm audit --omit=dev` / `pnpm audit` / `yarn npm audit`, and for Flutter
  `dart pub outdated` / `flutter pub audit` if available.
- Flag known-vulnerable or unmaintained packages, and lockfile drift.
- Note any `postinstall` scripts in dependencies (supply-chain risk).

### 4. Application logic (read the code)
- **AuthN/AuthZ:** Are API routes / server actions / endpoints protected? Look
  for routes that read user data with no session check. In Next.js, check
  `app/api/*`, route handlers, and server actions for missing auth guards.
- **Injection:** Raw SQL string concatenation, `dangerouslySetInnerHTML`,
  `eval`, `child_process` with user input, unsanitized shell/HTML/template input.
- **SSRF / open redirect:** server-side `fetch` to user-controlled URLs;
  redirects to user-supplied locations.
- **Input validation:** untrusted input reaching the DB, filesystem, or render
  without validation (zod/schema checks absent).
- **Secrets in logs:** tokens or PII written to `console.log` / analytics.
- **CORS & headers:** overly permissive CORS (`*` with credentials), missing
  security headers / CSP.
- **File uploads:** unrestricted type/size, path traversal.
- **Mobile transport:** cleartext HTTP allowed (Android `usesCleartextTraffic`,
  iOS ATS exceptions), missing cert handling for sensitive apps.

### 5. Config & infrastructure
- CI/CD secrets handling; secrets printed in build logs.
- Overly broad permissions in GitHub Actions (`permissions: write-all`).
- Exposed debug/admin endpoints, source maps shipped to prod with secrets.
- `.gitignore` coverage for `.env`, build artifacts, keystores, `*.p8`/`*.jks`.

### 6. Report
Produce a single prioritized report:
```
## Security Audit — <project>
Stack: <detected>   Date: <date>

### Critical (fix now)
- [finding] — file:line — why it matters — how to fix

### High
### Medium
### Low / Hygiene

### What I could NOT verify
- <runtime config, server-side env, infra outside the repo, etc.>
```
End by reminding the user this is a code-level review, not a penetration test,
and that secrets found in git history may need rotation + history scrubbing
(e.g. via `git filter-repo`/BFG) — not just deletion from the current commit.

## What this skill does NOT do
- It does not exploit, attack, or test live systems.
- It does not modify code or rotate credentials for the user.
- It does not guarantee the absence of vulnerabilities.
