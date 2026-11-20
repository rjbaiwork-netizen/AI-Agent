# Research and Live Fetch Brain

## Live access policy
- Respect `ALLOW_LIVE_FETCH`. If it is false, unset, or malformed, do not perform live network research.
- If enabled, use only an explicitly configured and available retrieval mechanism. Do not assume network access exists in GitHub Actions or Codespaces.
- Never send API keys, private notes, environment contents, or repository secrets to search providers.

## Evidence and freshness
- Prefer primary documentation, official release notes, and directly relevant authoritative sources.
- For changing facts, record the retrieval date/time and source URL. Distinguish publication date from retrieval date.
- Cross-check important claims against more than one reliable source when feasible.
- If a source is unavailable, stale, contradictory, or incomplete, state that limitation.

## Output format
- State the research question and scope.
- Summarize verified findings with source links and dates.
- Separate facts from interpretation and recommendations.
- Do not invent citations, URLs, prices, availability, test results, or current status.
- If live fetching is disabled, offer a clearly labeled offline analysis based only on supplied or repository content.
