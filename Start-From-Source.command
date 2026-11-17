#!/bin/zsh
set -eu
cd -- "${0:A:h}"
# A downloaded release app needs none of these setup steps.
for candidate in python3.12 python3.11 python3.10; do
  if command -v "$candidate" >/dev/null; then PYTHON_BIN="$(command -v "$candidate")"; break; fi
done
if [[ -z "${PYTHON_BIN:-}" ]]; then
  print 'Install Python 3.12 from https://www.python.org/downloads/macos/ then run this launcher again.'
  read '?Press Enter to close'; exit 1
fi
if [[ ! -x .venv/bin/python ]]; then "$PYTHON_BIN" -m venv .venv; fi
if [[ ! -f .venv/.ready ]]; then
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/.ready
fi
exec .venv/bin/python app.py
