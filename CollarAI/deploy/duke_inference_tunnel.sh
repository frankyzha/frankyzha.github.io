#!/usr/bin/env bash

set -u -o pipefail

readonly LOGIN=yz1075@login.cs.duke.edu
readonly LOCAL_PORT=8000
readonly REMOTE_PORT=18083

tunnel_pid=""
stop_tunnel() {
  if [[ -n "$tunnel_pid" ]]; then
    kill -TERM "$tunnel_pid" 2>/dev/null || true
    wait "$tunnel_pid" 2>/dev/null || true
  fi
}
trap 'stop_tunnel; exit 0' INT TERM

while true; do
  node="$(
    /usr/bin/ssh -o BatchMode=yes -o ConnectTimeout=10 "$LOGIN" \
      "squeue -h --name=collarai-gemma --state=RUNNING -o %N | head -1" 2>/dev/null
  )"
  if [[ ! "$node" =~ ^[A-Za-z0-9.-]+$ ]]; then
    /bin/sleep 10
    continue
  fi

  /usr/bin/ssh \
    -o BatchMode=yes \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=20 \
    -o ServerAliveCountMax=3 \
    -N -L "127.0.0.1:${LOCAL_PORT}:${node}:${REMOTE_PORT}" \
    "$LOGIN" &
  tunnel_pid=$!

  failures=0
  while kill -0 "$tunnel_pid" 2>/dev/null; do
    if /usr/bin/curl -fsS --max-time 3 "http://127.0.0.1:${LOCAL_PORT}/health" \
      >/dev/null 2>&1; then
      failures=0
    else
      failures=$((failures + 1))
      if (( failures >= 12 )); then
        break
      fi
    fi
    /bin/sleep 5
  done

  stop_tunnel
  tunnel_pid=""
  /bin/sleep 5
done
