# mini-agent

A minimal Python coding agent based on the loop described in Mihail Eric's
["The Emperor Has No Clothes"](https://www.mihaileric.com/The-Emperor-Has-No-Clothes/).

It gives an Anthropic model four local tools:

- `read_file(filename)`
- `list_files(path)`
- `edit_file(path, old_str, new_str)`
- `bash(command, timeout=30)`

The model emits textual tool calls, Python executes them locally, and tool results
are fed back into the conversation.

## Setup

```bash
uv sync
uv run mini-agent
```

On first run, if `.env` is missing or `ANTHROPIC_API_KEY` is not set, the agent
prompts for your key and saves it to `.env`. If `ANTHROPIC_MODEL` is missing, it
fetches the current Anthropic model list, asks you to choose one, and saves that
selection to `.env` too.

Optional manual setup:

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY / ANTHROPIC_MODEL
```

## Run

```bash
uv run mini-agent
```

Example prompt:

```text
Create hello.py with a function that returns "hello world".
```

## Notes

This is intentionally small and educational. It has no sandboxing, streaming,
context compaction, or approval workflow. Run it only in a workspace where you
are comfortable allowing file edits and shell commands.
