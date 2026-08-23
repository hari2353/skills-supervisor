# Security Notes

Orchestrators inherit the risk of everything they can reach — controls reflect that.

## Controls in place

- **Delegation containment**: the A2A skills subagent accepts a closed enum of four skills; unknown skills
  are rejected before any network call. Engine outages return structured failures, never stack traces
- **Tool-call hygiene**: LLM tool arguments are parsed as strict JSON objects; dispatch failures are captured
  per-call and fed back as tool messages (no process-level leakage); loop capped at 6 rounds
- **No prompt content in logs**: chat transcripts live in memory for the request duration only
- **LLM keys via env only** (`SKILLS_LLM_API_KEY`), never logged or persisted; no LLM configured = clean 503,
  not a crash
- **MCP registry validates entries** (name, transport, endpoint required) before persistence
- **Security headers** (`nosniff`) on all responses

## Known gaps (deliberate for demo scope)

- `/chat` performs no authN — production would sit behind auth-gateway bearer checks with per-user rate limits
- Tool-calling LLM output is treated as semi-trusted: arguments are JSON-validated but values (e.g., free text)
  flow to skills-engine, which treats all input as untrusted by design
