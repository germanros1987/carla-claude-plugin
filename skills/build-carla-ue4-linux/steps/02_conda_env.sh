#!/usr/bin/env bash
# Step 02 — create the conda env for the CARLA Python client.
#
# Why conda on Ubuntu 24.04: system python is externally-managed (PEP 668) and
# is 3.13 here (too new for CARLA's boost.python bindings). A dedicated 3.10
# env gives a clean, writable interpreter whose `python3.10` we feed to BOTH
# the boost build (Setup.sh) and the wheel build (BuildPythonAPI.sh) so the
# bindings link against one consistent ABI.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${HERE}/../env.sh"

# Locate conda.
if ! command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source "${HOME}/anaconda3/etc/profile.d/conda.sh" 2>/dev/null \
    || source "${HOME}/miniconda3/etc/profile.d/conda.sh" 2>/dev/null \
    || { echo "[conda] conda not found"; exit 1; }
fi

if conda env list | grep -qE "^${CARLA_CONDA_ENV}\s"; then
  echo "[conda] env '${CARLA_CONDA_ENV}' exists — skipping create."
else
  echo "[conda] creating env '${CARLA_CONDA_ENV}' (python ${CARLA_PY_VERSION})..."
  conda create -y -n "${CARLA_CONDA_ENV}" "python=${CARLA_PY_VERSION}"
fi

# Build-time deps for the wheel (build, auditwheel, pyelftools, ...) + a pinned
# numpy<2: CARLA's bindings are compiled against the numpy 1.x C-API and crash
# on import under numpy 2.x.
echo "[conda] installing client build deps + numpy<2..."
conda run -n "${CARLA_CONDA_ENV}" python -m pip install --upgrade \
  -r "${CARLA_UE4_ROOT}/PythonAPI/carla/requirements.txt" \
  "numpy<2.0.0"

echo "[conda] python in env:"
conda run -n "${CARLA_CONDA_ENV}" python --version
echo "[conda] DONE."
