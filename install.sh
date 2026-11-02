#!/usr/bin/env bash
# Install shellglot from this checkout: a `shgl` link in ~/.local/bin.
# shellglot needs only Python 3.8+; your shell config is left alone unless you pass --rc.
# Usage: ./install.sh [--rc]
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin="$HOME/.local/bin"

mkdir -p "$bin"
ln -sfn "$here/shellglot.py" "$bin/shgl"
echo "› linked $bin/shgl"
case ":$PATH:" in
	*":$bin:"*) ;;
	*) echo "  note: $bin is not on your PATH; add it, or run $bin/shgl" ;;
esac

case "$(basename "${SHELL:-bash}")" in
	zsh) shell=zsh rc="$HOME/.zshrc" ;;
	*) shell=bash rc="$HOME/.bashrc" ;;
esac
hook="eval \"\$(shgl init $shell)\""

if [ "${1:-}" = '--rc' ]; then
	if ! grep -qF "$hook" "$rc" 2>/dev/null; then
		printf '\n# shellglot\n%s\n' "$hook" >>"$rc"
		echo "› added the shell hook to $rc"
	fi
fi

echo
echo 'done. try:'
echo '  shgl find files bigger than 100MB'
if [ "${1:-}" != '--rc' ]; then
	echo
	echo "optional: to get picks straight onto your prompt and sglot mode, add this to $rc"
	echo "(or rerun with --rc):"
	echo "  $hook"
fi
