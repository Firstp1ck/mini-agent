# mini-agent

A minimal Python coding agent that gives an Anthropic model four local tools:
`read_file`, `list_files`, `edit_file`, `bash`. The model emits textual tool
calls, Python runs them, results are fed back into the conversation.

Inspired by Mihail Eric's
["The Emperor Has No Clothes"](https://www.mihaileric.com/The-Emperor-Has-No-Clothes/).

## Install & run

```bash
uv sync
uv run mini-agent
```

On first run the agent prompts for your `ANTHROPIC_API_KEY` (and a model
choice) and saves them to `.env`.

## Requirements

- Python 3.11+
- An Anthropic API key
- `bash` on `PATH` for the `bash` tool (Git Bash or WSL on Windows)

## Notes

No sandboxing, no streaming, no approval workflow. The agent can read, edit,
and execute shell commands in the working directory — run it only where you
are comfortable with that.

## License

[MIT](LICENSE)
