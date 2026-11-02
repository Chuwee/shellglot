# shellglot

Ask your terminal for a command in plain words and get live suggestions, each one with a key over every part of the command and an explanation of what that part does.

```
$ shglot delete log files older than a week
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

 press 1-3 to copy · Enter for 1 · any other key to cancel
```

When a suggestion uses an external dependency (a program that isn't part of a standard install of your OS, like `fd`, `rg` or `jq`), its header says so with `⬡ needs fd`. shellglot checks your `PATH`: if the program is missing, the header marks it as not installed and a line under the suggestion gives the command to install it.

Suggestions appear one by one as the model streams them. Pick one with its number and it's copied to your clipboard: paste it at your prompt, change it if you like, and press Enter. With the optional [shell hook](#shell-hook), the pick goes straight onto your prompt instead.

Copying uses your OS's clipboard tool: `pbcopy` on macOS, `wl-copy` on Wayland, `xclip` or `xsel` on X11, `clip.exe` on WSL and `termux-clipboard-set` on Termux. Without one, and always over SSH (where those tools would fill the remote machine's clipboard), shellglot asks your terminal to copy with OSC 52, which most modern terminals and tmux support.

## Install

**Homebrew** (macOS and Linux):

```sh
brew install chuwee/shellglot/shellglot
```

**apt** (Debian and Ubuntu):

```sh
curl -fsSL https://chuwee.github.io/shellglot/shellglot.gpg | sudo tee /usr/share/keyrings/shellglot.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/shellglot.gpg] https://chuwee.github.io/shellglot ./' | sudo tee /etc/apt/sources.list.d/shellglot.list
sudo apt update && sudo apt install shellglot
```

That's all you need: the command is `shglot`, so run `shglot <what you want to do>`.

**From a checkout:**

```sh
./install.sh        # links the shglot command into ~/.local/bin
./install.sh --rc   # same, and adds the optional shell hook to ~/.bashrc or ~/.zshrc
```

### Shell hook

The hook is optional. With it, a picked command lands on an editable line (bash) or in your next prompt (zsh) instead of the clipboard, it goes into your history, and you get `sglot` mode. Add this line to `~/.bashrc` (or `~/.zshrc`, with `zsh`), or run `./install.sh --rc`:

```sh
eval "$(shglot init bash)"
```

Then open a new terminal. The first time you ask for a suggestion, shellglot offers to set up an LLM provider, already filled in with what it finds on your machine: Claude Code, the Codex CLI, an `ANTHROPIC_API_KEY`, or a local Ollama. Run `shglot config` to change it later.

shellglot needs nothing but Python 3.8 or later: it talks to APIs with the standard library, and to Claude Code and Codex through their own CLIs.

With the `codex` provider, suggestions arrive all at once after a few seconds, because Codex only reports a message when it's complete. The other providers stream them in one by one.

## Use

| Command | What it does |
|---|---|
| `shglot <prompt>` | suggest commands; the one you pick is copied (or put on your prompt, with the hook) |
| `shglot config` | choose provider, model, API key, number of suggestions |
| `shglot on` | enter shellglot mode, where the prompt shows `(sglot)` (needs the hook) |
| `sglot <prompt>` | suggest commands (in shellglot mode) |
| `shglot off` | leave shellglot mode |

In shellglot mode, globs in the prompt are not expanded (`sglot remove *.tmp files` works), but quotes still need to be balanced, so write `whats` or quote the whole prompt.

Set `SHELLGLOT_AUTO_ON=1` before sourcing `shellglot.sh` to start every shell in shellglot mode.

## Providers

Settings live in `~/.config/shellglot/config.json` (mode 600):

| Key | Default | Notes |
|---|---|---|
| `provider` | `codex` | `claude` (runs your local Claude Code, so it uses your Claude subscription; no API key), `codex` (runs your local Codex CLI, so it uses your ChatGPT subscription; no API key), `anthropic` (the Anthropic API with an API key), `openai` (any OpenAI-compatible server: OpenAI, Ollama, LM Studio, OpenRouter) or `demo` (canned output, no network). First-run setup picks the first one it finds, in that order |
| `model` | `gpt-5.6-luna` | e.g. `claude-opus-5-5` or `claude-haiku-5-5` with `claude` or `anthropic`, `llama3.2` on Ollama |
| `effort` | `low` | claude, codex and anthropic; `""` to omit |
| `api_key` | `""` | empty uses `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` |
| `base_url` | `""` | empty uses the provider default (`http://localhost:11434/v1` for `openai`) |
| `suggestions` | `3` | 1–9 |
| `send_context` | `true` | sends your OS, shell, cwd and the names of up to 40 entries in cwd so suggestions fit your machine |

## Privacy and safety

With `send_context` on, the model provider sees the current directory path and the names of the files in it. Turn it off in `shglot config` if that matters.

Treat suggestions as untrusted text from the model, and read a command before you run it:

- No command runs without you choosing it and pressing Enter.
- **⚠ destructive** comes from the model *or* from shellglot's own check of the command (`rm`, `sudo`, `> file`, `find -delete`, `git reset --hard`, piping into a shell, package installs and more). The check can only add the label, never remove it, but it is a heuristic: no label doesn't mean safe.
- Anything the model writes is cleaned before it reaches your terminal: escape sequences and other control or invisible characters are shown as `�`. A suggested command containing any of them (including a newline or a bidi override) is dropped, so it can never be copied or put on your prompt.
- With the `claude` provider, Claude Code runs in a fresh empty directory with no tools at all, without your settings, MCP servers or saved sessions, and shellglot stops it if it starts any tool call anyway.
- With the `codex` provider, Codex runs in a read-only sandbox in a fresh empty directory, with its shell, code, browser, app and web search tools switched off, and shellglot stops it if it starts any tool call anyway.

## Releasing

Bump `__version__` in `shellglot.py`, then push a matching tag (`git tag v0.2.0 && git push origin v0.2.0`). The `release` workflow builds the `.deb`, attaches it to a GitHub release, adds it to the signed apt repository on the `gh-pages` branch (served by GitHub Pages), and updates the formula in [Chuwee/homebrew-shellglot](https://github.com/Chuwee/homebrew-shellglot). It needs two repository secrets: `APT_GPG_PRIVATE_KEY` (the key that signs the apt repository) and `HOMEBREW_TAP_TOKEN` (a fine-grained token that can write to the tap). Build a `.deb` locally with `packaging/deb/build.sh`.

## License

MIT
