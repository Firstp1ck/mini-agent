# mini-agent

A minimal Python coding agent that gives an Anthropic (Claude) or OpenAI
(GPT) model four local tools: `read_file`, `list_files`, `edit_file`,
`bash`. The model emits textual tool calls, Python runs them, results are
fed back into the conversation.

Inspired by Mihail Eric's
["The Emperor Has No Clothes"](https://www.mihaileric.com/The-Emperor-Has-No-Clothes/).

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

## Requirements

- Python 3.11+
- An Anthropic **or** OpenAI API key
- `bash` on `PATH` for the `bash` tool (Git Bash or WSL on Windows)

## Notes

No sandboxing, no streaming, no approval workflow. The agent can read, edit,
and execute shell commands in the working directory — run it only where you
are comfortable with that.

## License

[MIT](LICENSE)
