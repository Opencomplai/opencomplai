#!/usr/bin/env bash
# smoke_lib.sh - helpers for the smoke scripts. Source it; it has no side effects.
# Every failure prints "SMOKE FAIL step=<name>: <message>" to stderr and exits 1.

smoke_fail() { # NAME MSG
  echo "SMOKE FAIL step=$1: $2" >&2
  exit 1
}

smoke_step() { # NAME CMD...  (CMD must exit 0)
  local name="$1" rc=0
  shift
  "$@" || rc=$?
  [ "$rc" -eq 0 ] || smoke_fail "$name" "'$*' exited $rc"
  echo "SMOKE OK step=$name"
}

smoke_expect() { # NAME CODE CMD...  (CMD must exit exactly CODE)
  local name="$1" want="$2" rc=0
  shift 2
  "$@" || rc=$?
  [ "$rc" -eq "$want" ] || smoke_fail "$name" "'$*' exited $rc, expected $want"
  echo "SMOKE OK step=$name"
}

smoke_assert_eq() { # NAME ACTUAL EXPECTED
  [ "$2" = "$3" ] || smoke_fail "$1" "got '$2', expected '$3'"
  echo "SMOKE OK step=$1"
}
