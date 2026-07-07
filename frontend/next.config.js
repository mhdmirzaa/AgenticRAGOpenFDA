/** @type {import('next').NextConfig} */

// The backend origin the browser is allowed to call (SSE + fetch). Kept in sync
// with NEXT_PUBLIC_API_URL so connect-src stays tight.
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Strict Content-Security-Policy for the UI. Untrusted content (LLM answers,
// citations, openFDA text) is rendered as React text — never HTML — so no
// inline execution is possible; the CSP is defense-in-depth. No unsafe-eval.
// IBM Plex is self-hosted by next/font (served from 'self'), so no font CDN.
const csp = [
  "default-src 'self'",
  // Next needs inline bootstrap/runtime scripts; unsafe-eval is NOT allowed.
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self' data:",
  `connect-src 'self' ${API}`,
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Permissions-Policy", value: "geolocation=(), microphone=(), camera=()" },
];

const nextConfig = {
  // Emit a self-contained server bundle for a slim multi-stage production image
  // (only the traced runtime deps ship — see frontend/Dockerfile + DEPLOYMENT.md).
  output: "standalone",
  poweredByHeader: false, // don't advertise the framework/version
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

module.exports = nextConfig;
