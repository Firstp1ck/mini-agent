Create a new release file in the Projects releases directory (Release-docs/RELEASE_v{version}.md) for the given version and automatic generate the release notes, check for changes from the last release.

**File Format:**
```markdown
# Release v{version}

## Overview
...
```
The first two lines ("# Release v{version}" and empty line) are automatically stripped when publishing to GitHub releases, so the release notes start with "## Overview".

**Guidelines:**
- Keep the release file User-friendly, short, concise and clear and NON-Technical! (Use Git Commits as additional information)
- Only Application related changes should be included in the release notes
- No Development related changes should be included in the release notes
