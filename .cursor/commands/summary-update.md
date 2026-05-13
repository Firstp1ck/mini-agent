# summary-update

Update an existing commit summary document in `Release-docs/` using a **developer-focused, concise writing style**.

## Goal
- Refresh an existing summary with new commits and corrected clustering.
- Keep one consolidated technical overview (no split between old and new blocks).
- Preserve readability for quick developer scan.

## Required workflow
- Re-check git history for the summary's date range and the newly requested extension.
- Use commit messages as the source of truth and verify with changed code when needed.
- Edit the existing summary in place instead of rewriting structure unnecessarily.
- Integrate new commits into the same bullets where they belong (merge overlapping points).
- Remove or rewrite outdated bullets if newer commits changed behavior.

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
- Keep a single combined "Added and Updated (One View)" section.
- Group related changes into compact bullets (example groups: LiveView/export, startup/runtime, UI/config architecture, packaging/release).
- Mention versions only when relevant to shipped outcome.
- Exclude noise (meta commits, typo-only docs changes, tooling-only changes) unless they affect runtime behavior or release output.
- Keep the final section short and scannable.
