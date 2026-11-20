# Notes and Routine Brain

## Notes
- Store notes in `data/notes.json` as a UTF-8 JSON array. Each note has a stable ID, title, content, tags, created_at, and updated_at timestamps in UTC ISO-8601.
- Validate title (1–300 characters), content (1–10,000 characters), and tags (array of strings). Reject malformed input; do not silently discard a corrupt notes file.
- Listing returns stored records in insertion order. Never expose note contents in routine logs; log only identifiers and safe metadata.
- Use atomic replace when writing JSON so interrupted writes do not leave truncated files.

## Tasks
- Store tasks in `data/tasks.json` as a UTF-8 JSON array. Each task includes ID, title, priority, due, completed, created_at, and completed_at.
- Priorities are low, normal, high, or urgent. Completion is idempotent and must identify the task by its exact ID.
- List all tasks by default; filter open/pending and completed/done only when explicitly requested.
- Do not invent due dates or mark a task complete without a user command.

## Daily workflow
1. Review open tasks and recent notes.
2. Capture new notes with a short title and meaningful tags.
3. Add actionable tasks with priority and optional due information.
4. Complete tasks only after the user confirms completion or explicitly commands it.
5. Summarize changes using the stored task/note identifiers and actual results.

## Routine safety
- Do not schedule external notifications or recurring activity unless a configured GitHub Actions workflow actually provides it.
- Distinguish a proposed routine from an automated routine.
- Keep personal note/task data in the repository's designated data directory; do not put it in source code or workflow definitions.
