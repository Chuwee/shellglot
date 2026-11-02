#!/usr/bin/env python3
"""shellglot: quick shell command suggestions from an LLM, with every part of the command explained."""

import argparse
import getpass
import itertools
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

CONFIG_DIR = os.path.join(os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config'), 'shellglot')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
OLD_CONFIG_DIR = os.path.join(os.path.dirname(CONFIG_DIR), 'bashglot')  # before the rename to shellglot

DEFAULTS = {
	'provider': 'codex',          # codex (your local Codex CLI login) | anthropic | openai (any OpenAI-compatible server: OpenAI, Ollama, LM Studio, OpenRouter...) | demo
	'model': 'gpt-5.6-luna',
	'effort': 'low',              # codex and anthropic: low | medium | high | xhigh | max, or '' to omit
	'api_key': '',                # empty: use ANTHROPIC_API_KEY / OPENAI_API_KEY from the environment
	'base_url': '',               # empty: provider default
	'suggestions': 3,
	'send_context': True,         # send OS, shell, cwd and a listing of cwd so suggestions fit your machine
}

# Models that accept server-side refusal fallbacks in the "default" form.
FALLBACK_MODELS = {'claude-fable-5-1', 'claude-opus-5-5', 'claude-opus-5', 'claude-sonnet-5-5'}

OPENAI_DEFAULT_BASE_URL = 'http://localhost:11434/v1'  # Ollama

SYSTEM_PROMPT = """You are shellglot, a shell expert that suggests commands for a terminal user.

Reply with ONLY newline-delimited JSON: exactly {n} lines, one JSON object per line, best suggestion first. No prose, no code fences, no blank lines.

Each object has this shape:
{{"command": "<the full command>", "summary": "<what it does, max 70 chars>", "danger": <true|false>, "requires": [{{"program": "<executable name>", "install": "<command that installs it on the user's OS>"}}], "parts": [{{"text": "<piece of the command>", "explain": "<what this piece does here, max 80 chars>"}}]}}

Rules for "parts":
- Split the command into meaningful pieces, in left-to-right order, covering the whole command.
- Each "text" must be an exact substring of "command".
- Use small pieces: the program name is its own piece, each path or argument is its own piece, and each flag is its own piece together with its value (e.g. "-name '*.log'", "--depth 1"). Never lump several flags into one piece.
- Pipes, redirects and operators are their own pieces ("|", "&&", "2>/dev/null", "> out.txt").
- Explanations are specific to this usage, not generic man-page text.

Rules for "requires":
- List every program the command runs that is an external dependency: not part of a default install of the user's OS (e.g. fd, rg, jq, tree, htop, ffmpeg, pandoc on most Linux distros; brew-only tools on macOS). Shell builtins, coreutils, find, grep, sed, awk, tar, gzip, ps, etc. are standard and are not listed.
- "program" is the executable name exactly as it appears in the command; "install" uses the user's package manager and the right package name (e.g. "sudo apt install fd-find").
- Use [] when the command only uses standard tools.

The first suggestion is the simplest, most common command a seasoned user would type (often a single short command with few or no flags; e.g. "order the files by name" -> "ls"). Do not over-engineer: no pipelines or extra flags the task doesn't ask for. The other suggestions are genuinely different useful variants (another tool, or a common refinement). Prefer tools available on the user's OS (standard tools come first unless the task needs something else), and set "danger" to true when the command deletes or overwrites data, changes system state, or needs sudo."""


class ShellglotError(Exception):
	pass


# ---------------------------------------------------------------- config

def migrate_config():
	"""Move settings saved under the old bashglot name to the shellglot config directory."""
	if not os.path.exists(CONFIG_DIR) and os.path.isdir(OLD_CONFIG_DIR):
		os.rename(OLD_CONFIG_DIR, CONFIG_DIR)


def load_config():
	config = dict(DEFAULTS)
	try:
		with open(CONFIG_PATH) as f:
			config.update(json.load(f))
	except FileNotFoundError:
		pass
	except json.JSONDecodeError as e:
		raise ShellglotError(f'{CONFIG_PATH} is not valid JSON: {e}')
	return config


def save_config(config):
	os.makedirs(CONFIG_DIR, exist_ok=True)
	fd = os.open(CONFIG_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
	with os.fdopen(fd, 'w') as f:
		json.dump(config, f, indent=2)
		f.write('\n')


def ask(label, current):
	answer = input(f'  {label} [{current}]: ').strip()
	return answer or current


DEFAULT_MODELS = {'codex': 'gpt-5.6-luna', 'anthropic': 'claude-opus-5-5', 'openai': 'llama3.2', 'demo': 'demo'}


def detect_provider():
	"""Pick a sensible provider from what's on this machine: Codex CLI, then an Anthropic key, then a local Ollama."""
	if shutil.which('codex'):
		return 'codex'
	if os.environ.get('ANTHROPIC_API_KEY'):
		return 'anthropic'
	if os.environ.get('OPENAI_API_KEY') or shutil.which('ollama'):
		return 'openai'
	return 'codex'


def configure(provider_default=None):
	config = load_config()
	if provider_default and provider_default != config['provider']:
		config['provider'] = provider_default
		config['model'] = DEFAULT_MODELS[provider_default]
	print(c('1', 'shellglot setup') + c('2', f'  (saved to {CONFIG_PATH}, Enter keeps the current value)'))
	provider = ask('Provider: codex (local Codex CLI login), anthropic, openai (any OpenAI-compatible server, e.g. Ollama), demo', config['provider'])
	if provider not in PROVIDERS:
		raise ShellglotError(f'unknown provider "{provider}"')
	if provider != config['provider']:
		config['model'] = DEFAULT_MODELS[provider]
		config['base_url'] = ''
	config['provider'] = provider
	if provider != 'demo':
		config['model'] = ask('Model', config['model'])
		if provider in ('codex', 'anthropic'):
			config['effort'] = ask('Effort (low is fastest; "-" to omit)', config['effort'] or '-').replace('-', '')
		if provider == 'openai':
			config['base_url'] = ask('Base URL', config['base_url'] or OPENAI_DEFAULT_BASE_URL)
		if provider != 'codex':
			env_name = 'ANTHROPIC_API_KEY' if provider == 'anthropic' else 'OPENAI_API_KEY'
			key = getpass.getpass(f'  API key (leave empty to use ${env_name}; input hidden): ').strip()
			if key:
				config['api_key'] = key
	config['suggestions'] = int(ask('Suggestions per prompt', config['suggestions']))
	config['send_context'] = ask('Send OS, cwd and a cwd listing as context? (y/n)', 'y' if config['send_context'] else 'n').lower().startswith('y')
	save_config(config)
	print(c('32', '  saved.'))


# ---------------------------------------------------------------- context

def os_name():
	try:
		with open('/etc/os-release') as f:
			for line in f:
				if line.startswith('PRETTY_NAME='):
					return line.split('=', 1)[1].strip().strip('"')
	except OSError:
		pass
	if platform.system() == 'Darwin':
		return f'macOS {platform.mac_ver()[0]}'
	return f'{platform.system()} {platform.release()}'


def build_context():
	cwd = os.getcwd()
	try:
		entries = sorted(os.listdir(cwd))
	except OSError:
		entries = []
	listing = ', '.join(e + ('/' if os.path.isdir(os.path.join(cwd, e)) else '') for e in entries[:40])
	if len(entries) > 40:
		listing += f', ... ({len(entries) - 40} more)'
	shell = os.environ.get('SHELLGLOT_SHELL') or os.path.basename(os.environ.get('SHELL', 'sh'))
	return f'OS: {os_name()}\nShell: {shell}\nWorking directory: {cwd}\nFiles here: {listing or "(empty)"}'


# ---------------------------------------------------------------- providers

def stream_anthropic(config, system, user):
	try:
		import anthropic
	except ImportError:
		raise ShellglotError('the anthropic package is missing; run ./install.sh or `pip install anthropic`')
	client_options = {}
	if config['api_key']:
		client_options['api_key'] = config['api_key']
	if config['base_url']:
		client_options['base_url'] = config['base_url']
	client = anthropic.Anthropic(**client_options)
	extra_body = {}
	extra_headers = {}
	if config['effort']:
		extra_body['output_config'] = {'effort': config['effort']}
	if config['model'] in FALLBACK_MODELS:
		# On a safety decline, let the API re-run the request on its recommended fallback model.
		extra_headers['anthropic-beta'] = 'server-side-fallback-2026-07-01'
		extra_body['fallbacks'] = 'default'
	try:
		with client.messages.stream(
			model=config['model'],
			max_tokens=8000,
			system=system,
			messages=[{'role': 'user', 'content': user}],
			extra_body=extra_body or None,
			extra_headers=extra_headers or None,
		) as stream:
			yield from stream.text_stream
			final = stream.get_final_message()
	except anthropic.AuthenticationError:
		raise ShellglotError('authentication failed: set ANTHROPIC_API_KEY or run `shellglot config`')
	except anthropic.NotFoundError:
		raise ShellglotError(f'model "{config["model"]}" not found; run `shellglot config`')
	except anthropic.RateLimitError:
		raise ShellglotError('rate limited; try again in a moment')
	except anthropic.APIStatusError as e:
		raise ShellglotError(f'API error {e.status_code}: {e.message}')
	except anthropic.APIConnectionError:
		raise ShellglotError('could not reach the Anthropic API; check your connection')
	if final.stop_reason == 'refusal':
		raise ShellglotError('the model declined this request')


def stream_openai(config, system, user):
	base_url = (config['base_url'] or OPENAI_DEFAULT_BASE_URL).rstrip('/')
	api_key = config['api_key'] or os.environ.get('OPENAI_API_KEY', '')
	body = json.dumps({
		'model': config['model'],
		'stream': True,
		'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
	}).encode()
	headers = {'Content-Type': 'application/json'}
	if api_key:
		headers['Authorization'] = f'Bearer {api_key}'
	request = urllib.request.Request(f'{base_url}/chat/completions', data=body, headers=headers)
	try:
		response = urllib.request.urlopen(request, timeout=120)
	except urllib.error.HTTPError as e:
		raise ShellglotError(f'API error {e.code}: {e.read().decode(errors="replace")[:300]}')
	except urllib.error.URLError as e:
		raise ShellglotError(f'could not reach {base_url}: {e.reason}')
	with response:
		for raw in response:
			line = raw.decode(errors='replace').strip()
			if not line.startswith('data:'):
				continue
			data = line[5:].strip()
			if data == '[DONE]':
				break
			try:
				choices = json.loads(data).get('choices') or [{}]
			except json.JSONDecodeError:
				continue
			text = (choices[0].get('delta') or {}).get('content')
			if text:
				yield text


DEMO_SUGGESTIONS = [
	{'command': "find . -name '*.log' -mtime +7 -delete", 'summary': 'Delete .log files older than 7 days', 'danger': True, 'parts': [
		{'text': 'find', 'explain': 'walk the directory tree looking for matches'},
		{'text': '.', 'explain': 'start from the current directory'},
		{'text': "-name '*.log'", 'explain': 'only files whose name ends in .log'},
		{'text': '-mtime +7', 'explain': 'last modified more than 7 days ago'},
		{'text': '-delete', 'explain': 'remove every match (no confirmation!)'}], 'requires': []},
	{'command': "find . -name '*.log' -mtime +7 -print", 'summary': 'Preview which .log files would be deleted', 'danger': False, 'parts': [
		{'text': 'find .', 'explain': 'search from the current directory down'},
		{'text': "-name '*.log'", 'explain': 'match names ending in .log'},
		{'text': '-mtime +7', 'explain': 'older than 7 days'},
		{'text': '-print', 'explain': 'list the matches instead of deleting them'}], 'requires': []},
	{'command': "fd -e log --changed-before 7d -x rm", 'summary': 'Same with fd', 'danger': True, 'parts': [
		{'text': 'fd', 'explain': 'fast, friendly alternative to find'},
		{'text': '-e log', 'explain': 'files with the .log extension'},
		{'text': '--changed-before 7d', 'explain': 'modified more than 7 days ago'},
		{'text': '-x rm', 'explain': 'run rm on each result'}],
		'requires': [{'program': 'fd', 'install': 'sudo apt install fd-find'}]},
]


def stream_demo(config, system, user):
	text = '\n'.join(json.dumps(s) for s in DEMO_SUGGESTIONS[:config['suggestions']]) + '\n'
	time.sleep(0.6)
	for i in range(0, len(text), 12):
		time.sleep(0.01)
		yield text[i:i + 12]


def stream_codex(config, system, user):
	"""Run the local Codex CLI non-interactively, so requests use its ChatGPT login.

	Codex reports each agent message only once it is complete, so all suggestions arrive together.
	"""
	codex = shutil.which('codex')
	if not codex:
		raise ShellglotError('the codex CLI is not on PATH; install it or pick another provider with `shellglot config`')
	command = [
		codex, 'exec', '--json', '--ephemeral', '--skip-git-repo-check',
		'--ignore-user-config', '--ignore-rules', '--sandbox', 'read-only',
		# Run from an empty directory so Codex doesn't load AGENTS.md or repo context; shellglot sends its own.
		'--cd', tempfile.gettempdir(),
		'--model', config['model'],
	]
	if config['effort']:
		command += ['-c', f'model_reasoning_effort="{config["effort"]}"']
	command.append('-')
	prompt = f'{system}\n\nDo not run any tools or commands; answer directly.\n\n{user}'
	stderr = tempfile.TemporaryFile(mode='w+')
	process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, text=True)
	try:
		process.stdin.write(prompt)
		process.stdin.close()
		error = None
		for line in process.stdout:
			try:
				event = json.loads(line)
			except json.JSONDecodeError:
				continue
			item = event.get('item') or {}
			if event.get('type') == 'item.completed' and item.get('type') == 'agent_message':
				yield item.get('text', '') + '\n'
			elif event.get('type') in ('error', 'turn.failed'):
				error = event.get('message') or (event.get('error') or {}).get('message') or 'codex failed'
		process.wait()
		if error:
			raise ShellglotError(f'codex: {error}')
		if process.returncode:
			stderr.seek(0)
			tail = stderr.read().strip().splitlines()
			raise ShellglotError(f'codex: {tail[-1] if tail else f"exited with code {process.returncode}"}')
	finally:
		if process.poll() is None:
			process.kill()
		stderr.close()


PROVIDERS = {'codex': stream_codex, 'anthropic': stream_anthropic, 'openai': stream_openai, 'demo': stream_demo}


def iter_suggestions(chunks):
	"""Turn a stream of text chunks into suggestion dicts, yielding each as soon as its line is complete."""
	buffer = ''
	for chunk in chunks:
		buffer += chunk
		while '\n' in buffer:
			line, buffer = buffer.split('\n', 1)
			suggestion = parse_line(line)
			if suggestion:
				yield suggestion
	suggestion = parse_line(buffer)
	if suggestion:
		yield suggestion


def parse_line(line):
	line = line.strip()
	if not line.startswith('{'):
		return None
	try:
		suggestion = json.loads(line)
	except json.JSONDecodeError:
		return None
	if not isinstance(suggestion, dict) or not isinstance(suggestion.get('command'), str) or not suggestion['command'].strip():
		return None
	suggestion['requires'] = parse_requires(suggestion.get('requires'))
	return suggestion


def parse_requires(requires):
	"""Normalize the model's list of external dependencies to [{'program', 'install', 'installed'}]."""
	result = []
	for item in requires if isinstance(requires, list) else []:
		if isinstance(item, str):
			item = {'program': item}
		if not isinstance(item, dict) or not isinstance(item.get('program'), str) or not item['program'].strip():
			continue
		program = item['program'].strip()
		if any(r['program'] == program for r in result):
			continue
		install = item.get('install')
		result.append({
			'program': program,
			'install': install.strip() if isinstance(install, str) else '',
			'installed': shutil.which(program) is not None,
		})
	return result


# ---------------------------------------------------------------- rendering

COLOR = sys.stderr.isatty() and not os.environ.get('NO_COLOR')
PART_COLORS = ['33', '36', '35', '32', '34', '91', '93', '96', '95', '92']
INDENT = '     '


def c(code, text):
	return f'\x1b[{code}m{text}\x1b[0m' if COLOR else text


def paint(chars, owners):
	"""Color each run of characters by the part that owns it."""
	out = []
	for owner, run in itertools.groupby(zip(chars, owners), key=lambda pair: pair[1]):
		text = ''.join(ch for ch, _ in run)
		out.append(text if owner is None else c(PART_COLORS[owner % len(PART_COLORS)], text))
	return ''.join(out)


def locate_parts(command, parts):
	"""Find where each part sits in the command, in order. Parts that can't be found get None."""
	spans = []
	cursor = 0
	for part in parts:
		text = str(part.get('text', '')).strip()
		start = command.find(text, cursor) if text else -1
		if start < 0:
			spans.append(None)
			continue
		spans.append((start, start + len(text)))
		cursor = start + len(text)
	return spans


def render(number, suggestion, columns):
	command = suggestion['command']
	parts = [p for p in suggestion.get('parts') or [] if isinstance(p, dict)][:26]
	spans = locate_parts(command, parts)
	lines = []

	header = f' {c("1;97", f"[{number}]")} {c("1", suggestion.get("summary", ""))}'
	if suggestion.get('danger'):
		header += '  ' + c('1;31', '⚠ destructive')
	requires = suggestion.get('requires') or []
	if requires:
		missing = [r for r in requires if not r['installed']]
		names = ', '.join(r['program'] for r in requires)
		if missing:
			header += '  ' + c('1;33', f'⬡ needs {names} (not installed)' if len(missing) == len(requires)
				else f'⬡ needs {names} ({", ".join(r["program"] for r in missing)} not installed)')
		else:
			header += '  ' + c('2', f'⬡ needs {names} (installed)')
	lines.append(header)

	owners = [None] * len(command)
	for i, span in enumerate(spans):
		if span:
			for x in range(*span):
				owners[x] = i

	# Key notation: a letter over each part, with a bracket spanning the part's characters.
	if any(spans) and len(INDENT) + len(command) <= columns:
		keys = [' '] * len(command)
		brackets = [' '] * len(command)
		for i, span in enumerate(spans):
			if not span:
				continue
			start, end = span
			middle = start + (end - start - 1) // 2
			for x in range(start, end):
				brackets[x] = '─'
			if end - start >= 3:
				brackets[start] = '╭'
				brackets[end - 1] = '╮'
			brackets[middle] = '┴'
			keys[middle] = chr(ord('a') + i)
		end = max(span[1] for span in spans if span)
		lines.append(INDENT + paint(keys[:end], owners))
		lines.append(INDENT + paint(brackets[:end], owners))
	lines.append(INDENT + c('1', paint(list(command), owners)))

	# Legend: one line per key.
	width = min(max((len(str(p.get('text', '')).strip()) for p in parts), default=0), 28)
	for i, part in enumerate(parts):
		text = str(part.get('text', '')).strip()
		shown = text if len(text) <= width else text[:width - 1] + '…'
		color = PART_COLORS[i % len(PART_COLORS)]
		key = chr(ord('a') + i) if spans[i] else '·'
		lines.append(f'{INDENT}{c("1;" + color, key)}  {c(color, shown.ljust(width))}  {c("2", str(part.get("explain", "")))}')

	for r in requires:
		if not r['installed']:
			how = f'install with: {c("1", r["install"])}' if r['install'] else 'install it first'
			lines.append(f'{INDENT}{c("33", "⬡")}  {c("33", r["program"])} is an external dependency and is not installed; {how}')
	return '\n'.join(lines)


class Spinner:
	def __init__(self, label):
		self.label = label
		self.lock = threading.Lock()
		self.stopped = threading.Event()
		self.thread = threading.Thread(target=self.run, daemon=True)
		self.enabled = sys.stderr.isatty()

	def run(self):
		for frame in itertools.cycle('⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'):
			if self.stopped.wait(0.08):
				break
			with self.lock:
				sys.stderr.write(f'\r {c("36", frame)} {c("2", self.label)}\x1b[K')
				sys.stderr.flush()

	def __enter__(self):
		if self.enabled:
			self.thread.start()
		return self

	def print(self, text):
		with self.lock:
			sys.stderr.write('\r\x1b[K' + text + '\n')
			sys.stderr.flush()

	def __exit__(self, *exc):
		self.stopped.set()
		if self.enabled:
			self.thread.join()
			sys.stderr.write('\r\x1b[K')
			sys.stderr.flush()


def read_key():
	"""Read one keypress from the terminal without waiting for Enter."""
	try:
		import termios
		import tty
	except ImportError:
		return sys.stdin.readline()[:1]
	fd = sys.stdin.fileno()
	old = termios.tcgetattr(fd)
	try:
		tty.setraw(fd)
		return os.read(fd, 1).decode(errors='replace')
	finally:
		termios.tcsetattr(fd, termios.TCSADRAIN, old)


def first_run_setup():
	"""Offer to pick an LLM provider the first time shellglot runs; save either way so we only ask once."""
	detected = detect_provider()
	print(c('1', 'Welcome to shellglot!') + ' No LLM provider is configured yet.')
	if input('  Set one up now? [Y/n]: ').strip().lower().startswith('n'):
		config = load_config()
		config['provider'] = detected
		config['model'] = DEFAULT_MODELS[detected]
		save_config(config)
		print(c('2', f'  using {detected} / {config["model"]}; change it any time with `shellglot config`'))
	else:
		configure(detected)
	print()


def suggest(prompt, out_path):
	if not os.path.exists(CONFIG_PATH) and sys.stdin.isatty():
		first_run_setup()
	config = load_config()
	provider = PROVIDERS.get(config['provider'])
	if not provider:
		raise ShellglotError(f'unknown provider "{config["provider"]}"; run `shellglot config`')
	count = max(1, min(int(config['suggestions']), 9))
	user = f'Task: {prompt}'
	if config['send_context']:
		user = f'{build_context()}\n\n{user}'
	columns = shutil.get_terminal_size((100, 24)).columns

	suggestions = []
	with Spinner(f'asking {config["model"]}…') as spinner:
		for suggestion in iter_suggestions(provider(config, SYSTEM_PROMPT.format(n=count), user)):
			if len(suggestions) == count:
				break
			suggestions.append(suggestion)
			spinner.print(('' if len(suggestions) == 1 else '\n') + render(len(suggestions), suggestion, columns))
	if not suggestions:
		raise ShellglotError('the model returned no usable suggestions; try rephrasing')

	if not (out_path and sys.stdin.isatty()):
		return
	choices = '1' if len(suggestions) == 1 else f'1-{len(suggestions)}'
	sys.stderr.write(f'\n {c("2", f"press {choices} to edit and run · Enter for 1 · any other key to cancel")} ')
	sys.stderr.flush()
	key = read_key()
	if key in ('\r', '\n'):
		key = '1'
	if key.isdigit() and 1 <= int(key) <= len(suggestions):
		sys.stderr.write(f'\r\x1b[K {c("2", f"using [{key}]")}\n')
		with open(out_path, 'w') as f:
			f.write(suggestions[int(key) - 1]['command'])
	else:
		sys.stderr.write(f'\r\x1b[K {c("2", "cancelled")}\n')


def main():
	parser = argparse.ArgumentParser(prog='shellglot', description=__doc__)
	sub = parser.add_subparsers(dest='action', required=True)
	suggest_parser = sub.add_parser('suggest', help='suggest commands for a prompt')
	suggest_parser.add_argument('--out', help='file to write the chosen command to')
	suggest_parser.add_argument('prompt', nargs='+')
	sub.add_parser('config', help='set the provider, model and key')
	args = parser.parse_args()
	try:
		migrate_config()
		if args.action == 'config':
			configure()
		else:
			suggest(' '.join(args.prompt), args.out)
	except ShellglotError as e:
		sys.stderr.write(f'\r\x1b[K {c("1;31", "shellglot:")} {e}\n')
		sys.exit(1)
	except KeyboardInterrupt:
		sys.stderr.write('\r\x1b[K')
		sys.exit(130)


if __name__ == '__main__':
	main()
