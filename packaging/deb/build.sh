#!/usr/bin/env bash
# Build dist/shellglot_<version>_all.deb from this checkout.
# Usage: packaging/deb/build.sh
set -euo pipefail
umask 022

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
version="$(make -s -C "$root" version)"
stage="$(mktemp -d)"
chmod 755 "$stage"
trap 'rm -rf "$stage"' EXIT

make -s -C "$root" install DESTDIR="$stage" PREFIX=/usr PYTHON=/usr/bin/python3
install -d "$stage/usr/share/doc/shellglot" "$stage/DEBIAN"
install -m 644 "$root/LICENSE" "$stage/usr/share/doc/shellglot/copyright"
install -m 644 "$root/README.md" "$stage/usr/share/doc/shellglot/README.md"

cat >"$stage/DEBIAN/control" <<CONTROL
Package: shellglot
Version: $version
Architecture: all
Maintainer: Chuwee <https://github.com/Chuwee/shellglot>
Depends: python3 (>= 3.8)
Recommends: python3-anthropic
Section: utils
Priority: optional
Homepage: https://github.com/Chuwee/shellglot
Installed-Size: $(du -sk "$stage/usr" | cut -f1)
Description: shell command suggestions from plain words, with every part explained
 Ask your terminal for a command in plain words and get a few suggestions,
 each with a letter over every part of the command and a line explaining it.
 Works with the Codex CLI, the Anthropic API or any OpenAI-compatible server.
 .
 Enable it by adding  eval "\$(shellglot init bash)"  to ~/.bashrc
 (or  eval "\$(shellglot init zsh)"  to ~/.zshrc).
CONTROL

mkdir -p "$root/dist"
out="$root/dist/shellglot_${version}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$stage" "$out" >/dev/null
echo "$out"
