# Security Policy

## Supported versions

Only the latest minor release receives security fixes. After v1.0, the policy is:

| Version | Supported |
|---------|-----------|
| 0.x     | latest minor only |
| 1.x     | latest minor + previous minor for 6 months |

## Reporting a vulnerability

**Do NOT open a public GitHub issue for security reports.**

Instead:

- Email: `luizhcrs@gmail.com` with subject `[SECURITY] template-engine`
- Or open a [private security advisory](https://github.com/Luizhcrs/template-engine/security/advisories/new)

Include:

- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact

You'll get an acknowledgment within 48 hours and a status update within 5 business days. Coordinated disclosure with credit is the default.

## Threat model

### What template-engine guards against

- **Path traversal** in `preset_loader`: `user_sub` is validated, paths resolved + bounded with `is_relative_to()`.
- **Prompt injection** in `llm_mapper`/`preset_creator`: untrusted document content is delimited (`<<<UNTRUSTED_*_*>>>`) and the system instruction explicitly directs the LLM to ignore commands inside delimiters.
- **No implicit network/filesystem I/O outside declared APIs.**

### What template-engine does NOT guard against

- **Adversarial document content extracting confidential data via the LLM.** If you feed sensitive data alongside untrusted documents in the same prompt, an attacker may be able to exfiltrate. Use a clean LLM context per untrusted document.
- **LLM hallucination.** Outputs are not guaranteed to match the source. Always validate critical fields.
- **DoS via large documents.** Source/gold doc truncation is enforced (12000/8000 chars by default), but extracting a 1GB PDF still loads memory. Limit input sizes upstream.
- **Provider-side data retention.** Whatever the LLM provider logs/retains is outside our control. Configure provider settings (e.g. OpenAI `data_retention=0`, Gemini disable improvement-mode) per your needs.

## Best practices for callers

1. **Validate `user_sub` upstream too.** `preset_loader` enforces `^[a-zA-Z0-9_-]{1,64}$` but constraining it earlier is defense-in-depth.
2. **Run untrusted document conversion in a separate LLM session/key** from sessions that handle confidential org data.
3. **Set `temperature=0`** (already default) — reduces non-determinism.
4. **Validate LLM output against `preset.schema_json`** — call `validator.validate()` and check `confidence_label()` before trusting downstream.
5. **Sandbox file outputs**: write `.docx` to a temporary directory you control, not directly to user-accessible paths.

## Disclosure history

None yet.
