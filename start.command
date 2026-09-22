#!/bin/zsh
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv || exit 1
  .venv/bin/pip install -r requirements.txt || exit 1
fi
if curl -fsS http://localhost:8765/api/status >/dev/null 2>&1; then
  open http://localhost:8765
  exit 0
fi
.venv/bin/python app.py &
service_pid=$!
trap 'kill "$service_pid" 2>/dev/null' EXIT INT TERM
for attempt in {1..30}; do
  if curl -fsS http://localhost:8765/api/status >/dev/null 2>&1; then
    open http://localhost:8765
    break
  fi
  sleep 0.2
done
wait "$service_pid"
