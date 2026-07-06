---
name: build-carla-ue4-linux
description: Build CARLA (branch ue4-dev, Unreal Engine 4.26) from source on Linux, end-to-end, including Ubuntu 24.04. Produces a headless server + a Python client wheel and verifies them.
inputs:
  - UE4_ROOT: path to the CarlaUnreal UE4.26 fork checkout (default: <repo>/UnrealEngine_4.26)
  - CARLA_UE4_ROOT: path to the carla source checkout on branch ue4-dev (default: <repo>/carla)
  - CARLA_CONDA_ENV: conda env name for the client (default: carla-ue4)
  - CARLA_PY_VERSION: client python version (default: 3.10)
---

# Build CARLA ue4-dev on Linux (end-to-end)

This skill builds CARLA from the **`ue4-dev`** branch (Unreal Engine **4.26**), on
Ubuntu 20.04 / 22.04 / **24.04**. Each step is an idempotent script under
`steps/`; the scripts ARE the procedure — running them in order performs and
verifies the build.

## Access note (for users without Unreal access)

The UE4 fork is private to the Epic Games GitHub org. Before step 03 a user
MUST:
1. Have a GitHub account **linked to Epic Games** (https://www.unrealengine.com/en-US/ue-on-github).
2. Be able to clone `https://github.com/CarlaUnreal/UnrealEngine.git` (branch `carla`).

If `git clone` of the fork returns `repository not found` / `403`, the account
is not linked yet — STOP and surface this message; the rest of the build cannot
proceed. (An MCP exposing this skill should detect the missing `${UE4_ROOT}/Engine`
and return exactly this guidance rather than failing opaquely.)

## Prerequisites

- Linux, x86_64. Ubuntu 20.04 / 22.04 supported; **24.04 works** with the shims below.
- ~**120 GB** free disk (UE4 ~80 GB + content ~31 GB + intermediate builds).
- NVIDIA GPU (RTX 2000-series or better) for the rendering server.
- A conda/miniconda install (used for the Python client env).

> **Full battle-log:** [`LESSONS.md`](LESSONS.md) — every non-obvious failure
> hit during this build, with root cause + fix. Read it before debugging.

## Ubuntu 24.04 deltas (the "changes" needed beyond the official docs)

The `ue4-dev` branch already ships `Util/BuildTools/Ubuntu24Compat.sh`, sourced
by `Setup.sh`, which auto-detects and patches three issues at build time:

1. **Old bundled linker vs glibc ≥ 2.36.** UE4's bundled `ld` (2019) cannot read
   `.relr.dyn` sections present on Ubuntu 22.04+. Fix: the compiler is wrapped
   with `-fuse-ld=lld`. ⇒ **`lld` must be installed** (`sudo apt install lld`);
   the shim hard-fails otherwise. (Handled in `steps/01_install_deps.sh`.)
2. **PEP 668 externally-managed Python.** Ubuntu 24 blocks `pip install` into
   system Python, so the build sets `_SKIP_PIP_INSTALL` and leaves the client
   wheel in `PythonAPI/carla/dist/`. We install it into a conda env instead.
3. **CMake ≥ 4.0** rejects `cmake_minimum_required < 3.5` in third-party
   sources. Fix: `cmake` is wrapped to inject `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`.

Additional host-specific gotchas:
- System python here is 3.13 (anaconda `base`); too new for the boost.python
  bindings. We build the client against a dedicated **conda py3.10** env.
- **numpy must be < 2.0**: bindings are compiled against the numpy 1.x C-API.
- **Python version consistency**: `--python-version` passed to `make PythonAPI`
  forwards to the `setup` target, so boost.python (Setup.sh) and the wheel
  (BuildPythonAPI.sh) bind to the same interpreter. A mismatch → `ImportError`.

## Steps (run in order)

| # | Script | What | Notes |
|---|--------|------|-------|
| 00 | `steps/00_check_env.sh` | Preflight report | read-only |
| 01 | `steps/01_install_deps.sh` | apt deps incl `lld`, `libtiff-dev`, `g++-12` | **needs sudo** |
| 02 | `steps/02_conda_env.sh` | conda env `carla-ue4` (py3.10, numpy<2) | no sudo |
| 03 | `steps/03_build_ue4.sh` | UE4 fork: Setup → GenerateProjectFiles → make | ~10GB dl + ~1h; **no `-j`** |
| 04 | `steps/04_build_pythonapi.sh` | LibCarla client + boost + wheel → install to env | needs 02+03 |
| 05 | `steps/05_fetch_content.sh` | `git clone` carla-content (bitbucket) → Content/Carla | ~31GB; parallel-safe |
| 06 | `steps/06_build_editor.sh` | `make package` (headless) or `TARGET=launch` (editor) | needs 03+05 |
| 07 | `steps/07_verify.sh` | start headless server, run `generate_traffic.py` | proof |

Dependency graph: `01,02` independent; `03` & `05` independent (run in parallel);
`04` needs `02+03`; `06` needs `03+05`; `07` needs `04+06`.

### Environment

`env.sh` defines `UE4_ROOT`, `CARLA_UE4_ROOT`, `CARLA_CONDA_ENV`, `CARLA_PY_VERSION`.
Every step sources it; override by exporting before running.

### Quick start

```bash
cd skills/build-carla-ue4-linux
bash steps/00_check_env.sh
bash steps/01_install_deps.sh          # sudo
bash steps/02_conda_env.sh &           # parallel
bash steps/03_build_ue4.sh &           # parallel, long
bash steps/05_fetch_content.sh &       # parallel, long
wait
bash steps/04_build_pythonapi.sh
bash steps/06_build_editor.sh          # TARGET=package (default) or launch
bash steps/07_verify.sh
```

## Outputs

- UE4 editor binary: `${UE4_ROOT}/Engine/Binaries/Linux/UE4Editor`
- Headless server package: `${CARLA_UE4_ROOT}/Dist/CARLA_*/LinuxNoEditor/CarlaUE4.sh`
- Python client wheel installed into conda env `${CARLA_CONDA_ENV}`
- Maps/assets: `${CARLA_UE4_ROOT}/Unreal/CarlaUE4/Content/Carla`

## Build system note

`ue4-dev` uses the classic **Makefile** flow (`make PythonAPI`, `make launch`,
`make package`) — NOT the root `CarlaSetup.sh`/CMake flow seen on `ue5-dev`.
The readthedocs "latest" Linux page matches this flow, but this branch HEAD is
modernized (boost 1.90, the Ubuntu24 shims); trust the scripts here over stale
prose.
