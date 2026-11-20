# Logs and Issues Brain

## Log formats
- `logs/bot.log` is append-only human-readable operational history. Each entry starts with a UTC ISO-8601 timestamp and includes event, status, and safe structured metadata.
- `logs/trace.jsonl` contains exactly one valid JSON object per non-empty line. Records include timestamp, event_type, status, source, and payload.
- Never store credentials, authorization headers, full environment dumps, or sensitive note/task content in logs.

## Diagnosis sequence
1. Identify the failing component and exact timestamp.
2. Read the relevant Actions run, job, and step logs; do not infer execution from a workflow file alone.
3. Check Python version, installed requirements, working directory, import path, environment variable names, and file permissions.
4. Validate JSON files with a JSON parser and each non-empty JSONL line independently.
5. Compare the error with the latest successful commit and report the first concrete failing operation.

## Recovery
- Preserve the original corrupt file before attempting repair; never silently replace malformed user data with an empty array.
- Use atomic file replacement for repairs and report the backup location.
- For Git push conflicts, fetch and rebase only when safe. Abort on conflicts; never force-push over main.
- Retry transient network/API failures a bounded number of times and record the final error without secrets.
- After a fix, rerun the smallest relevant test and then the full affected workflow.

## Status vocabulary
- success: operation completed and evidence is available.
- degraded: service responds but one or more checks fail.
- failed: required operation could not complete.
- unverified: no execution evidence is available.
