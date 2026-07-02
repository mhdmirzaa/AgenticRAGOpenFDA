---
name: llm-provider
description: "Provider-agnostic LLM + embedding layer for the RAG: swap between Gemini, OpenAI, Groq, and local Ollama via one config switch, with streaming generation and embeddings. Use when wiring an LLM provider, choosing between Gemini/OpenAI/Groq/Ollama, setting up embeddings, streaming tokens from a model, adding a fallback model, or keeping the model choice configurable. Triggers: 'llm provider', 'model config', 'gemini api', 'openai api', 'groq', 'ollama', 'local llm', 'embeddings', 'text-embedding', 'nomic-embed', 'streaming generation', 'swap model', 'model fallback', 'provider switch', 'zero cost llm', 'free tier llm'."
---

# LLM provider layer (provider-agnostic)

IRON LAW: The model is a config switch, never a hardcoded call site. One env var (`LLM_PROVIDER`) selects the backend. Nothing in the agent, retrieval, or API code names a specific vendor.

## Why provider-agnostic

For a graded assessment the total token volume is tiny (small corpus + golden set + demo), so total spend is < $1 on ANY provider. That means the right optimization is not sticker price — it's demo smoothness, answer quality, and having a fallback if the demo room has no internet. A config switch gives you all three and lets you escalate quality in one line if a hard question needs it.

## Best-value default (this project)

| Rank | Provider · model | ~Cost /1M (in/out) | Why |
|---|---|---|---|
| **Default** | **Gemini Flash-Lite / Flash** | ~$0.10/$0.40 (Lite); **free tier ~1,500 req/day, no card** | Hosted speed + quality at effectively $0; strongest free tier |
| Fastest/cheapest hosted | Groq Llama 3.1 8B | ~$0.05/$0.08 | 500+ tok/s, free dev tier |
| Reliable paid | OpenAI GPT-4.1 Mini / Nano | ~$0.40/$1.60 · ~$0.10/$0.40 | Best instruction-following |
| **Offline fallback** | **Ollama Llama 3.1 8B** | **$0** | True $0, offline, private; demo survives no-internet |

Embeddings (barely affects cost — pick one and use it for BOTH indexing and querying):
- Google `text-embedding-005` (~$0.006/1M) — cheapest hosted, pairs with Gemini
- OpenAI `text-embedding-3-small` (~$0.02/1M) — standard RAG default
- Ollama `nomic-embed-text` ($0) — local/offline

## The interface (implement once)

```python
# providers/base.py
class LLMProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...
    async def generate_stream(self, prompt: str): ...      # async generator of tokens
    async def complete(self, prompt: str) -> str: ...       # non-streaming (grading)

def get_provider() -> LLMProvider:
    name = os.environ.get("LLM_PROVIDER", "gemini")
    return {"gemini": Gemini, "openai": OpenAI,
            "groq": Groq, "ollama": Ollama}[name]()
```

Agent/retrieval/API code calls `get_provider()` — never a vendor SDK directly.

## Provider notes

- **Gemini:** free tier needs no card but has daily rate limits and free-tier data may train Google products (fine for a synthetic corpus). Use the streaming endpoint for token-by-token.
- **Groq:** OpenAI-compatible API; fastest inference; free dev tier with daily limits.
- **OpenAI:** most reliable instruction-following; needs a card; a few cents total here.
- **Ollama:** `ollama pull llama3.1:8b && ollama pull nomic-embed-text`; runs on localhost:11434; **warm up on startup** (one throwaway generation + embed) or the first demo query is slow.

## Rules that survive any provider
- Same embedding model for indexing AND querying — mismatches silently wreck retrieval.
- Keep each LLM sub-task small (binary grading, short rewrites) — reliable on cheap/small models.
- Stream generation for perceived speed; use non-streaming `complete()` for grading.
- No blocking calls on FastAPI's async path — async client or threadpool.

## Anti-patterns
- ❌ Hardcoding a vendor SDK in agent code. → go through `get_provider()`.
- ❌ Different embed models index vs query. → identical both sides.
- ❌ Optimizing sticker price when total spend is < $1. → optimize demo smoothness + fallback.
- ❌ No offline fallback. → keep Ollama wired for a no-internet demo room.
- ❌ No warm-up (Ollama). → cold first request.

## Pre-delivery checklist
- [ ] `LLM_PROVIDER` switches backend with no other code change
- [ ] At least two providers work end-to-end (default + Ollama fallback)
- [ ] Same embed model used for index + query
- [ ] Streaming generation yields incrementally
- [ ] Warm-up runs when provider is Ollama
