#!/usr/bin/env bash
# Launch a headless CARLA RPC server from the UNCOOKED editor project — no
# `make package` cook required. Used to verify a freshly-authored vehicle end to
# end (spawn + drive over the RPC API).
#
# WHY -nullrhi (not -RenderOffScreen): uncooked meshes have null distance-field /
# GPU-scene data (built only during the cook), so a real renderer SIGSEGVs the
# render thread (FDistanceFieldVolumeTexture::IsValidDistanceFieldVolume). -nullrhi
# removes the render thread entirely; RPC + physics + traffic manager still run.
# Trade-off: NO camera/lidar images. For sensors, cook and use -RenderOffScreen.
# See build-carla-ue4-linux/LESSONS.md L17 and ../LESSONS.md V11.
#
# Usage:
#   bash run_server.sh [MAP] [RPC_PORT]
#   MAP default: /Game/Carla/Maps/Town02  (light map = fast first load)
#   RPC_PORT default: 2000
#
#   WINDOW=1 bash run_server.sh   -> visible window on $DISPLAY, REAL rendering
#                                    (default is headless -nullrhi, no window)
#   RESX / RESY                   -> window size (default 1280x720)
#
# Runs in the FOREGROUND (blocks). Background it from the caller if needed:
#   bash run_server.sh >server.log 2>&1 &
# Stop with:  pkill -x UE4Editor     (NOT `pkill -f CarlaUE4.uproject` — that also
#                                      matches and kills the launching shell)
#
# WINDOWED on UNCOOKED content: the real renderer SIGSEGVs on null mesh distance
# fields (build L17), so windowed mode passes an -ini: override disabling their
# generation (r.GenerateMeshDistanceFields=False). Verified: Town02 window on
# DISPLAY=:1, vehicle.ford.testcar spawned + drove. (No DF shadows/AO; for full
# rendering fidelity, cook.) Headless -nullrhi mode needs no such override.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${HERE}/../../build-carla-ue4-linux/env.sh"

MAP="${1:-/Game/Carla/Maps/Town02}"
RPC_PORT="${2:-2000}"
STREAM_PORT="$((RPC_PORT + 1))"

UE4_EDITOR="${UE4_ROOT}/Engine/Binaries/Linux/UE4Editor"
UPROJECT="${CARLA_UE4_ROOT}/Unreal/CarlaUE4/CarlaUE4.uproject"

[ -x "${UE4_EDITOR}" ] || { echo "[server] ERROR: UE4Editor not built (build skill step 03)."; exit 1; }
[ -f "${UPROJECT}" ]   || { echo "[server] ERROR: CarlaUE4.uproject missing: ${UPROJECT}"; exit 1; }

export DISPLAY="${DISPLAY:-:1}"
cd "${CARLA_UE4_ROOT}/Unreal/CarlaUE4"

if [ "${WINDOW:-0}" = "1" ]; then
  echo "[server] map=${MAP} rpc=${RPC_PORT} WINDOWED on ${DISPLAY} (real render, DF off, uncooked)"
  exec "${UE4_EDITOR}" "${UPROJECT}" "${MAP}" \
    -game -windowed -ResX="${RESX:-1280}" -ResY="${RESY:-720}" -nosound \
    "-ini:Engine:[/Script/Engine.RendererSettings]:r.GenerateMeshDistanceFields=False" \
    -carla-rpc-port="${RPC_PORT}" -carla-streaming-port="${STREAM_PORT}"
else
  echo "[server] map=${MAP} rpc=${RPC_PORT} stream=${STREAM_PORT} (-game -nullrhi, headless, uncooked)"
  exec "${UE4_EDITOR}" "${UPROJECT}" "${MAP}" \
    -game -nullrhi -nosound \
    -carla-rpc-port="${RPC_PORT}" -carla-streaming-port="${STREAM_PORT}"
fi
