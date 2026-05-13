# mini-agent

<p align="center">
  <img src="icon.png" alt="mini-agent icon: stylized robot on a dark background" width="160" height="160" />
</p>

A minimal Python coding agent that runs an interactive loop with **Anthropic
(Claude)** or **OpenAI (GPT)**. The model gets four local tools: `read_file`,
`list_files`, `edit_file`, and `bash`. It emits textual tool calls; this
program runs them and feeds results back into the conversation.

Inspired by Mihail Eric's *The Emperor Has No Clothes*
([@emperor-has-no-clothes.html](emperor-has-no-clothes.html)).

## Install & run

```bash
uv sync
uv run mini-agent
```

On first run the agent prompts you to:

1. **Pick a provider** (Anthropic or OpenAI) and saves the choice to `.env`
   as `MINI_AGENT_PROVIDER`.
2. **Enter the API key** for that provider (`ANTHROPIC_API_KEY` or
   `OPENAI_API_KEY`).
3. **Pick a default model**, saved as `ANTHROPIC_MODEL` or `OPENAI_MODEL`.

Subsequent runs read everything from `.env` and skip the prompts. To switch
providers later, change `MINI_AGENT_PROVIDER` in `.env` (or unset it to be
asked again). See [`.env.example`](.env.example) for the full set of
variables.

To leave the session: **Ctrl-C** always works. On **Unix/macOS**, **Ctrl-D**
sends end-of-file. On **Windows**, **Ctrl-Z** then **Enter** for EOF (Ctrl-D is not EOF and may show as ``^D``).

## Project guides (optional)

If `AGENTS.md` or `CLAUDE.md` exists in the current working directory or any
parent directory, their contents are appended to the system prompt (nearest
directory first). Use that to give the model repo-specific conventions or
context.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or another way to install
  dependencies from `pyproject.toml`
- An Anthropic **or** OpenAI API key
- `bash` on `PATH` for the `bash` tool (Git Bash or WSL on Windows)

## Optional: standalone executable

To build a Windows binary with PyInstaller, install the build dependency group
and run the spec from the repository root:

```bash
uv sync --group build
uv run pyinstaller mini-agent.spec
```

Output is configured under `dist/windows/`. Details and icon notes live in
[`mini-agent.spec`](mini-agent.spec).

## Notes

No sandboxing, no streaming, no approval workflow. The agent can read, edit,
and execute shell commands in the working directory — run it only where you
are comfortable with that.

## License

[MIT](LICENSE)
