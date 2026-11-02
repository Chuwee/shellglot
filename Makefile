# Install layout used by the apt and Homebrew packages:
#   $(PREFIX)/share/shellglot/shellglot.py   the program
#   $(PREFIX)/share/shellglot/shellglot.sh   the shell hook (`shglot init` prints a line that sources it)
#   $(PREFIX)/bin/shglot                     the command: a symlink to the program
# PYTHON, when set, replaces the program's `#!/usr/bin/env python3` shebang.

PREFIX ?= /usr/local
DESTDIR ?=
PYTHON ?=

SHARE = $(DESTDIR)$(PREFIX)/share/shellglot
BIN = $(DESTDIR)$(PREFIX)/bin

.PHONY: install uninstall version

install:
	install -d $(SHARE) $(BIN)
	install -m 755 shellglot.py $(SHARE)/shellglot.py
	install -m 644 shellglot.sh $(SHARE)/shellglot.sh
	if [ -n "$(PYTHON)" ]; then sed -i.bak '1s|.*|#!$(PYTHON)|' $(SHARE)/shellglot.py && rm -f $(SHARE)/shellglot.py.bak; fi
	ln -sf ../share/shellglot/shellglot.py $(BIN)/shglot

uninstall:
	rm -f $(BIN)/shglot
	rm -rf $(SHARE)

version:
	@sed -n "s/^__version__ = '\(.*\)'/\1/p" shellglot.py
