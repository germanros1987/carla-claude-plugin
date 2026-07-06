#!/usr/bin/env bash
# Run add_vehicle.py headless inside the CarlaUE4 UE4 editor.
#
# Usage:
#   VEH_MAKE=Ford VEH_MODEL=Mustang66 bash run.sh [--close-editor]
#
# Env vars forwarded to add_vehicle.py:
#   VEH_MAKE      - make label          (default: Mustang)
#   VEH_MODEL     - model / folder name (default: Mustang66)
#   VEH_TEMPLATE  - template to clone   (default: Mustang)
#   VEH_MODE      - synthetic|other     (default: synthetic)
#   UEPY_RESULT   - override result file path (optional)
#
# Prerequisites:
#   1. UE4 + CarlaUE4 built (see build-carla-ue4-linux skill).
#   2. CarlaTools plugin compiled + CarlaUE4 project rebuilt so
#      unreal.VehicleAuthoringLibrary is available.
#   3. Template Mustang assets present in the content browser.
#
# Outputs:
#   scripts/add_vehicle_result.txt  - manifest of every step (utf-8)
#   stdout / UE4 log                - mirrored via unreal.log()
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${HERE}/scripts/add_vehicle.py"

# Export VEH_* vars so the headless editor Python picks them up.
export VEH_MAKE="${VEH_MAKE:-Mustang}"
export VEH_MODEL="${VEH_MODEL:-Mustang66}"
export VEH_TEMPLATE="${VEH_TEMPLATE:-Mustang}"
export VEH_MODE="${VEH_MODE:-synthetic}"

echo "[add-vehicle] make=${VEH_MAKE} model=${VEH_MODEL} template=${VEH_TEMPLATE} mode=${VEH_MODE}"

# Delegate to the shared UE Python runner; pass --close-editor through if given.
exec bash "${HERE}/../ue4-editor-python/run_python.sh" "${SCRIPT}" "$@"
