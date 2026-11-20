# Coding and Security Brain

## Secure configuration
- Store local configuration in an ignored `.env` file; keep only safe variable names and non-secret defaults in `.env.example`.
- Read `GEMINI_API_KEY` and other credentials from environment variables or GitHub Actions secrets. Never commit their values or print them.
- Set debug mode off by default and bind to `0.0.0.0` only when required for Codespaces forwarding.
- Do not treat a private repository as a substitute for secret management.

## Input and data validation
- Validate type, required fields, maximum lengths, allowed enum values, and collection shapes at API and tool boundaries.
- Parse JSON strictly. A corrupt file is an explicit error, not an empty dataset.
- Use JSON serialization rather than string concatenation for structured records.
- Write JSON through a temporary file in the same directory, flush/fsync, then atomically replace the destination.
- Restrict file paths to fixed application directories; never accept arbitrary filesystem paths from user input.

## Runtime safety
- Catch expected exceptions at API boundaries and return non-secret diagnostics with correct status codes.
- Use bounded timeouts, bounded retry counts, and explicit maximum plan steps.
- Avoid shell execution for user-provided text. Never use eval or dynamically execute model-generated code.
- Treat model tool calls as untrusted: require an allowlisted tool name and schema-validated JSON arguments.
- Do not claim a timed-out thread was forcibly terminated; Python thread cancellation is cooperative.

## Git and automation
- Grant only required GitHub Actions permissions. Serialize workflows that update shared JSON/log files.
- Stage only intended paths, fetch before pushing, reject rebase conflicts, and never force-push main.
- Keep dependencies pinned or bounded and update them deliberately.
- Add tests for storage corruption, invalid inputs, missing brains, malformed JSONL, and tool timeouts.
