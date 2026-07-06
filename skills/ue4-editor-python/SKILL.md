---
name: ue4-editor-python
description: Drive the CarlaUE4 project from UE4's editor Python API, headless — read/modify blueprints, assets, maps, props via the AssetRegistry and editor scripting, without the GUI.
inputs:
  - UE4_ROOT / CARLA_UE4_ROOT: inherited from the build-carla-ue4-linux skill's env.sh
  - script: path to a UE editor Python script to execute
---

# UE4 editor Python (project-direct surface)

The CARLA MCP needs to operate **directly on the CarlaUE4 project** — list and
edit blueprints, inspect/modify assets, generate maps, place props. That is the
editor's job, not the runtime RPC. This skill runs UE4 editor Python headless so
an agent can do it scriptably.

Prereq: UE4 + CARLA built (see [`../build-carla-ue4-linux/SKILL.md`](../build-carla-ue4-linux/SKILL.md)).

## How it works

`run_python.sh <script.py>` invokes:

```bash
UE4Editor-Cmd CarlaUE4.uproject \
  -stdout -unattended -nosplash -nopause -nullrhi \
  -EnablePlugins=PythonScriptPlugin \
  -ExecutePythonScript="<abs script>"
```

- Embedded interpreter is **Python 3.7.7** (UE4.26's bundled Python) — independent
  of the conda client env; the `unreal` module is only importable here.
- `PythonScriptPlugin` is **not** enabled in `CarlaUE4.uproject`, so we enable it
  per-invocation with `-EnablePlugins`.
- `-nullrhi` → no GPU/rendering needed for asset work.

## Usage

```bash
cd skills/ue4-editor-python
# GUI editor closed:
bash run_python.sh scripts/list_blueprints.py
# GUI editor open (release its lock first):
bash run_python.sh scripts/list_blueprints.py --close-editor
```

Scripts should **write results to a file** (a late engine crash can swallow
stdout). `list_blueprints.py` writes `scripts/bp_result.txt`.

## Verified capability

`scripts/list_blueprints.py` enumerated **851 Blueprint-class assets** via the
AssetRegistry, grouped by package path and parent class (44 `CarlaWheeledVehicle`,
43 `WalkerBase`, 30 `TrafficSignBase`, 21 `TrafficLightBase`, etc.) — parent
classes read from registry **tags** (no asset loading).

## Patterns for new scripts

- Query without loading: `ar.get_assets_by_class(...)`, `a.get_tag_value(...)`.
- Load only when modifying: `unreal.EditorAssetLibrary.load_asset(path)`.
- Save edits: `unreal.EditorAssetLibrary.save_asset(path)`.
- Blueprint graph/CDO work needs the asset loaded — do it deliberately, and
  expect it to be slower and RHI-sensitive.

See [`LESSONS.md`](LESSONS.md) for the crash modes and fixes.
