#!/usr/bin/env bash
# Step 06 — build the CarlaUE4 editor / server.
#
# Prereqs: step 03 (UE4), step 04 (LibCarla server is built by this target's
# deps), and step 05 (Content present, else maps are empty).
#
# Targets:
#   make launch   -> builds CarlaUE4Editor + opens the UE4 editor (interactive).
#   make package  -> builds a shippable, headless server in Dist/ (no editor UI).
#
# Default here is `package` because it is what the MCP server will actually
# drive (headless, scriptable). Override with TARGET=launch for editor work.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${HERE}/../env.sh"

TARGET="${TARGET:-package}"

[ -x "${UE4_ROOT}/Engine/Binaries/Linux/UE4Editor" ] \
  || { echo "[editor] ERROR: UE4 not built (step 03)."; exit 1; }
[ -d "${CARLA_UE4_ROOT}/Unreal/CarlaUE4/Content/Carla" ] \
  || echo "[editor] WARN: Content/Carla missing (step 05) — maps will be empty."

# `make package` builds the PythonAPI.wheel target near the end, which invokes
# `python${CARLA_PY_VERSION} -m build`. That module lives in the conda env, NOT
# system python — so the env must be active here too, exactly like step 04.
# Without it the package dies at the wheel stage with
# "No module named build.__main__" AFTER the long editor compile. (See L15.)
_CONDA_BASE="$(conda info --base 2>/dev/null || echo "${HOME}/anaconda3")"
# shellcheck disable=SC1091
source "${_CONDA_BASE}/etc/profile.d/conda.sh"
conda activate "${CARLA_CONDA_ENV}"
echo "[editor] using: $(command -v python${CARLA_PY_VERSION})"

cd "${CARLA_UE4_ROOT}"
echo "[editor] make ${TARGET} (heavy: shader compile, ~30-60min first run)..."
make "${TARGET}" ARGS="--python-version=${CARLA_PY_VERSION}"

if [ "${TARGET}" = "package" ]; then
  echo "[editor] package(s) in Dist/:"; ls -la "${CARLA_UE4_ROOT}/Dist/" 2>/dev/null | grep -i carla || true
fi
echo "[editor] DONE (${TARGET})."
