# Lessons — add-carla-vehicle skill

Battle-log from building and verifying the headless vehicle-authoring workflow.
Format mirrors ue4-editor-python/LESSONS.md: **symptom -> root cause -> fix -> where encoded**.

Inherits all lessons from [[ue4-editor-python]] (P1-P9) — those apply here too.
See also [[build-carla-ue4-linux]] for build-time lessons.

---

### V17 — A cloned skeletal mesh shares the donor's PhysicsAsset; generate a dedicated one
- **Symptom / risk:** `SM_TestCar` was duplicated from `SM_Mustang_v2`, so it inherited
  the pointer to the **shared** `SM_Mustang1966_PhysicsAsset`. The old
  `setup_vehicle_physics_asset` edited `Mesh->PhysicsAsset` in place — i.e. it mutated
  the REAL Mustang's physics asset (wheel bodies → r16, etc.). It also looked up the
  chassis body by the hard-coded name `Vehicle_Base`, which silently missed (the
  skeleton's root bone is named differently), so the chassis was never configured.
- **Root cause:** `duplicate_asset` copies the mesh's `PhysicsAsset` reference, not the
  asset; there is no per-vehicle PA until you make one.
- **Fix:** `SetupVehiclePhysicsAsset` now builds a DEDICATED `<Mesh>_PhysicsAsset` next
  to the mesh via `FPhysicsAssetUtils::CreateFromSkeletalMesh` (auto convex chassis hull
  from the skinned verts), assigns it to the mesh, then: chassis = the single NON-wheel
  body (name-agnostic — no `Vehicle_Base` hard-code), simulated, optionally overridden
  by the artist `SMC_` hull; the 4 canonical wheel bones = KINEMATIC spheres sized to
  `WHEEL_RADIUS`. Verified: `SM_TestCar_PhysicsAsset` (6.8K, clean 5-body) created,
  Mustang PA (94.4K) untouched, `vehicle.ford.testcar` still drives under TM (PASS).
- **Geometry answer (for artists):** nothing extra is required — the chassis hull is
  generated from the provided skeletal mesh and the wheels are parametric spheres
  (radius only). An `SMC_<model>` hull is an OPTIONAL quality upgrade, not an input.
- **Also (probe trap):** UE4.26 Python CANNOT introspect physics-asset bodies —
  `PhysicsAsset.skeletal_body_setups` raises "Failed to find property". A probe helper
  that returned an `"ERR(...)"` string on failure was then `len()`-counted, inventing a
  phantom "155 bodies / 143 constraints" (those were the error-string lengths). PA
  inspection must be done in C++ (the generator now `UE_LOG`s every body it makes).
- **Encoded:** `VehicleAuthoringLibrary::SetupVehiclePhysicsAsset` (3-arg: +WheelRadius),
  `scripts/add_vehicle.py` [6], `SKILL.md` artist prereqs.

### V1 — Unsaved duplicated assets are lost on editor SIGKILL (the big one)
- **Symptom:** the new vehicle BP's `Mesh.skeletal_mesh` read `None` on every fresh
  reload, despite C++ setting it correctly in-memory (`before save='SM_TestCar'`).
  Many rebuild cycles were spent chasing a "native-component serialization" ghost.
- **Root cause:** `EditorAssetLibrary.duplicate_asset` creates the asset **in memory
  only**. `run_python.sh --close-editor` closes the editor with SIGKILL, skipping
  autosave — so the duplicated `SM_TestCar` skeletal mesh was **never written to disk**
  (its folder was empty). The BP referenced `SM_TestCar` correctly, but on reload the
  missing asset resolved to null → `None`.
- **Fix:** call `unreal.EditorAssetLibrary.save_asset(dest)` right after every
  `duplicate_asset`. Confirm assets exist on disk, not just "dup OK" in the manifest.
- **Lesson:** when the editor is killed rather than shut down cleanly, ANY asset you
  create/modify must be **explicitly saved**. "OK" in a log = in-memory success, not
  on-disk persistence.
- **Encoded:** `scripts/add_vehicle.py` `dup()` helper.

### V2 — Set inherited-component defaults via the editor path, not raw SavePackage
- **Symptom:** C++ `CDOMesh->SetSkeletalMesh` + `UPackage::SavePackage` did not
  serialise the native-component override (compounded V1's confusion).
- **Cause:** raw `SavePackage` doesn't write an inherited native-component subobject
  delta the way the editor details-panel edit does.
- **Fix:** set the mesh from Python via
  `mesh_comp.set_editor_property("skeletal_mesh", m)` + `save_loaded_asset(bp)` — the
  editor-faithful edit+save flow that demonstrably persists. C++ still does the
  duplicate + anim + wheel_setups (those persist fine).
- **Encoded:** `scripts/add_vehicle.py` step `[8b]`.

### V3 — ~~shipped VehicleFactory is graph-literal, not data-driven~~ **WRONG — see V14**
- **This lesson was incorrect and caused a multi-hour dead end.** I claimed the
  shipped `VehicleFactory` had "no reflectable array to append to" and therefore
  built a custom runtime `AAuthoredVehicleFactory` (DataTable-driven) instead.
- **Reality:** `VehicleFactory`'s generated-class CDO exposes a fully reflected
  `vehicles` array (`TArray<FVehicleParameters>`, len 41 stock). It IS appendable
  from Python: `cdo.get_editor_property("vehicles")` → append an
  `unreal.VehicleParameters()` → `set_editor_property` back → force-save (V8). This
  is exactly the tutorial's Step 8.
- The custom factory not only was unnecessary — it was **broken** (V14): vehicles
  spawned through it do not drive. **Register via the shipped VehicleFactory.**
- **Superseded by:** [[V14]]; `add_vehicle.py` step `[9]`.

### V4 — UE python name is `register_vehicle_in_data_table`
- UE tokenises `DataTable` → `data_table`. When a UFUNCTION binding seems "missing",
  `dir(unreal.X)` gives the exact snake_case — don't guess.

### V5 — `.generated_class()` / `get_editor_property("generated_class")` fail (UE4.26)
- Both fail on a UE4.26 `Blueprint` python object. Only reliable path:
  `unreal.EditorAssetLibrary.load_blueprint_class("/Game/.../BP_Foo")`.

### V6 — Verify persistence in a SEPARATE process
- In-process reads reflect live/unsaved state → false positives. Prove persistence by
  reading from a freshly-launched editor process (that caught V1/V2). `rm` stale
  result files first.

### V7 — Wheel class/bone order must match
- wheels list `[FL, FR, RR, RL]` must align with WHEEL_BONES
  `["Wheel_Front_Left","Wheel_Front_Right","Wheel_Rear_Right","Wheel_Rear_Left"]`
  index-for-index, or rear wheels cross-bind.

### V8 — CDO default edit + `save_asset` silently NO-OPs (registration never persisted)
- **Symptom:** `setup_registration.py` reported the GameMode's `actor_factories` set
  now contained `AuthoredVehicleFactory` (in-process read), the run exited 0, yet on
  a running server `vehicle.ford.testcar` was **absent** — only the 40 shipped
  vehicles registered. `strings CarlaGameMode.uasset` showed the 8 stock factories,
  **no AuthoredVehicleFactory** → the edit never hit disk.
- **Root cause:** `unreal.EditorAssetLibrary.save_asset(path)` defaults
  `only_if_is_dirty=True`. Mutating a Blueprint **CDO** default via
  `get_default_object()` + `set_editor_property()` updates the live CDO but does
  **not** flag the package dirty → `save_asset` sees "clean" and writes nothing. (The
  DataTable saved fine because `create_asset` dirties its package.) Same family as V2:
  a Python object edit that doesn't persist through the naive save path.
- **Fix:** force the write — `save_asset(GM_PATH, only_if_is_dirty=False)`. Returns
  `True` and the class name then appears in the uasset on disk. (`Package` has no
  `mark_package_dirty`/`dirty` attribute in 4.26 py — don't rely on dirtying; just
  force the save.)
- **Encoded:** `scripts/setup_registration.py` step [2] save block.

### V9 — "Verified" must mean *in a running server*, not an in-process read
- **Symptom:** the feature was called "registered + verified" on the strength of a
  fresh-editor reload that confirmed the skeletal mesh (V6). But that only proved the
  BP/DataTable assets; the **GameMode factory wiring** (V8) was never exercised, and
  it was silently broken. The gap only surfaced when a real `carla.Client` queried the
  blueprint library.
- **Lesson:** verification has **layers**. Fresh-editor reload proves asset
  persistence; only a **running CARLA server + RPC client spawn** proves runtime
  registration + physics. Do not claim a spawnable is registered until
  `spawn_test.py` PASSES against a live server. Extends V6 one layer up.
- **Encoded:** `scripts/spawn_test.py` is the gate; SKILL.md "Verify" section.

### V10 — `blueprint_library.find()` RAISES when absent (not None)
- **Symptom:** the missing-vehicle case aborted with a bare `IndexError: blueprint
  'vehicle.ford.testcar' not found` traceback instead of the intended diagnostic
  "available vehicle.* blueprints" listing.
- **Cause:** `carla.BlueprintLibrary.find(id)` throws on a miss; the code assumed it
  returned `None`.
- **Fix:** wrap `find()` in `try/except (IndexError, RuntimeError)` → `None`, then fall
  through to the `filter()` + diagnostic path.
- **Encoded:** `scripts/spawn_test.py` step [2].

### V12 — Drivability must be measured by VELOCITY, not displacement (false PASS)
- **Symptom:** `spawn_test.py` reported `vehicle.ford.testcar` "moved 142.389 m →
  VERDICT PASS". It had **not moved at all** — under full throttle its speed was
  0.000 m/s. The feature was declared verified/e2e-done on this false PASS.
- **Root cause (two compounding bugs):**
  1. `actor.get_location()` **immediately after spawn returns ~(0,0,0)** (the
     transform hasn't replicated yet). The test's `loc0` captured that origin, so
     `displacement = |loc1 - loc0|` measured the spawn point's distance **from the
     world origin** (~142 m in Town02), not motion.
  2. It used **autopilot** as the motion source with a *soft-warn* on no-move — so a
     genuinely immobile car produced no failure.
- **Fix:** settle ~0.5 s before sampling; drive with **manual full throttle** (no
  traffic-manager dependency); assert on **peak `get_velocity()` speed** (≥0.5 m/s),
  which cannot be faked by the spawn-origin artifact. Cross-check against a stock
  vehicle (mustang drives ~12 m/s; testcar 0).
- **Also:** destroy leftover actors before testing — a car spawned on top of an
  existing one gets ejected by PhysX and reads a bogus high speed (another false
  PASS). `for a in world.get_actors().filter("vehicle.*"): a.destroy()`.
- **Meta-lesson:** a green check on the wrong metric is worse than no check. Pick a
  metric the failure mode **cannot** satisfy. Extends V9.
- **Encoded:** `scripts/spawn_test.py` step [4]-[6].

### V14 — A custom ACarlaActorFactory spawns vehicles that WON'T DRIVE — use the shipped VehicleFactory
- **Symptom:** `vehicle.ford.testcar` (via our custom `AAuthoredVehicleFactory`)
  spawned, its rigid body simulated (`add_impulse` flung it), `get_physics_control`
  read correct wheels/engine/differential — yet **0 m/s under full throttle**. Every
  asset (mesh, skeleton, PhysicsAsset, wheels, wheel CDOs, drivetrain, components,
  compile state) was byte-identical to the drivable Mustang. Hours were lost probing
  the *vehicle*.
- **Decisive test (should have been FIRST):** register the **known-good BP_Mustang66**
  through our custom factory. It **also froze** (0 m/s), while `vehicle.ford.mustang`
  via the shipped factory drove ~16 m/s. → The defect was the **factory**, not the
  vehicle.
- **Root cause:** the shipped `VehicleFactory` is a Blueprint whose `SpawnActor` graph
  does CARLA's proper vehicle spawn (deferred spawn → apply params → `FinishSpawning`),
  which initialises the PhysX `WheeledVehicle`. Our C++ factory did a naive
  `World->SpawnActor<AActor>(Class, Transform)` — the actor exists and its body
  simulates, but the wheeled-vehicle drive is never initialised → no traction.
- **Fix:** do NOT build a custom factory. Register by appending an `FVehicleParameters`
  to the shipped **VehicleFactory**'s reflected `vehicles` array (tutorial Step 8;
  V3 was wrong to say this was impossible). Then spawns go through the working graph.
  Verified: `vehicle.ford.testcar` drives 17.3 m/s at multiple spawn points.
- **Meta-lesson:** when a synthesised artifact fails but is *identical* to a working
  reference, the bug is in the **surrounding machinery** (spawn/registration path),
  not the artifact. Run the swap test (good artifact through your path / your artifact
  through the good path) BEFORE deep-diving the artifact.
- **Encoded:** `add_vehicle.py` step `[9]` (VehicleFactory append); custom
  `AAuthoredVehicleFactory` / `setup_registration.py` DEPRECATED. Supersedes V3, V13.

### V15 — `sticky_control=false` makes the vehicle ignore apply_control (false "frozen")
- **Symptom:** after the real drive bug (V14) was fixed and the car demonstrably drove
  (17 m/s in a scratch client), `spawn_test.py` STILL reported 0 m/s / FAIL.
- **Root cause:** `spawn_test` set the blueprint attribute `sticky_control=false`
  (to "let autopilot work cleanly"). With sticky control disabled the vehicle
  **ignores `apply_control` entirely** — verified 0.00 m/s vs 17.8 m/s with the
  default — and re-applying every tick does NOT help.
- **Fix:** leave `sticky_control` at its default (true) when driving via manual
  `apply_control`. Removed the disable line.
- **Encoded:** `scripts/spawn_test.py` (sticky_control note + leftover cleanup). With
  V12 + V14 + this, the gate now PASSES on a drivable car and FAILS on a stuck one.

### V16 — Default drivability test is AUTOPILOT / Traffic Manager, not manual throttle
- Production spawns drive via the Traffic Manager, so that is what the gate must
  exercise. `spawn_test.py` default: `set_autopilot(True, tm.get_port())`, observe up
  to 20 s (early-exit once moving), assert peak **velocity** ≥ 1 m/s. Verified:
  `vehicle.ford.testcar` drives itself under TM (8 m/s cruising, 29 m in 30 s).
- On no-motion it falls back to a manual full-throttle burst purely to DIAGNOSE:
  manual-moves ⇒ drivetrain OK, TM just didn't route it (light/yield — re-run);
  manual-also-stuck ⇒ real drive bug (check registration went through the shipped
  VehicleFactory, V14). Autopilot remains the pass criterion.
- **Encoded:** `scripts/spawn_test.py` steps [5]/[6].

### V13 — (RESOLVED by V14) authored vehicle spawned but did not drive
- Was suspected to be a PhysicsAsset/wheel defect. **It was not the vehicle at all** —
  the custom spawn factory never initialised the PhysX vehicle (V14). The mesh,
  PhysicsAsset (shared with Mustang), wheels and drivetrain were all correct. Kept as a
  record of the wrong trail: identical-to-working config that still failed →
  look outside the artifact.

### V11 — No cook needed: `-game -nullrhi` serves RPC on uncooked content
- The 30–60min `make package` cook is **not** required to test spawn/registration.
  Run the editor binary directly against the uncooked project:
  `UE4Editor CarlaUE4.uproject /Game/Carla/Maps/Town02 -game -nullrhi -nosound
  -carla-rpc-port=2000 -carla-streaming-port=2001` → RPC ready in ~15–20s, factory
  registration + physics + autopilot all work. **`-RenderOffScreen` on uncooked
  content crashes** the render thread on null mesh distance fields (see build
  [[build-carla-ue4-linux]] L17) — `-nullrhi` sidesteps rendering entirely. Cook only
  needed for camera/lidar sensors or a shippable artifact. See build lesson L17.
- **Encoded:** SKILL.md "Verify"; build LESSONS L17.
