# bashglot shell integration for bash and zsh.
# Source it from ~/.bashrc or ~/.zshrc (install.sh does this for you):
#   export BASHGLOT_HOME=/path/to/bashglot
#   source "$BASHGLOT_HOME/bashglot.sh"

if [ -z "$BASHGLOT_HOME" ] && [ -n "$BASH_VERSION" ]; then
	BASHGLOT_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

_bashglot_py() {
	local py="$BASHGLOT_HOME/.venv/bin/python"
	[ -x "$py" ] || py=python3
	"$py" "$BASHGLOT_HOME/bashglot.py" "$@"
}

# Ask for suggestions, then put the chosen command on an editable line.
_bashglot_suggest() {
	local out rc cmd line
	out="$(mktemp "${TMPDIR:-/tmp}/bashglot.XXXXXX")" || return 1
	BASHGLOT_SHELL="${ZSH_VERSION:+zsh}${BASH_VERSION:+bash}" _bashglot_py suggest --out "$out" -- "$*"
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

# `bglot` in bashglot mode.
_bashglot_bglot() {
	[ -n "$BASH_VERSION" ] && set +f
	if [ $# -eq 0 ]; then
		echo 'usage: bglot <what you want to do>'
		return 2
	fi
	_bashglot_suggest "$@"
}

_bashglot_on() {
	[ -n "$BASHGLOT_MODE" ] && { echo 'bashglot mode is already on'; return 0; }
	BASHGLOT_MODE=1
	_BASHGLOT_OLD_PS1="$PS1"
	PS1="(bglot) $PS1"
	# Turn globbing off while the prompt is parsed, so `bglot find *.log files` reaches the model as typed.
	if [ -n "$ZSH_VERSION" ]; then
		alias bglot='noglob _bashglot_bglot'
	else
		alias bglot='set -f; _bashglot_bglot'
	fi
	echo "bashglot mode on: type $(printf '\e[1m')bglot <what you want to do>$(printf '\e[0m')  ·  bashglot off to leave"
}

_bashglot_off() {
	[ -z "$BASHGLOT_MODE" ] && return 0
	unset BASHGLOT_MODE
	PS1="$_BASHGLOT_OLD_PS1"
	unset _BASHGLOT_OLD_PS1
	unalias bglot 2>/dev/null
	echo 'bashglot mode off'
}

bashglot() {
	case "$1" in
		on) _bashglot_on ;;
		off) _bashglot_off ;;
		config | setup) _bashglot_py config ;;
		status) [ -n "$BASHGLOT_MODE" ] && echo 'bashglot mode: on' || echo 'bashglot mode: off' ;;
		'' | -h | --help | help)
			cat <<-'EOF'
				usage: bashglot on            enter bashglot mode (then: bglot <prompt>)
				       bashglot off           leave bashglot mode
				       bashglot config        choose provider, model and API key
				       bashglot <prompt>      one-off suggestion without entering the mode
			EOF
			;;
		*) _bashglot_suggest "$@" ;;
	esac
}

[ "$BASHGLOT_AUTO_ON" = 1 ] && _bashglot_on >/dev/null
