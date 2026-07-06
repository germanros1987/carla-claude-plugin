---
name: add-carla-vehicle
description: Headless UE4 editor Python skill that duplicates a Mustang template and wires up a new 4-wheeled vehicle via VehicleAuthoringLibrary C++ UFUNCTIONs.
requires: [[ue4-editor-python]], [[build-carla-ue4-linux]]
---

# add-carla-vehicle skill

Automates tutorial steps 8-19 of the CARLA "Add a new vehicle" workflow
(https://carla.readthedocs.io/en/latest/tuto_A_add_vehicle/) headlessly via
UE4 editor Python + a C++ authoring library.

---

## Artist FBX prereqs (steps 1-7 — OUT OF SCOPE for this skill)

These steps require a human artist and Blender/Maya; this skill does NOT
automate them. They must be completed before running `run.sh`.

1. Model the vehicle in Blender/Maya to CARLA scale (≈4-5 m long).
2. Create a **5-bone** skeleton with these EXACT bone names (they are fixed
   PxVehicleDrive4W roles — the wheel-order and physics wiring depend on them):
   a root chassis bone `VehicleBase`, plus `Wheel_Front_Left`,
   `Wheel_Front_Right`, `Wheel_Rear_Left`, `Wheel_Rear_Right` parented to it.
3. Rig and skin the mesh to the skeleton (the chassis collision hull is
   auto-generated from the verts weighted to `VehicleBase`).
4. Export a single FBX containing mesh + skeleton.
5. Export 4 separate wheel FBXs (one per wheel bone, small cylinder) — used only
   to size the wheels; the physics wheels are spheres derived from the radius.
6. Import the body FBX into UE4:
   `Content/Carla/Static/Car/4Wheeled/<Model>/SM_<Model>`.
   "Create physics asset" is OPTIONAL — the skill builds a dedicated
   `SM_<Model>_PhysicsAsset` itself (step [6]) and repoints the mesh to it, so
   any imported physics asset is superseded.
7. Import each wheel FBX into:
   `Content/Carla/Static/Car/4Wheeled/<Model>/SM_<Model>_<pos>`
   (pos = FL/FR/RL/RR).

Optional: provide a hand-simplified chassis collision hull as
`SMC_<Model>` (a StaticMesh). When present it replaces the auto-generated
convex hull for higher-quality chassis collision; when absent the skill
auto-generates a single convex hull from the skeletal mesh.

After these steps the content browser must contain the skeletal mesh, skeleton,
and 4 wheel meshes. The physics asset and per-wheel BPs are created by the skill.

---

## Automatable steps (8-19) and skill mapping

| Tutorial step | What it does                                        | Skill action                                |
|---------------|-----------------------------------------------------|---------------------------------------------|
| 8             | Create AnimBlueprint from Mustang template          | `create_vehicle_anim_bp` (C++)              |
| 9             | Retarget anim BP to new skeleton                    | handled inside `create_vehicle_anim_bp`     |
| 10            | Create wheel BPs from Mustang wheel BP template     | `duplicate_asset` x4 (synthetic mode)       |
| 11            | Set wheel radius / friction / handbrake per wheel   | `configure_wheel` x4 (C++)                 |
| 12            | Create main vehicle BP (WheeledVehicle parent)      | `create_vehicle_blueprint` (C++)            |
| 13            | Assign skeletal mesh to BP                          | handled inside `create_vehicle_blueprint`   |
| 14            | Assign physics asset                                | handled inside `create_vehicle_blueprint`   |
| 15            | Assign anim BP to mesh component                   | handled inside `create_vehicle_blueprint`   |
| 16            | Add wheel components, assign wheel BPs              | handled inside `create_vehicle_blueprint`   |
| 17            | Configure vehicle movement component                | handled inside `create_vehicle_blueprint`   |
| 18            | Add vehicle to VehicleFactory blueprint             | `register_vehicle_in_factory` (C++)        |
| 19            | Save all assets                                     | implicit on duplicate_asset / create calls  |

---

## Usage

```bash
# Defaults: clone Mustang template, create Mustang66 vehicle
bash run.sh --close-editor

# Custom vehicle
VEH_MAKE=Toyota VEH_MODEL=Prius bash run.sh --close-editor

# Override result file location
UEPY_RESULT=/tmp/prius_result.txt VEH_MAKE=Toyota VEH_MODEL=Prius bash run.sh

# Skip --close-editor only if no GUI editor is running
VEH_MODEL=Prius bash run.sh
```

Check `scripts/add_vehicle_result.txt` for per-step status and created asset
paths. Look for `ADD_VEHICLE_END` at the bottom to confirm completion.

### Prerequisite check

If the result file contains `STATUS=REBUILD_CARLATOOLS_REQUIRED`, the
CarlaTools UE plugin has not been compiled. Run the build-carla-ue4-linux
skill's CarlaTools build step, then re-run.

### Registration (via the shipped VehicleFactory)

`add_vehicle.py` step `[9]` registers the vehicle by appending an
`FVehicleParameters` to the **shipped `VehicleFactory`** blueprint's reflected
`vehicles` array (this is the tutorial's Step 8), then **force-saves**
(`only_if_is_dirty=False`) because a CDO-default edit doesn't dirty the package
(LESSONS V8). This is the ONLY path that yields a **drivable** vehicle: spawns go
through VehicleFactory's BP `SpawnActor` graph, which does CARLA's deferred spawn
+ `FinishSpawning` and initialises the PhysX WheeledVehicle.

**Do NOT** build a custom `ACarlaActorFactory` — a naive `World->SpawnActor` never
inits the wheeled vehicle, so the car spawns but will not drive (LESSONS V14).
`setup_registration.py` and the `AAuthoredVehicleFactory`/`DT_AuthoredVehicles`
C++ are DEPRECATED (kept for history).

### Verify end-to-end (no cook required)

Registration is only *proven* by a spawn on a running server (LESSONS V9) — an
in-editor read is not enough. You do **not** need `make package`:

```bash
# 1. Launch a headless RPC server from the UNCOOKED project (-nullrhi; ~15-20s).
bash scripts/run_server.sh /Game/Carla/Maps/Town02 2000 > /tmp/carla_server.log 2>&1 &

# 2. Wait for RPC port 2000, then spawn + drive the new vehicle (conda client).
conda activate carla-ue4
VEH_MAKE=Ford VEH_MODEL=TestCar python scripts/spawn_test.py --host 127.0.0.1 --port 2000
#   Default check: hands the car to the Traffic Manager (set_autopilot) and asserts
#   it drives itself (peak velocity >= 1 m/s). On no-motion it falls back to a manual
#   throttle burst to tell "can't drive" (VehicleFactory/registration bug, V14) apart
#   from "TM didn't route it". -> VERDICT PASS.

# 3. Stop the server (do NOT `pkill -f CarlaUE4.uproject` — kills your shell too).
pkill -x UE4Editor
```

`-nullrhi` serves RPC + physics but produces **no sensor images**; for
camera/lidar, cook (`make package`) and run `-RenderOffScreen` on the package.
See build-carla-ue4-linux L17 for why `-RenderOffScreen` on uncooked content
crashes.

### Watch it drive (visual demo)

To *see* the vehicle drive itself, run a **windowed** server and the chase-cam demo:

```bash
WINDOW=1 bash scripts/run_server.sh /Game/Carla/Maps/Town02 2000 >/tmp/carla.log 2>&1 &
# wait for RPC 2000, then:
conda activate carla-ue4
VEH_MAKE=Ford VEH_MODEL=TestCar python scripts/drive_demo.py --port 2000 --secs 240
```

`drive_demo.py` spawns the vehicle, hands it to the Traffic Manager (autopilot),
adds NPC traffic, and keeps a chase camera locked behind it (`ignore_lights` so it
visibly drives rather than idling). The camera only tracks while the script runs —
a short/one-shot loop makes the car appear to "stop" once the process exits.

---

## Env var interface

| Variable           | Default    | Description                                                       |
|--------------------|------------|-------------------------------------------------------------------|
| `VEH_MAKE`         | `Mustang`  | Make label stored in VehicleParameters                            |
| `VEH_MODEL`        | `Mustang66`| Model name; also the asset subfolder under Blueprints/Static      |
| `VEH_TEMPLATE`     | `Mustang`  | Source template to clone (currently only Mustang supported)       |
| `VEH_MODE`         | `synthetic`| `synthetic` duplicates mesh+wheels; others reuse template paths   |
| `VEH_WHEEL_RADIUS` | `35.0`     | Wheel radius (cm) passed to configure_wheel                       |
| `VEH_WHEEL_WIDTH`  | `20.0`     | Wheel width (cm)                                                  |
| `VEH_WHEEL_MASS`   | `20.0`     | Wheel mass (kg)                                                   |
| `VEH_FRONT_STEER`  | `70.0`     | Front wheel max steer angle (degrees)                             |
| `VEH_REAR_STEER`   | `0.0`      | Rear wheel steer angle (degrees, typically 0)                     |
| `UEPY_RESULT`      | (next to script) | Override path for `add_vehicle_result.txt`                  |

---

## C++ UFUNCTION -> Python snake_case binding table

Canonical bindings confirmed by cpp-eng (2026-06-30). All parameters are typed
UE objects. All accessed as `unreal.VehicleAuthoringLibrary.<name>(...)`.

**UE4.26 class-loading rules (confirmed by live runs):**
- The ONLY reliable way to obtain a Blueprint's generated class in UE4.26 Python is by path:
  `unreal.EditorAssetLibrary.load_blueprint_class("/Game/.../BP_Foo")`
  This works for both wheel BPs and for the vehicle BP's class passed to VehicleParameters.
- `.generated_class()` — does NOT exist as a callable; raises `AttributeError`.
- `bp.get_editor_property("generated_class")` — also fails at runtime:
  `Exception: Failed to find property 'generated_class' on 'Blueprint'`.
  Do NOT use either form.

| C++ UFUNCTION              | Python binding                | Returns       | Call step |
|----------------------------|-------------------------------|---------------|-----------|
| `CreateVehicleAnimBP`      | `create_vehicle_anim_bp`      | AnimBlueprint | [5]       |
| `SetupVehiclePhysicsAsset` | `setup_vehicle_physics_asset` | bool          | [6]       |
| `ConfigureWheel`           | `configure_wheel`             | bool          | [7] x4    |
| `CreateVehicleBlueprint`   | `create_vehicle_blueprint`    | Blueprint     | [8]       |
| `RegisterVehicleInFactory` | `register_vehicle_in_factory` | bool*         | [9]       |
| `CompileAndSaveBlueprint`  | `compile_and_save_blueprint`  | bool          | [10]      |

*`register_vehicle_in_factory` returning `False` is NON-FATAL: the shipped
VehicleFactory uses a graph literal (`MakeVehicleDefinitions`), not a stored
array. False is the confirmed expected result; manifest records
`REGISTRATION_UNCONFIRMED`.

---

## Canonical C++ function signatures (cpp-eng, 2026-06-30)

```python
# [5] Duplicate + retarget template anim BP to the new skeleton.
# Returns AnimBlueprint UE object, or raises on failure.
VAL.create_vehicle_anim_bp(
    skeleton,           # unreal.Skeleton object
    template_anim_bp,   # unreal.AnimBlueprint object (source template)
    dest_package_path,  # str: full /Game/... package path
)

# [6] Create / configure physics asset for the duplicated skeletal mesh.
# Returns bool; False treated as fatal.
VAL.setup_vehicle_physics_asset(
    mesh,               # unreal.SkeletalMesh object
    collision_mesh,     # unreal.StaticMesh object (collision proxy), or None
)

# [7] Configure per-wheel properties on each duplicated wheel blueprint class.
# Called BEFORE create_vehicle_blueprint (wheel class configured standalone).
# wheel_class obtained via load_blueprint_class(path) — NOT .generated_class().
# Called positionally; 6th arg name is affected_by_handbrake (UE strips 'b').
# Returns bool; False is logged but non-fatal.
VAL.configure_wheel(
    wheel_class,            # TSubclassOf<UVehicleWheel>
                            # = unreal.EditorAssetLibrary.load_blueprint_class(path)
    radius,                 # float, cm
    width,                  # float, cm
    mass,                   # float, kg
    steer_angle_deg,        # float, degrees (0.0 for rear wheels)
    affected_by_handbrake,  # bool (False for front, True for rear)
    tire_config,            # UTireConfig object or None for default
)

# [8] Assemble the main vehicle blueprint.
# dest_folder_path is the FOLDER; C++ appends the asset name internally.
# wheels = list of 4 TSubclassOf<UVehicleWheel> via load_blueprint_class().
# wheel_bones order must match wheels list [FL, FR, RR, RL].
# Returns Blueprint UE object, or raises on failure.
VAL.create_vehicle_blueprint(
    name,               # str: asset base name, e.g. "BP_TestCar"
    dest_folder_path,   # str: FOLDER /Game/... path (NOT full asset path)
    mesh,               # unreal.SkeletalMesh
    anim,               # unreal.AnimBlueprint asset (C++ derives AnimClass)
    raycast_mesh,       # unreal.StaticMesh SM_sc_ (sensor collision proxy)
    wheels,             # list of 4 TSubclassOf<UVehicleWheel>: [FL, FR, RR, RL]
    wheel_bones,        # list of 4 FName strings, same index order as wheels:
                        #   ["Wheel_Front_Left", "Wheel_Front_Right",
                        #    "Wheel_Rear_Right",  "Wheel_Rear_Left"]
                        #   NOTE: RR before RL to match wheels list order
)

# [9] Append vehicle entry to VehicleFactory. Returns bool (NON-FATAL if False).
# factory_bp is a loaded Blueprint UE object (not a path string).
# VehicleParameters.class: Python reserved word -- use set_editor_property.
# Class value MUST come from load_blueprint_class(new_vehicle_bp_path).
# Do NOT use bp.get_editor_property("generated_class") or .generated_class() --
# both raise exceptions in UE4.26 (confirmed live-run).
vehicle_cls = unreal.EditorAssetLibrary.load_blueprint_class(new_vehicle_bp_path)
params = unreal.VehicleParameters()
params.set_editor_property("make",             make_str)
params.set_editor_property("model",            model_str)
params.set_editor_property("class",            vehicle_cls)
params.set_editor_property("number_of_wheels", 4)
VAL.register_vehicle_in_factory(factory_bp, params)

# [10] Compile blueprint and flush to disk. Returns bool; False is fatal.
# Must be the last call -- an uncompiled blueprint cannot be spawned.
VAL.compile_and_save_blueprint(bp)
```

---

## Template asset paths (Mustang, ue4-dev branch)

All paths confirmed on disk (2026-07-01). See LESSONS P9 — content is under
`Static/Car/4Wheeled/`, not `Static/Vehicles/` as the CARLA docs say.
Two distinct StaticMeshes serve different roles (SM_sc_ vs SMC_ prefix):

```
# Blueprints
/Game/Carla/Blueprints/Vehicles/Mustang/BP_Mustang66
/Game/Carla/Blueprints/Vehicles/Mustang/BP_Mustang_FLW
/Game/Carla/Blueprints/Vehicles/Mustang/BP_Mustang_FRW
/Game/Carla/Blueprints/Vehicles/Mustang/BP_Mustang_RRW
/Game/Carla/Blueprints/Vehicles/Mustang/BP_Mustang_RW
/Game/Carla/Blueprints/Vehicles/VehicleFactory

# Meshes / rig (all under Static/Car/4Wheeled/Mustang/)
/Game/Carla/Static/Car/4Wheeled/Mustang/SM_Mustang_v2          (skeletal mesh)
/Game/Carla/Static/Car/4Wheeled/Mustang/SM_Mustang1966_Skeleton
/Game/Carla/Static/Car/4Wheeled/Mustang/BP_Mustang66_Animation  (anim BP lives here, NOT in Blueprints/Vehicles)
/Game/Carla/Static/Car/4Wheeled/Mustang/SM_sc_Mustang           (raycast/sensor proxy -> create_vehicle_blueprint)
/Game/Carla/Static/Car/4Wheeled/Mustang/SMC_Mustang             (physics-asset collision source -> setup_vehicle_physics_asset)
```
