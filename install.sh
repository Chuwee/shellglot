#!/usr/bin/env bash
# Install bashglot: a private virtualenv with the Anthropic SDK, plus the shell hook in your rc file.
# Usage: ./install.sh [--no-rc]
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo '› creating virtualenv'
if python3 -m venv "$here/.venv" 2>/dev/null; then
	"$here/.venv/bin/pip" install --quiet --upgrade anthropic
else
	# No ensurepip (Debian/Ubuntu without python3-venv): make a pip-less venv and fill it with the system pip.
	rm -rf "$here/.venv"
	python3 -m venv --without-pip "$here/.venv"
	python3 -m pip --python "$here/.venv/bin/python" install --quiet --upgrade anthropic
fi

if [ "${1:-}" != '--no-rc' ]; then
	case "$(basename "${SHELL:-bash}")" in
		zsh) rc="$HOME/.zshrc" ;;
		*) rc="$HOME/.bashrc" ;;
	esac
	if ! grep -q 'bashglot.sh' "$rc" 2>/dev/null; then
		printf '\n# bashglot\nexport BASHGLOT_HOME=%q\nsource "$BASHGLOT_HOME/bashglot.sh"\n' "$here" >>"$rc"
		echo "› added the shell hook to $rc"
	fi
fi

echo
echo 'done. open a new terminal (or source your rc file), then:'
echo '  bashglot config     # optional: pick provider/model (it also asks on first use)'
echo '  bashglot on'
echo '  bglot find files bigger than 100MB'
