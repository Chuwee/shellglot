# shellglot

Ask your terminal for a command in plain words and get live suggestions, each one with a key over every part of the command and an explanation of what that part does.

```
(sglot) $ sglot delete log files older than a week
 [1] Delete .log files older than 7 days  ⚠ destructive
      a   b       c           d        e
     ╭┴─╮ ┴ ╭─────┴─────╮ ╭───┴───╮ ╭──┴──╮
     find . -name '*.log' -mtime +7 -delete
     a  find           walk the directory tree looking for matches
     b  .              start from the current directory
     c  -name '*.log'  only files whose name ends in .log
     d  -mtime +7      last modified more than 7 days ago
     e  -delete        remove every match (no confirmation!)
 [2] ...

 press 1-3 to edit and run · Enter for 1 · any other key to cancel
```

When a suggestion uses an external dependency (a program that isn't part of a standard install of your OS, like `fd`, `rg` or `jq`), its header says so with `⬡ needs fd`. shellglot checks your `PATH`: if the program is missing, the header marks it as not installed and a line under the suggestion gives the command to install it.

Suggestions appear one by one as the model streams them. Pick one with its number: bash puts it on an editable line (Enter runs it, Ctrl-C cancels), and zsh puts it in your next prompt.

## Install

```sh
./install.sh            # creates .venv with the Anthropic SDK and adds the hook to ~/.bashrc or ~/.zshrc
./install.sh --no-rc    # same, without touching your rc file
```

Then open a new terminal. The first time you ask for a suggestion, shellglot offers to set up an LLM provider, already filled in with what it finds on your machine: the Codex CLI, an `ANTHROPIC_API_KEY`, or a local Ollama. Run `shellglot config` to change it later.

With the `codex` provider, suggestions arrive all at once after a few seconds, because Codex only reports a message when it's complete. The `anthropic` and `openai` providers stream them in one by one.

## Use

| Command | What it does |
|---|---|
| `shellglot on` | enter shellglot mode; the prompt shows `(sglot)` |
| `sglot <prompt>` | suggest commands (in shellglot mode) |
| `shellglot off` | leave shellglot mode |
| `shellglot <prompt>` | one-off suggestion without entering the mode |
| `shellglot config` | choose provider, model, API key, number of suggestions |

Globs in the prompt are not expanded (`sglot remove *.tmp files` works), but quotes still need to be balanced, so write `whats` or quote the whole prompt.

Set `SHELLGLOT_AUTO_ON=1` before sourcing `shellglot.sh` to start every shell in shellglot mode.

## Providers

Settings live in `~/.config/shellglot/config.json` (mode 600):

| Key | Default | Notes |
|---|---|---|
| `provider` | `codex` | `codex` (runs your local Codex CLI, so it uses your ChatGPT subscription; no API key), `anthropic`, `openai` (any OpenAI-compatible server: OpenAI, Ollama, LM Studio, OpenRouter) or `demo` (canned output, no network) |
| `model` | `gpt-5.6-luna` | e.g. `claude-opus-5-5` or `claude-haiku-5-5` on Anthropic, `llama3.2` on Ollama |
| `effort` | `low` | codex and anthropic; `""` to omit |
| `api_key` | `""` | empty uses `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` |
| `base_url` | `""` | empty uses the provider default (`http://localhost:11434/v1` for `openai`) |
| `suggestions` | `3` | 1–9 |
| `send_context` | `true` | sends your OS, shell, cwd and the names of up to 40 entries in cwd so suggestions fit your machine |

## Privacy

With `send_context` on, the model provider sees the current directory path and the names of the files in it. Turn it off in `shellglot config` if that matters. No command runs without you choosing it and pressing Enter.
