#!/usr/bin/env bash
# Step 00 — preflight. Read-only checks that the host can build CARLA ue4-dev.
# Prints a PASS/WARN/FAIL report; exits non-zero only on hard blockers.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${HERE}/../env.sh"

rc=0
ok(){   echo "  PASS $*"; }
warn(){ echo "  WARN $*"; }
bad(){  echo "  FAIL $*"; rc=1; }

echo "== OS =="
. /etc/os-release
case "${VERSION_ID}" in
  20.04|22.04) ok "Ubuntu ${VERSION_ID} (officially supported)";;
  24.04)       warn "Ubuntu 24.04 — supported via Ubuntu24Compat.sh (needs lld; PEP668 wheel install).";;
  *)           warn "Ubuntu ${VERSION_ID:-?} — untested.";;
esac

echo "== Disk (need ~120GB free: UE ~80 + content ~31 + builds) =="
FREE_G=$(df -BG --output=avail "${REPO_ROOT}" | tail -1 | tr -dc '0-9')
[ "${FREE_G:-0}" -ge 120 ] && ok "${FREE_G}G free" || warn "${FREE_G}G free (<120G)"

echo "== Tools =="
for t in git git-lfs cmake ninja make; do command -v "$t" >/dev/null && ok "$t" || bad "$t missing"; done
command -v ld.lld >/dev/null && ok "ld.lld (24.04 linker fix)" \
  || { [ "${VERSION_ID}" = "24.04" ] && bad "ld.lld missing (REQUIRED on 24.04: sudo apt install lld)" || warn "ld.lld missing"; }

echo "== UE4 fork =="
if [ -d "${UE4_ROOT}/Engine" ]; then
  if [ -x "${UE4_ROOT}/Engine/Binaries/Linux/UE4Editor" ]; then ok "UE4 built"; else warn "UE4 cloned but NOT built (run step 03)"; fi
else
  warn "UE4 fork not cloned at ${UE4_ROOT} (step 03 will instruct)"
fi

echo "== CARLA source =="
if [ -d "${CARLA_UE4_ROOT}/.git" ]; then
  BR=$(git -C "${CARLA_UE4_ROOT}" branch --show-current)
  [ "${BR}" = "ue4-dev" ] && ok "carla on ue4-dev" || warn "carla on '${BR}' (expected ue4-dev)"
else
  bad "carla source not found at ${CARLA_UE4_ROOT}"
fi
# A bare Content/Carla dir is created by `git clone` immediately, so its mere
# existence does not mean the ~31GB checkout finished. Require the .git repo AND
# at least one checked-out asset entry (populated only once checkout completes).
CONTENT="${CARLA_UE4_ROOT}/Unreal/CarlaUE4/Content/Carla"
if [ -d "${CONTENT}/.git" ] && [ -n "$(find "${CONTENT}" -mindepth 1 -maxdepth 1 ! -name '.git' -print -quit 2>/dev/null)" ]; then
  ok "Content present"
elif [ -d "${CONTENT}/.git" ]; then
  warn "Content clone in progress / incomplete (step 05 not finished)"
else
  warn "Content missing (step 05)"
fi

echo "== Conda =="
command -v conda >/dev/null 2>&1 || source "${HOME}/anaconda3/etc/profile.d/conda.sh" 2>/dev/null || true
if command -v conda >/dev/null 2>&1; then
  conda env list | grep -qE "^${CARLA_CONDA_ENV}\s" && ok "env ${CARLA_CONDA_ENV} exists" || warn "env ${CARLA_CONDA_ENV} not created (step 02)"
else
  warn "conda not on PATH"
fi

echo "== Result =="
[ "$rc" -eq 0 ] && echo "  preflight OK (warnings are non-blocking)" || echo "  HARD BLOCKERS present — fix FAIL items."
exit $rc
