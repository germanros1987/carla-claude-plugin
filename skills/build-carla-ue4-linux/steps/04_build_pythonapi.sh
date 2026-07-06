#!/usr/bin/env bash
# Step 04 — build the CARLA Python API client (LibCarla client + boost.python
# bindings + osm2odr) and install the wheel into the conda env.
#
# Prereqs: step 03 (UE4 built -> bundled clang SDK) and step 02 (conda env).
#
# Key correctness points encoded here:
#   * --python-version=${CARLA_PY_VERSION} is passed to `make PythonAPI`, which
#     forwards ARGS to the `setup` target too. So boost.python (built in
#     Setup.sh) and the wheel (built in BuildPythonAPI.sh) bind to the SAME
#     interpreter. Mismatch => ImportError at `import carla`.
#   * The conda env is ACTIVATED so `/usr/bin/env python3.10` resolves to the
#     env interpreter (the build invokes it by exact minor version).
#   * On Ubuntu 24.04 the build sets _SKIP_PIP_INSTALL (PEP 668), leaving the
#     wheel in PythonAPI/carla/dist/. We install it explicitly into the env.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${HERE}/../env.sh"

[ -x "${UE4_ROOT}/Engine/Binaries/Linux/UE4Editor" ] \
  || { echo "[py] ERROR: UE4 not built yet (run step 03)."; exit 1; }

# Activate conda env so python${CARLA_PY_VERSION} on PATH is the env's.
# NOTE: the `conda` *binary* being on PATH is not enough — `conda activate` is a
# shell function defined by conda.sh, which a non-interactive shell has not
# sourced. Source it unconditionally (locate base via the binary).
_CONDA_BASE="$(conda info --base 2>/dev/null || echo "${HOME}/anaconda3")"
# shellcheck disable=SC1091
source "${_CONDA_BASE}/etc/profile.d/conda.sh"
conda activate "${CARLA_CONDA_ENV}"
echo "[py] using: $(command -v python${CARLA_PY_VERSION}) ($(python${CARLA_PY_VERSION} --version))"

cd "${CARLA_UE4_ROOT}"

echo "[py] make PythonAPI (boost + LibCarla client + osm2odr + wheel)..."
make PythonAPI ARGS="--python-version=${CARLA_PY_VERSION} --build-wheel"

# Install the freshly built wheel into the env (PEP 668 left it in dist/).
WHEEL="$(ls -t "${CARLA_UE4_ROOT}"/PythonAPI/carla/dist/*.whl 2>/dev/null | head -1 || true)"
[ -n "${WHEEL}" ] || { echo "[py] ERROR: no wheel produced in PythonAPI/carla/dist/"; exit 1; }
echo "[py] installing ${WHEEL} into ${CARLA_CONDA_ENV}..."
python -m pip install --force-reinstall "${WHEEL}"

echo "[py] verifying import..."
python -c "import carla; print('carla', carla.__version__ if hasattr(carla,'__version__') else 'imported OK')"
echo "[py] DONE."
