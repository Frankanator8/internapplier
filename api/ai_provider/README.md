# api/ai_provider/

Thin abstraction over the LLM backend. Loads prompt templates from [`prompts/`](../../prompts/), formats them, calls the configured provider, and parses responses.

| File | Purpose |
|---|---|
| `provider.py` | Public surface — `complete`, `complete_json`, model selection, seeding. |
| `http_client.py` | Shared HTTP client + retry/timeout policy. |
| `prompts.py` | Loads and renders prompt templates from `prompts/`. |
| `formatting.py` | Message/role formatting helpers. |
| `settings.py` | Provider/model/key config (reads from `app_settings`). |
| `errors.py` | Provider-specific exception types. |

## Provider routing

Every chat-completions payload includes `provider: {sort: "throughput"}`, so
OpenRouter picks the currently fastest endpoint instead of the cheapest.
This is the `provider` object, not the `:nitro` model-slug shortcut — nitro
also admits priority-tier endpoints (and their pricing). Append `:nitro` to a
model id in Settings if you want that.

## Stream timeouts

The read half of `OPENROUTER_STREAM_TIMEOUT` is a per-socket-read budget, not a
budget for the whole completion — OpenRouter's SSE keep-alive comments reset it,
so it only fires on genuine silence. The silence that matters is time-to-first-byte:
reasoning models on a large tool-loop transcript can spend minutes prefilling
before the response headers arrive, which is why the budget is generous.

A stream that dies from a timeout or dropped connection is retried
(`OPENROUTER_STREAM_MAX_RETRIES`) as long as nothing has been yielded to the
caller yet. Tool-calling rounds buffer their output rather than yielding it, so
they stay retryable for the whole round; plain streams lose that eligibility as
soon as the first chunk goes out. HTTP errors are not retried.
