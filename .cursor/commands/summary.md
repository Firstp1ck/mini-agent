# summary

Create or update a commit summary document in `Release-docs/` using a **developer-focused, concise writing style**.

## Goal
- Summarize recent changes in one clear view.
- Focus on what was **added/changed/fixed**.
- Keep it technical enough for developers, but easy to scan.

## Required workflow
- Re-check git history for the requested date range before writing.
- Use commit messages as the source of truth and verify with changed code when needed.
- Merge overlapping points into one bullet (avoid duplicates).
- Integrate new commits into the existing summary content (do not append a separate "new commits" block).

## Writing style
- Clear, concise, and direct.
- No long narrative paragraphs.
- No "What improved" or business/marketing language.
- Prefer concrete technical statements (modules, runtime behavior, config keys, export logic, startup flow, packaging).
- Keep each bullet to one change cluster.

## Output format
Use this structure:

```markdown
# Summary (DD.MM.YYYY - DD.MM.YYYY)

## Added and Updated (One View)

- ...
- ...
- ...
```

## Content rules
- Group related changes into compact bullets (example groups: LiveView/export, startup/runtime, UI/config architecture, packaging/release).
- Mention versions only when relevant to shipped outcome.
- Exclude noise (meta commits, typo-only docs changes, tooling-only changes) unless they affect runtime behavior or release output.
- Keep the final section short and scannable.
