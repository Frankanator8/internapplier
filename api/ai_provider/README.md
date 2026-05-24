# api/ai_provider/

Thin abstraction over the LLM backend. Loads prompt templates from [`prompts/`](../../prompts/), formats them, calls the configured provider, and parses responses.

| File | Purpose |
|---|---|
| `provider.py` | Public surface — `complete`, `complete_json`, model selection, seeding. |
| `http_client.py` | Shared HTTP client + retry/timeout policy. |
| `prompts.py` | Loads and renders prompt templates from `prompts/`. |
| `formatting.py` | Message/role formatting helpers. |
| `settings.py` | Provider/model/key config (reads from `app_settings`). |
| `keyword_extractor.py` | Lightweight keyword utility used by resume scoring. |
| `errors.py` | Provider-specific exception types. |
