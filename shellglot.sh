# shellglot shell integration for bash and zsh.
# Load it from ~/.bashrc or ~/.zshrc. Installed with apt or brew:
#   eval "$(shellglot init bash)"     # or zsh
# From a checkout (install.sh does this for you):
#   export SHELLGLOT_HOME=/path/to/shellglot
#   source "$SHELLGLOT_HOME/shellglot.sh"

if [ -z "$SHELLGLOT_HOME" ]; then
	if [ -n "$BASH_VERSION" ]; then
		SHELLGLOT_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	elif [ -n "$ZSH_VERSION" ]; then
		eval 'SHELLGLOT_HOME="${${(%):-%x}:A:h}"'
	fi
fi

_shellglot_py() {
	local script="$SHELLGLOT_HOME/shellglot.py"
	if [ -x "$SHELLGLOT_HOME/.venv/bin/python" ]; then
		"$SHELLGLOT_HOME/.venv/bin/python" "$script" "$@"
	elif [ -x "$script" ]; then
		# Packaged installs point the script's shebang at the right Python.
		"$script" "$@"
	else
		python3 "$script" "$@"
	fi
}

# Ask for suggestions, then put the chosen command on an editable line.
_shellglot_suggest() {
	local out rc cmd line
	out="$(mktemp "${TMPDIR:-/tmp}/shellglot.XXXXXX")" || return 1
	SHELLGLOT_SHELL="${ZSH_VERSION:+zsh}${BASH_VERSION:+bash}" _shellglot_py suggest --out "$out" -- "$*"
	rc=$?
	cmd="$(cat "$out")"
	rm -f "$out"
	[ $rc -eq 0 ] || return $rc
	[ -n "$cmd" ] || return 0
	if [ -n "$ZSH_VERSION" ]; then
		# zsh: drop the command into the next prompt's buffer, ready to edit or run.
		print -z -- "$cmd"
	else
		# bash: prefill an editable line; Enter runs it, Ctrl-C cancels.
		read -r -e -i "$cmd" -p $'\001\e[1;32m\002❯\001\e[0m\002 ' line || { echo; return 130; }
		[ -n "$line" ] || return 0
		history -s -- "$line"
		eval -- "$line"
	fi
}

# `sglot` in shellglot mode.
_shellglot_sglot() {
	[ -n "$BASH_VERSION" ] && set +f
	if [ $# -eq 0 ]; then
		echo 'usage: sglot <what you want to do>'
		return 2
	fi
	_shellglot_suggest "$@"
}

_shellglot_on() {
	[ -n "$SHELLGLOT_MODE" ] && { echo 'shellglot mode is already on'; return 0; }
	SHELLGLOT_MODE=1
	_SHELLGLOT_OLD_PS1="$PS1"
	PS1="(sglot) $PS1"
	# Turn globbing off while the prompt is parsed, so `sglot find *.log files` reaches the model as typed.
	if [ -n "$ZSH_VERSION" ]; then
		alias sglot='noglob _shellglot_sglot'
	else
		alias sglot='set -f; _shellglot_sglot'
	fi
	echo "shellglot mode on: type $(printf '\e[1m')sglot <what you want to do>$(printf '\e[0m')  ·  shellglot off to leave"
}

_shellglot_off() {
	[ -z "$SHELLGLOT_MODE" ] && return 0
	unset SHELLGLOT_MODE
	PS1="$_SHELLGLOT_OLD_PS1"
	unset _SHELLGLOT_OLD_PS1
	unalias sglot 2>/dev/null
	echo 'shellglot mode off'
}

shellglot() {
	case "$1" in
		on) _shellglot_on ;;
		off) _shellglot_off ;;
		config | setup) _shellglot_py config ;;
		status) [ -n "$SHELLGLOT_MODE" ] && echo 'shellglot mode: on' || echo 'shellglot mode: off' ;;
		'' | -h | --help | help)
			cat <<-'EOF'
				usage: shellglot on            enter shellglot mode (then: sglot <prompt>)
				       shellglot off           leave shellglot mode
				       shellglot config        choose provider, model and API key
				       shellglot <prompt>      one-off suggestion without entering the mode
			EOF
			;;
		*) _shellglot_suggest "$@" ;;
	esac
}

[ "$SHELLGLOT_AUTO_ON" = 1 ] && _shellglot_on >/dev/null
