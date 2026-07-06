#!/usr/bin/env bash
# Step 07 — end-to-end verification.
#
# Starts the headless packaged server, waits for the RPC port, runs a stock
# example against it from the conda env, then shuts the server down. This is
# the proof the whole toolchain (UE4 + LibCarla + bindings + content) works.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${HERE}/../env.sh"

RPC_PORT="${RPC_PORT:-2000}"

# Prefer the packaged server; fall back to the editor's launch script.
SERVER_SH="$(ls -t "${CARLA_UE4_ROOT}"/Dist/CARLA_*/LinuxNoEditor/CarlaUE4.sh 2>/dev/null | head -1 || true)"
[ -n "${SERVER_SH}" ] || { echo "[verify] ERROR: no packaged server (run step 06 TARGET=package)."; exit 1; }

# `conda activate` is a shell function from conda.sh; source it unconditionally
# (a non-interactive shell hasn't, even though the conda binary is on PATH).
_CONDA_BASE="$(conda info --base 2>/dev/null || echo "${HOME}/anaconda3")"
# shellcheck disable=SC1091
source "${_CONDA_BASE}/etc/profile.d/conda.sh"
conda activate "${CARLA_CONDA_ENV}"

echo "[verify] starting headless server: ${SERVER_SH}"
"${SERVER_SH}" -RenderOffScreen -nosound \
  --carla-rpc-port="${RPC_PORT}" --carla-streaming-port=0 &
SERVER_PID=$!
trap 'echo "[verify] stopping server ${SERVER_PID}"; kill "${SERVER_PID}" 2>/dev/null || true' EXIT

echo "[verify] waiting for RPC port ${RPC_PORT}..."
for i in $(seq 1 60); do
  if (echo > "/dev/tcp/127.0.0.1/${RPC_PORT}") >/dev/null 2>&1; then
    echo "[verify] port up after ${i}s"; break
  fi
  sleep 1
  [ "$i" -eq 60 ] && { echo "[verify] ERROR: server never opened port ${RPC_PORT}"; exit 1; }
done

echo "[verify] running example: generate_traffic.py (10s)..."
cd "${CARLA_UE4_ROOT}/PythonAPI/examples"
timeout 30 python generate_traffic.py --host 127.0.0.1 --port "${RPC_PORT}" -n 10 -w 5 &
EX_PID=$!
sleep 12
kill "${EX_PID}" 2>/dev/null || true

echo "[verify] SUCCESS — server accepted client + example ran."
