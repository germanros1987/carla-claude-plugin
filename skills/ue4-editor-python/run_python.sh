#!/usr/bin/env bash
# Run a Python script inside the CarlaUE4 editor, headless (UE4 PythonScriptPlugin).
#
# This is the MCP's "project-direct" entrypoint: execute arbitrary UE editor
# Python against the CarlaUE4 project (asset registry, blueprints, maps, props)
# without a GUI, and capture the result.
#
# Usage:
#   run_python.sh <script.py> [--close-editor] [-- <extra UE args>]
#
# The script runs via:
#   UE4Editor-Cmd <proj> -ExecutePythonScript=<script> ...
#
# IMPORTANT behaviours (see LESSONS.md):
#   * PythonScriptPlugin is NOT enabled in CarlaUE4.uproject -> we pass
#     -EnablePlugins=PythonScriptPlugin.
#   * Do NOT pass -NoShaderCompile: it leaves GShaderCompilingManager null while
#     the editor's Slate notification ticks it -> SIGSEGV. -nullrhi is fine.
#   * A running GUI editor holds the project lock; a headless instance then
#     conflicts. Pass --close-editor to terminate it first.
#   * Have your script also WRITE results to a file; a late engine crash can
#     swallow stdout.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Reuse the build skill's env for UE4_ROOT / CARLA_UE4_ROOT.
source "${HERE}/../build-carla-ue4-linux/env.sh" >/dev/null

CLOSE_EDITOR=false
SCRIPT=""
EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --close-editor) CLOSE_EDITOR=true; shift;;
    --) shift; EXTRA=("$@"); break;;
    *) SCRIPT="$1"; shift;;
  esac
done
[ -n "${SCRIPT}" ] || { echo "usage: run_python.sh <script.py> [--close-editor] [-- <extra UE args>]"; exit 2; }
[ -f "${SCRIPT}" ] || { echo "[uepy] script not found: ${SCRIPT}"; exit 2; }
SCRIPT="$(cd "$(dirname "${SCRIPT}")" && pwd)/$(basename "${SCRIPT}")"   # absolutize

UPROJECT="${CARLA_UE4_ROOT}/Unreal/CarlaUE4/CarlaUE4.uproject"
CMD="${UE4_ROOT}/Engine/Binaries/Linux/UE4Editor-Cmd"
[ -x "${CMD}" ] || { echo "[uepy] UE4Editor-Cmd missing — build UE4 first (build skill step 03)."; exit 1; }

# Release the project lock if a GUI editor is open.
if pgrep -f "UE4Editor.*CarlaUE4.uproject" >/dev/null; then
  if ${CLOSE_EDITOR}; then
    echo "[uepy] closing running GUI editor (holds project lock)..."
    for p in $(pgrep -f "UE4Editor.*CarlaUE4.uproject"); do kill -TERM "$p" 2>/dev/null || true; done
    for _ in $(seq 1 15); do pgrep -f "UE4Editor.*CarlaUE4.uproject" >/dev/null || break; sleep 1; done
    for p in $(pgrep -f "UE4Editor.*CarlaUE4.uproject"); do kill -KILL "$p" 2>/dev/null || true; done
  else
    echo "[uepy] ERROR: GUI editor is running and holds the lock. Re-run with --close-editor."
    exit 1
  fi
fi

echo "[uepy] running ${SCRIPT} headless..."
"${CMD}" "${UPROJECT}" \
  -stdout -unattended -nosplash -nopause -nullrhi \
  -EnablePlugins=PythonScriptPlugin \
  -ExecutePythonScript="${SCRIPT}" \
  "${EXTRA[@]}"
echo "[uepy] done (rc=$?)."
