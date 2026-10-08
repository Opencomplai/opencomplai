#!/usr/bin/env bash
#
# install.sh — Install the opencomplai CLI with uv and a uv-managed Python.
#
# Wraps `uv tool install`, so no Python has to be installed beforehand. The
# interpreter is requested from uv (default 3.11, the minimum the packages
# support). Only PyPI packages are downloaded; nothing is sent anywhere.
#
# Usage:
#   bash install.sh [--install-uv] [--python <version>] [--help]
#
#   --install-uv       if uv is missing, run the official uv installer
#                      (https://astral.sh/uv/install.sh) first
#   --python <version> interpreter to request (default: $OPENCOMPLAI_PYTHON or 3.11)
#
# Environment:
#   OPENCOMPLAI_PYTHON      default for --python
#   OPENCOMPLAI_SPEC        package to install (default: opencomplai)
#   OPENCOMPLAI_FIND_LINKS  directory of local wheels to prefer (used by CI)
#
# The script does not edit shell rc files or PATH. Works on macOS, Linux and
# Git Bash on Windows.

set -euo pipefail

PY="${OPENCOMPLAI_PYTHON:-3.11}"
INSTALL_UV=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --install-uv) INSTALL_UV=1 ;;
    --python)
      if [ "$#" -lt 2 ]; then
        echo "install.sh: --python needs a version" >&2
        exit 2
      fi
      PY="$2"
      shift
      ;;
    --help | -h)
      sed -n '2,23p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "install.sh: unknown option: $1 (try --help)" >&2
      exit 2
      ;;
  esac
  shift
done

if ! command -v uv >/dev/null 2>&1; then
  if [ "$INSTALL_UV" -eq 1 ]; then
    echo "Installing uv with the official installer (https://astral.sh/uv/install.sh)..."
    UV_INSTALLER="$(mktemp)"
    curl -LsSf -o "$UV_INSTALLER" https://astral.sh/uv/install.sh
    UV_NO_MODIFY_PATH=1 sh "$UV_INSTALLER"
    rm -f "$UV_INSTALLER"
    export PATH="$HOME/.local/bin:$PATH"
  else
    echo "install.sh: uv is not installed." >&2
    echo "Install it first: https://docs.astral.sh/uv/getting-started/installation/" >&2
    echo "or re-run this script with --install-uv to run the official uv installer." >&2
    exit 1
  fi
fi

ARGS=(--python "$PY" --force)
if [ -n "${OPENCOMPLAI_FIND_LINKS:-}" ]; then
  ARGS+=(--find-links "$OPENCOMPLAI_FIND_LINKS")
fi
uv tool install "${ARGS[@]}" "${OPENCOMPLAI_SPEC:-opencomplai}"

BIN="$(uv tool dir --bin)"
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "Add $BIN to your PATH to run opencomplai from any shell." ;;
esac

EXE="$BIN/opencomplai"
[ -x "$EXE" ] || EXE="$BIN/opencomplai.exe" # Windows layout
"$EXE" --version
