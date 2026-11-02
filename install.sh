#!/usr/bin/env bash
# Install shellglot from this checkout: a private virtualenv with a pinned Anthropic SDK,
# and a `shellglot` link in ~/.local/bin. Your shell config is left alone unless you pass --rc.
# Usage: ./install.sh [--rc]
set -euo pipefail

# The SDK version this checkout is tested with. Bump it deliberately, not by reinstalling.
ANTHROPIC_VERSION=2.3.0

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin="$HOME/.local/bin"

echo '› creating virtualenv'
if python3 -m venv "$here/.venv" 2>/dev/null; then
	"$here/.venv/bin/pip" install --quiet "anthropic==$ANTHROPIC_VERSION"
else
	# No ensurepip (Debian/Ubuntu without python3-venv): make a pip-less venv and fill it with the system pip.
	rm -rf "$here/.venv"
	python3 -m venv --without-pip "$here/.venv"
	python3 -m pip --python "$here/.venv/bin/python" install --quiet "anthropic==$ANTHROPIC_VERSION"
fi

# Run through the virtualenv's Python, so the SDK is found.
mkdir -p "$bin"
cat >"$bin/shellglot" <<EOF
#!/bin/sh
exec $(printf '%q' "$here/.venv/bin/python") $(printf '%q' "$here/shellglot.py") "\$@"
EOF
chmod 755 "$bin/shellglot"
echo "› linked $bin/shellglot"
case ":$PATH:" in
	*":$bin:"*) ;;
	*) echo "  note: $bin is not on your PATH; add it, or run $bin/shellglot" ;;
esac

case "$(basename "${SHELL:-bash}")" in
	zsh) shell=zsh rc="$HOME/.zshrc" ;;
	*) shell=bash rc="$HOME/.bashrc" ;;
esac
hook="eval \"\$(shellglot init $shell)\""

if [ "${1:-}" = '--rc' ]; then
	if ! grep -qF "$hook" "$rc" 2>/dev/null; then
		printf '\n# shellglot\n%s\n' "$hook" >>"$rc"
		echo "› added the shell hook to $rc"
	fi
fi

echo
echo 'done. try:'
echo '  shellglot find files bigger than 100MB'
if [ "${1:-}" != '--rc' ]; then
	echo
	echo "optional: to get picks straight onto your prompt and sglot mode, add this to $rc"
	echo "(or rerun with --rc):"
	echo "  $hook"
fi
