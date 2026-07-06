#!/usr/bin/env bash
# Shared environment for the build-carla-ue4-linux skill.
# Source this before running any step:  source env.sh
#
# All paths are overridable from the caller's environment; the defaults match
# this repo's layout (carla/ and UnrealEngine_4.26/ live next to skills/).

set -euo pipefail

# --- Repo / build roots -----------------------------------------------------
# Resolve the repo root as the directory two levels above this file
# (skills/build-carla-ue4-linux/env.sh -> repo root).
_SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${_SKILL_DIR}/../.." && pwd)"

# UE4_ROOT: the CarlaUnreal UE 4.26 fork checkout (must be BUILT first).
export UE4_ROOT="${UE4_ROOT:-${REPO_ROOT}/UnrealEngine_4.26}"

# CARLA_UE4_ROOT: the carla source checkout (branch: ue4-dev).
export CARLA_UE4_ROOT="${CARLA_UE4_ROOT:-${REPO_ROOT}/carla}"

# --- Conda env for the CARLA Python client ----------------------------------
# Ubuntu 24.04 ships python as externally-managed (PEP 668); the build writes a
# wheel to PythonAPI/carla/dist/ and we install it into this dedicated env.
export CARLA_CONDA_ENV="${CARLA_CONDA_ENV:-carla-ue4}"
export CARLA_PY_VERSION="${CARLA_PY_VERSION:-3.10}"

# --- Build tuning -----------------------------------------------------------
# Parallelism for CARLA make steps. UE4's own `make` must NOT use -j (it OOMs /
# races); that is handled inside 03_build_ue4.sh, not here.
export CARLA_MAKE_JOBS="${CARLA_MAKE_JOBS:-$(nproc)}"

echo "[env] REPO_ROOT       = ${REPO_ROOT}"
echo "[env] UE4_ROOT        = ${UE4_ROOT}"
echo "[env] CARLA_UE4_ROOT  = ${CARLA_UE4_ROOT}"
echo "[env] CARLA_CONDA_ENV = ${CARLA_CONDA_ENV} (python ${CARLA_PY_VERSION})"
