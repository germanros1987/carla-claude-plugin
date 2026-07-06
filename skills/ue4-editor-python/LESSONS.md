# Lessons — UE4 editor Python (headless commandlet)

Battle-log from getting UE4 editor Python to run reliably against CarlaUE4.
Each: **symptom → root cause → fix → where encoded**.

---

### P1 — PythonScriptPlugin is built but not enabled in the project
- **Symptom:** `unreal` module unavailable / `-ExecutePythonScript` ignored.
- **Cause:** `CarlaUE4.uproject` does not list `PythonScriptPlugin`, though the engine ships it and the build compiled `libUE4Editor-PythonScriptPlugin.so`.
- **Fix:** enable per-invocation: `-EnablePlugins=PythonScriptPlugin` (no need to edit the uproject).
- **Encoded:** `run_python.sh`.

### P2 — `-NoShaderCompile` crashes the editor (SIGSEGV in a Slate notification)
- **Symptom:** engine inits, Python 3.7.7 loads, then SIGSEGV reading `0x68`. Callstack: `FShaderCompilingNotificationImpl::ShouldShowNotification` ← `FGlobalNotification::TickNotification` ← `UEditorEngine::Tick`.
- **Cause:** `-NoShaderCompile` leaves `GShaderCompilingManager` null, but the editor's global shader-compiling **notification still ticks** and derefs it.
- **Fix:** do NOT pass `-NoShaderCompile`. `-nullrhi` alone is fine and still skips rendering.
- **Encoded:** `run_python.sh` omits it deliberately.

### P3 — Don't load assets in a `-nullrhi` commandlet just to read metadata
- **Symptom:** first script crashed while iterating blueprints (calling `load_blueprint_class` / `get_default_object` per asset).
- **Cause:** loading blueprint classes pulls in dependencies that are RHI/CDO-sensitive under nullrhi.
- **Fix:** read what you need from **AssetRegistry tags** — `a.get_tag_value("NativeParentClass")`, `"ParentClass"`, `"GeneratedClass"` — which require no asset load. Only `load_asset` when you actually modify.
- **Encoded:** `scripts/list_blueprints.py`.

### P4 — Write results to a file, not just stdout
- **Symptom:** Python clearly ran (`LogPython: Using Python 3.7.7`) but no captured output after a later crash.
- **Cause:** a crash during engine shutdown/tick can truncate buffered stdout.
- **Fix:** scripts write results to a file (`bp_result.txt`); the runner reads the file, not the log.
- **Encoded:** `scripts/list_blueprints.py` writes `UEPY_RESULT`.

### P5 — The GUI editor holds the project lock
- **Symptom:** headless commandlet conflicts / refuses while the GUI editor is open on the same `.uproject`.
- **Cause:** UE takes a project lock + shares `Saved/`, `Intermediate/`, and the DDC; two instances corrupt or block.
- **Fix:** close the GUI editor before running a headless commandlet. `run_python.sh --close-editor` does this (TERM, wait, then KILL).
- **Encoded:** `run_python.sh`.

### P6 — Killing UE from scripts: match the right PID, avoid self-match
- **Symptom:** `pkill -f "Package.sh"`-style calls returned 144 and aborted the shell; the launcher PID ≠ the real editor PID.
- **Cause:** `pkill -f <pattern>` also matches the very shell running the command (its args contain the pattern); and the launch wrapper PID is not the editor process.
- **Fix:** resolve concrete PIDs with `pgrep -f` and `kill` them explicitly; verify with `ps -eo comm | grep -c` (authoritative, won't self-match).
- **Encoded:** `run_python.sh` loops over `pgrep` PIDs.

### P8 — UE4.26 embedded Python opens files as ASCII; non-ASCII writes crash
- **Symptom:** script aborted mid-run with `UnicodeEncodeError: 'ascii' codec can't encode character '—'` on a `—` em-dash; rc still 0, partial output only.
- **Cause:** UE4.26's embedded Python 3.7 runs with an ASCII default locale, so `open(path,'w')` uses ASCII; writing any non-ASCII char throws.
- **Fix:** `open(path, 'w', encoding='utf-8')`, and prefer plain ASCII in output strings.
- **Encoded:** `scripts/probe_vehicle_api.py`.

### P9 — Content layout differs from the docs (Static/Car, not Static/Vehicles)
- The tutorial says meshes live in `Content/Carla/Static/Vehicles/4Wheeled`, but the actual ue4-dev content has the Mustang at `Content/Carla/Static/Car/4Wheeled/Mustang/`. Always discover real paths via the AssetRegistry, not the docs.

### P7 — UE Python is 3.7.7, separate from the conda client
- The embedded interpreter (PythonScriptPlugin) is **3.7.7**; `import carla` (the
  conda 3.10 client) and `import unreal` (editor) live in **different** worlds.
  Editor scripting ≠ the RPC client. Don't cross them.
