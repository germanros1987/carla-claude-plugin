# Add a new 4-wheeled vehicle to CarlaUE4 by duplicating a Mustang template and
# wiring it up via VehicleAuthoringLibrary (C++ UFUNCTIONs exposed to editor Python).
#
# Runs inside UE4's embedded Python 3.7.7 (PythonScriptPlugin, -nullrhi headless).
# Results are written incrementally to add_vehicle_result.txt so a late engine
# crash keeps partial output (see ue4-editor-python LESSONS P4).
#
# Parameters (env vars):
#   VEH_MAKE     - vehicle make label            (default: Mustang)
#   VEH_MODEL    - vehicle model / asset folder   (default: Mustang66)
#   VEH_TEMPLATE - template vehicle to clone from (default: Mustang)
#   VEH_MODE     - "synthetic" (default): duplicate template assets to new paths
#
# Canonical C++ -> Python snake_case bindings (reconciled from cpp-eng, 2026-06-30):
#   CreateVehicleAnimBP      -> create_vehicle_anim_bp(skeleton, template_anim_bp, dest_package_path)
#                               skeleton and template_anim_bp are loaded UE objects; returns AnimBlueprint
#   SetupVehiclePhysicsAsset -> setup_vehicle_physics_asset(mesh, collision_static_mesh, wheel_radius)
#                               collision_static_mesh = SMC_Mustang (not the SM_sc_ raycast mesh);
#                               wheel_radius (cm) sizes the kinematic wheel spheres;
#                               builds a DEDICATED <mesh>_PhysicsAsset (never mutates the shared
#                               donor PA); returns bool
#   ConfigureWheel           -> configure_wheel(wheel_class, radius, width, mass,
#                                               steer_angle_deg, affected_by_handbrake, tire_config)
#                               wheel_class is bp_asset.generated_class(); called positionally; returns bool
#   CreateVehicleBlueprint   -> create_vehicle_blueprint(name, dest_folder_path, mesh, anim,
#                                                        raycast_mesh, wheels, wheel_bones)
#                               raycast_mesh = SM_sc_Mustang (custom-collision/raycast proxy)
#                               wheels is list of 4 generated classes; returns Blueprint
#   Registration -> step [9] appends FVehicleParameters to the shipped
#                   VehicleFactory's reflected `vehicles` array (tutorial Step 8).
#                   This is the ONLY drivable path; a custom factory does not init
#                   the PhysX wheeled vehicle (LESSONS V14). No C++ UFUNCTION needed.
#   CompileAndSaveBlueprint  -> compile_and_save_blueprint(bp)
#                               bp is the Blueprint UE object from create_vehicle_blueprint; returns bool
#
# NOTE on asset loads: C++ functions require typed UE objects so we call unreal.load_asset()
# before passing. This differs from read-only probing (LESSONS P3) but is unavoidable here.
#
# ascii-only in file writes (UE4.26 embedded py3.7 ascii locale; see LESSONS P8).
import os
import sys
import unreal

# --- result file opened immediately; flushed after every line (crash-proof) ---
RESULT_PATH = os.environ.get(
    "UEPY_RESULT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "add_vehicle_result.txt"),
)
# encoding='utf-8' guards against non-ASCII in asset names (see LESSONS P8).
_f = open(RESULT_PATH, "w", encoding="utf-8")


def emit(s=""):
    _f.write(str(s) + "\n")
    _f.flush()
    unreal.log(str(s))


def emit_step(name, status, detail=""):
    line = "STEP %-48s %s" % (name, status)
    if detail:
        line += "  | " + str(detail)
    emit(line)


def abort(reason, detail=""):
    emit("STATUS=ABORT reason=%s" % reason)
    if detail:
        emit("DETAIL=" + str(detail))
    emit("ADD_VEHICLE_END")
    _f.close()
    sys.exit(1)


emit("ADD_VEHICLE_BEGIN")

# ---------------------------------------------------------------------------
# Guard: VehicleAuthoringLibrary must be compiled into the editor.
# ---------------------------------------------------------------------------
if not hasattr(unreal, "VehicleAuthoringLibrary"):
    emit("STATUS=REBUILD_CARLATOOLS_REQUIRED")
    emit("DETAIL=unreal.VehicleAuthoringLibrary not found in editor bindings.")
    emit("DETAIL=Compile the CarlaTools UE plugin and rebuild CarlaUE4 project.")
    emit("ADD_VEHICLE_END")
    _f.close()
    sys.exit(0)

VAL = unreal.VehicleAuthoringLibrary

# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
VEH_MAKE     = os.environ.get("VEH_MAKE",     "Mustang")
VEH_MODEL    = os.environ.get("VEH_MODEL",    "Mustang66")
VEH_TEMPLATE = os.environ.get("VEH_TEMPLATE", "Mustang")
VEH_MODE     = os.environ.get("VEH_MODE",     "synthetic")

WHEEL_RADIUS = float(os.environ.get("VEH_WHEEL_RADIUS", "35.0"))  # cm
WHEEL_WIDTH  = float(os.environ.get("VEH_WHEEL_WIDTH",  "20.0"))  # cm
WHEEL_MASS   = float(os.environ.get("VEH_WHEEL_MASS",   "20.0"))  # kg
FRONT_STEER  = float(os.environ.get("VEH_FRONT_STEER",  "70.0"))  # degrees
REAR_STEER   = float(os.environ.get("VEH_REAR_STEER",    "0.0"))  # degrees

emit("PARAMS make=%s model=%s template=%s mode=%s" % (
    VEH_MAKE, VEH_MODEL, VEH_TEMPLATE, VEH_MODE))

# ---------------------------------------------------------------------------
# Template asset paths (Mustang, ue4-dev layout -- confirmed on disk).
# LESSONS P9: content lives under Static/Car/4Wheeled/, not Static/Vehicles/.
#
# Two distinct StaticMeshes serve different roles:
#   raycast_mesh   SM_sc_Mustang  -> sensor raycast / custom-collision proxy
#                                    passed to create_vehicle_blueprint
#   collision_mesh SMC_Mustang    -> physics-asset collision source (SMC_ prefix)
#                                    passed to setup_vehicle_physics_asset
#
# anim_bp lives under Static/Car/ (NOT Blueprints/Vehicles/).
# ---------------------------------------------------------------------------
_TMPL_BP   = "/Game/Carla/Blueprints/Vehicles/Mustang"
_TMPL_MESH = "/Game/Carla/Static/Car/4Wheeled/Mustang"

TEMPLATE_ASSETS = {
    "main_bp":        _TMPL_BP   + "/BP_Mustang66",
    "wheel_flw":      _TMPL_BP   + "/BP_Mustang_FLW",
    "wheel_frw":      _TMPL_BP   + "/BP_Mustang_FRW",
    "wheel_rrw":      _TMPL_BP   + "/BP_Mustang_RRW",
    "wheel_rw":       _TMPL_BP   + "/BP_Mustang_RW",
    "skel_mesh":      _TMPL_MESH + "/SM_Mustang_v2",
    "skeleton":       _TMPL_MESH + "/SM_Mustang1966_Skeleton",
    "raycast_mesh":   _TMPL_MESH + "/SM_sc_Mustang",
    "collision_mesh": _TMPL_MESH + "/SMC_Mustang",
    "anim_bp":        _TMPL_MESH + "/BP_Mustang66_Animation",
    "factory":        "/Game/Carla/Blueprints/Vehicles/VehicleFactory",
}

# ---------------------------------------------------------------------------
# [1] Verify all template assets (all paths now confirmed; any MISSING is fatal).
# ---------------------------------------------------------------------------
emit("\n[1] Verifying template assets")
missing = []
for key in sorted(TEMPLATE_ASSETS):
    path = TEMPLATE_ASSETS[key]
    exists = unreal.EditorAssetLibrary.does_asset_exist(path)
    emit("  %-16s %-8s %s" % (key, "OK" if exists else "MISSING", path))
    if not exists:
        missing.append((key, path))

if missing:
    emit("MISSING_COUNT=%d" % len(missing))
    for key, path in missing:
        emit("  MISSING key=%s path=%s" % (key, path))
    abort("MISSING_TEMPLATE_ASSETS")

emit_step("verify_templates", "OK", "%d assets confirmed" % len(TEMPLATE_ASSETS))

# ---------------------------------------------------------------------------
# [2] Destination paths
# ---------------------------------------------------------------------------
DEST_BP   = "/Game/Carla/Blueprints/Vehicles/" + VEH_MODEL
DEST_MESH = "/Game/Carla/Static/Car/4Wheeled/"  + VEH_MODEL

emit("\n[2] Destination paths")
emit("  dest_bp   = " + DEST_BP)
emit("  dest_mesh = " + DEST_MESH)

for d in (DEST_BP, DEST_MESH):
    if not unreal.EditorAssetLibrary.does_directory_exist(d):
        unreal.EditorAssetLibrary.make_directory(d)
        emit("  mkdir: " + d)
    else:
        emit("  exists: " + d)

# ---------------------------------------------------------------------------
# Helper: duplicate one asset; skip (idempotent) if dest already exists.
# ---------------------------------------------------------------------------
def dup(src, dest_dir, asset_name):
    dest = dest_dir + "/" + asset_name
    if unreal.EditorAssetLibrary.does_asset_exist(dest):
        emit("  dup SKIP (exists): " + dest)
        return dest
    ok = unreal.EditorAssetLibrary.duplicate_asset(src, dest)
    # CRITICAL: duplicate_asset creates the asset in memory only. run_python.sh
    # SIGKILLs the editor on --close-editor before it autosaves, so unsaved
    # duplicates are LOST (folder ends up empty on disk). Explicitly flush each
    # duplicate to disk now.
    saved = unreal.EditorAssetLibrary.save_asset(dest) if ok else False
    emit("  dup %-5s save=%-5s %s -> %s" % ("OK" if ok else "FAIL", saved, src, dest))
    return dest

# ---------------------------------------------------------------------------
# [3] Duplicate template assets (synthetic mode).
# Duplicated: skel mesh, SM_sc_ raycast mesh, SMC_ collision mesh, 4 wheel BPs.
# Physics asset is NOT duplicated -- setup_vehicle_physics_asset [6] creates it.
# ---------------------------------------------------------------------------
emit("\n[3] Asset duplication (mode=%s)" % VEH_MODE)

if VEH_MODE == "synthetic":
    new_skel_mesh      = dup(TEMPLATE_ASSETS["skel_mesh"],
                             DEST_MESH, "SM_" + VEH_MODEL)
    new_raycast_mesh   = dup(TEMPLATE_ASSETS["raycast_mesh"],
                             DEST_MESH, "SM_sc_" + VEH_MODEL)
    new_collision_mesh = dup(TEMPLATE_ASSETS["collision_mesh"],
                             DEST_MESH, "SMC_" + VEH_MODEL)
    new_wheel_flw      = dup(TEMPLATE_ASSETS["wheel_flw"], DEST_BP,
                             "BP_" + VEH_MODEL + "_FLW")
    new_wheel_frw      = dup(TEMPLATE_ASSETS["wheel_frw"], DEST_BP,
                             "BP_" + VEH_MODEL + "_FRW")
    new_wheel_rrw      = dup(TEMPLATE_ASSETS["wheel_rrw"], DEST_BP,
                             "BP_" + VEH_MODEL + "_RRW")
    new_wheel_rw       = dup(TEMPLATE_ASSETS["wheel_rw"],  DEST_BP,
                             "BP_" + VEH_MODEL + "_RW")
    emit_step("duplicate_assets", "OK")
else:
    emit("  non-synthetic: reusing template asset paths")
    new_skel_mesh      = TEMPLATE_ASSETS["skel_mesh"]
    new_raycast_mesh   = TEMPLATE_ASSETS["raycast_mesh"]
    new_collision_mesh = TEMPLATE_ASSETS["collision_mesh"]
    new_wheel_flw      = TEMPLATE_ASSETS["wheel_flw"]
    new_wheel_frw      = TEMPLATE_ASSETS["wheel_frw"]
    new_wheel_rrw      = TEMPLATE_ASSETS["wheel_rrw"]
    new_wheel_rw       = TEMPLATE_ASSETS["wheel_rw"]
    emit_step("duplicate_assets", "SKIPPED mode=%s" % VEH_MODE)

# Dest path for the freshly-created anim BP (C++ creates it; we don't duplicate).
new_anim_bp_path = DEST_BP + "/BP_" + VEH_MODEL + "_Animation"

# ---------------------------------------------------------------------------
# [4] Load UE objects (typed references required by C++ functions).
# ---------------------------------------------------------------------------
emit("\n[4] Loading UE objects")


def load(path, label):
    obj = unreal.load_asset(path)
    emit("  load %-6s %-18s %s" % ("OK" if obj else "FAIL", label, path))
    return obj


mesh_obj       = load(new_skel_mesh,               "skel_mesh")
skeleton_obj   = load(TEMPLATE_ASSETS["skeleton"],  "skeleton")
tmpl_anim_obj  = load(TEMPLATE_ASSETS["anim_bp"],   "tmpl_anim_bp")
raycast_obj    = load(new_raycast_mesh,             "raycast_mesh")
collision_obj  = load(new_collision_mesh,           "collision_mesh")
factory_obj    = load(TEMPLATE_ASSETS["factory"],   "factory")
# Template vehicle BP — duplicated INTERNALLY by create_vehicle_blueprint so the
# new BP inherits the template's already-serialised native-component override
# slots (Mesh.SkeletalMesh etc.). Do NOT pre-duplicate it.
template_bp_obj = load(TEMPLATE_ASSETS["main_bp"],  "template_bp")

if not mesh_obj:
    abort("LOAD_FAILED_SKEL_MESH", new_skel_mesh)
if not skeleton_obj:
    abort("LOAD_FAILED_SKELETON", TEMPLATE_ASSETS["skeleton"])
if not tmpl_anim_obj:
    abort("LOAD_FAILED_TMPL_ANIM_BP", TEMPLATE_ASSETS["anim_bp"])
if not raycast_obj:
    abort("LOAD_FAILED_RAYCAST_MESH", new_raycast_mesh)
if not collision_obj:
    abort("LOAD_FAILED_COLLISION_MESH", new_collision_mesh)
if not factory_obj:
    abort("LOAD_FAILED_FACTORY", TEMPLATE_ASSETS["factory"])

# Wheel generated classes as TSubclassOf<UVehicleWheel>. UE4.26 has NO
# Blueprint.generated_class() method; EditorAssetLibrary.load_blueprint_class
# returns the generated class directly from the asset path.
def load_wheel_class(path, label):
    cls = unreal.EditorAssetLibrary.load_blueprint_class(path)
    emit("  wheel_class %-6s %-10s %s" % ("OK" if cls else "FAIL", label, path))
    return cls


wheel_fl_cls = load_wheel_class(new_wheel_flw, "FL")
wheel_fr_cls = load_wheel_class(new_wheel_frw, "FR")
wheel_rr_cls = load_wheel_class(new_wheel_rrw, "RR")
wheel_rl_cls = load_wheel_class(new_wheel_rw,  "RL")

if not all([wheel_fl_cls, wheel_fr_cls, wheel_rr_cls, wheel_rl_cls]):
    abort("LOAD_FAILED_WHEEL_CLASS",
          "one or more wheel blueprint classes failed to load")

emit_step("load_objects", "OK")

# ---------------------------------------------------------------------------
# [5] CreateVehicleAnimBP
# create_vehicle_anim_bp(skeleton, template_anim_bp, dest_package_path)
# Returns the created AnimBlueprint UE object.
# ---------------------------------------------------------------------------
emit("\n[5] CreateVehicleAnimBP")
new_anim_bp_obj = None
try:
    new_anim_bp_obj = VAL.create_vehicle_anim_bp(
        skeleton_obj,      # skeleton the new anim BP will target
        tmpl_anim_obj,     # template anim BP to duplicate from
        new_anim_bp_path,  # destination package path (string)
    )
    emit_step("create_vehicle_anim_bp", "OK", str(new_anim_bp_obj))
except Exception as e:
    emit_step("create_vehicle_anim_bp", "FAIL", repr(e))
    abort("ANIM_BP_FAILED", repr(e))

if not new_anim_bp_obj:
    abort("ANIM_BP_RETURNED_NONE",
          "create_vehicle_anim_bp returned None without raising; "
          "cpp-eng: UFUNCTION must return the created AnimBlueprint or raise.")

# ---------------------------------------------------------------------------
# [6] SetupVehiclePhysicsAsset
# setup_vehicle_physics_asset(mesh, collision_static_mesh)
# collision_static_mesh = SMC_Mustang (SMC_ prefix, not the SM_sc_ raycast mesh).
# Returns bool; False is fatal.
# ---------------------------------------------------------------------------
emit("\n[6] SetupVehiclePhysicsAsset")
# Wheel sphere-body radius (cm) = the SAME WHEEL_RADIUS applied to the wheel BPs in
# step [7], so the kinematic collision sphere matches the final wheel size. (Do NOT
# read it from the wheel CDO here: [6] runs BEFORE configure_wheel [7], so the CDO
# still holds the cloned template's radius, not the target.)
wheel_radius = WHEEL_RADIUS
emit("  wheel_radius (= WHEEL_RADIUS, applied to wheels in [7]) = %.1f cm" % wheel_radius)
try:
    ok = VAL.setup_vehicle_physics_asset(mesh_obj, collision_obj, wheel_radius)
    emit_step("setup_vehicle_physics_asset", "OK" if ok else "FAIL",
              "returned %s" % ok)
    if not ok:
        abort("SETUP_PHYSICS_ASSET_RETURNED_FALSE",
              "cpp-eng: verify physics asset was created for %s" % new_skel_mesh)
except Exception as e:
    emit_step("setup_vehicle_physics_asset", "FAIL", repr(e))
    abort("SETUP_PHYSICS_ASSET_FAILED", repr(e))

# ---------------------------------------------------------------------------
# [7] ConfigureWheel x4 (called positionally; affected_by_handbrake = 6th arg).
# Failures are logged but non-fatal.
# ---------------------------------------------------------------------------
emit("\n[7] ConfigureWheel (x4)")
_wheel_configs = [
    (wheel_fl_cls, WHEEL_RADIUS, WHEEL_WIDTH, WHEEL_MASS, FRONT_STEER, False, "FL"),
    (wheel_fr_cls, WHEEL_RADIUS, WHEEL_WIDTH, WHEEL_MASS, FRONT_STEER, False, "FR"),
    (wheel_rr_cls, WHEEL_RADIUS, WHEEL_WIDTH, WHEEL_MASS, REAR_STEER,  True,  "RR"),
    (wheel_rl_cls, WHEEL_RADIUS, WHEEL_WIDTH, WHEEL_MASS, REAR_STEER,  True,  "RL"),
]
for wheel_cls, radius, width, mass, steer, handbrake, label in _wheel_configs:
    try:
        ok = VAL.configure_wheel(wheel_cls, radius, width, mass, steer, handbrake, None)
        emit_step("configure_wheel[%s]" % label, "OK" if ok else "WARN(False)",
                  "r=%.0f w=%.0f m=%.0f steer=%.0f hb=%s" % (
                      radius, width, mass, steer, handbrake))
    except Exception as e:
        emit_step("configure_wheel[%s]" % label, "FAIL", repr(e))

# ---------------------------------------------------------------------------
# [8] CreateVehicleBlueprint
# create_vehicle_blueprint(name, dest_folder_path, mesh, anim, raycast_mesh,
#                          wheels, wheel_bones)
#   dest_folder_path  FOLDER path; C++ appends the asset name internally
#   anim              AnimBlueprint asset object (C++ derives AnimClass)
#   raycast_mesh      SM_sc_Mustang (sensor collision proxy)
#   wheels            list of 4 generated classes [FL, FR, RR, RL]
#   wheel_bones       list of 4 FName strings, same index order as wheels
# Returns Blueprint UE object.
# ---------------------------------------------------------------------------
emit("\n[8] CreateVehicleBlueprint")

# Order MUST match the wheels list [FL, FR, RR, RL] so each wheel class binds to
# its correct bone (index 2 = RR, index 3 = RL).
WHEEL_BONES = [
    "Wheel_Front_Left",
    "Wheel_Front_Right",
    "Wheel_Rear_Right",
    "Wheel_Rear_Left",
]
bp_asset_name = "BP_" + VEH_MODEL

created_bp_obj = None
try:
    created_bp_obj = VAL.create_vehicle_blueprint(
        bp_asset_name,
        DEST_BP,            # dest FOLDER; C++ appends name
        template_bp_obj,    # template to duplicate (inherits proven CDO slots)
        mesh_obj,
        new_anim_bp_obj,
        raycast_obj,        # SM_sc_ raycast proxy (not the SMC_ physics one)
        [wheel_fl_cls, wheel_fr_cls, wheel_rr_cls, wheel_rl_cls],
        WHEEL_BONES,
    )
    emit_step("create_vehicle_blueprint", "OK", str(created_bp_obj))
except Exception as e:
    emit_step("create_vehicle_blueprint", "FAIL", repr(e))
    abort("BLUEPRINT_FAILED", repr(e))

if not created_bp_obj:
    abort("BLUEPRINT_RETURNED_NONE",
          "create_vehicle_blueprint returned None without raising; "
          "cpp-eng: UFUNCTION must return the created Blueprint or raise.")

# ---------------------------------------------------------------------------
# [8b] Repoint the skeletal mesh via the EDITOR-FAITHFUL Python path.
# The C++ raw UPackage::SavePackage does NOT serialise an inherited NATIVE
# component's SkeletalMesh override to disk (value is correct in-memory but a
# fresh load reads None). set_editor_property on the CDO's Mesh component +
# EditorAssetLibrary.save_loaded_asset IS the details-panel edit+save flow that
# demonstrably persists (verified experiment). So C++ builds the duplicate +
# anim + wheels; Python sets the mesh.
# ---------------------------------------------------------------------------
new_vehicle_bp_path = DEST_BP + "/" + bp_asset_name
emit("\n[8b] Repoint skeletal mesh (editor-faithful path)")
try:
    _cls = unreal.EditorAssetLibrary.load_blueprint_class(new_vehicle_bp_path)
    _cdo = unreal.get_default_object(_cls) if _cls else None
    _mc = _cdo.get_editor_property("mesh") if _cdo else None
    if _mc is None:
        emit_step("set_skeletal_mesh", "FAIL", "could not resolve CDO Mesh component")
        abort("MESH_COMPONENT_NONE")
    _mc.set_editor_property("skeletal_mesh", mesh_obj)
    saved = unreal.EditorAssetLibrary.save_loaded_asset(created_bp_obj)
    after = _mc.get_editor_property("skeletal_mesh")
    emit_step("set_skeletal_mesh", "OK" if (saved and after) else "FAIL",
              "skeletal_mesh=%s saved=%s" % (after, saved))
    if not (saved and after):
        abort("SET_SKELETAL_MESH_FAILED")
except Exception as e:
    emit_step("set_skeletal_mesh", "FAIL", repr(e))
    abort("SET_SKELETAL_MESH_EXCEPTION", repr(e))

# ---------------------------------------------------------------------------
# [9] Register in the shipped VehicleFactory (the ONLY drivable path).
# Append an FVehicleParameters to VehicleFactory's `vehicles` array so the
# vehicle spawns through VehicleFactory's BP SpawnActor graph — which does
# CARLA's correct deferred-spawn + FinishSpawning that initialises the PhysX
# WheeledVehicle. A custom ACarlaActorFactory that naively World->SpawnActor()s
# the class produces a vehicle that spawns but WILL NOT DRIVE (0 m/s under full
# throttle) — see LESSONS V14. `vehicles` IS a reflected CDO array (V3 was
# wrong). Force-save because a CDO-default edit doesn't dirty the package (V8).
# ---------------------------------------------------------------------------
VF_PATH = "/Game/Carla/Blueprints/Vehicles/VehicleFactory"
emit("\n[9] Register in shipped VehicleFactory (drivable path)")
try:
    vf_cls = unreal.EditorAssetLibrary.load_blueprint_class(VF_PATH)
    vf_cdo = unreal.get_default_object(vf_cls) if vf_cls else None
    tc_cls = unreal.EditorAssetLibrary.load_blueprint_class(new_vehicle_bp_path)
    if vf_cdo is None or tc_cls is None:
        emit_step("register_in_vehicle_factory", "FAIL",
                  "could not load VehicleFactory CDO or vehicle class")
    else:
        vehicles = vf_cdo.get_editor_property("vehicles")
        key = "%s/%s" % (VEH_MAKE, VEH_MODEL)
        have = ["%s/%s" % (v.get_editor_property("make"), v.get_editor_property("model"))
                for v in vehicles]
        if key in have:
            emit_step("register_in_vehicle_factory", "OK(EXISTS)",
                      "%s already in VehicleFactory" % key)
        else:
            p = unreal.VehicleParameters()
            p.set_editor_property("make", VEH_MAKE)
            p.set_editor_property("model", VEH_MODEL)
            p.set_editor_property("class_", tc_cls)
            p.set_editor_property("base_type", "car")
            p.set_editor_property("number_of_wheels", 4)
            p.set_editor_property("generation", 2)
            vehicles.append(p)
            vf_cdo.set_editor_property("vehicles", vehicles)
            try:
                vf_cdo.modify()
            except Exception:
                pass
            saved = unreal.EditorAssetLibrary.save_asset(VF_PATH, only_if_is_dirty=False)
            emit_step("register_in_vehicle_factory", "OK",
                      "appended %s -> spawnable vehicle.%s.%s (VehicleFactory now %d; save=%s)" % (
                          key, VEH_MAKE.lower(), VEH_MODEL.lower(),
                          len(vf_cdo.get_editor_property("vehicles")), saved))
except Exception as e:
    emit_step("register_in_vehicle_factory", "FAIL", repr(e))
    emit("  WARN: registration failed; vehicle assets were still created above")

# ---------------------------------------------------------------------------
# [10] (intentionally NO extra compile here.) CreateVehicleBlueprint already
# compiled + saved the BP, and as its FINAL step set SkeletalMesh/AnimClass on
# the native Mesh component's CDO and saved WITHOUT recompiling. A second
# CompileBlueprint here reconstructs the CDO and DROPS the native-component
# SkeletalMesh delta (verified: it reverts Mesh.skeletal_mesh to None). So we
# skip it -- the BP is already persisted.
# ---------------------------------------------------------------------------
emit("\n[10] CompileAndSaveBlueprint -- skipped (CreateVehicleBlueprint already")
emit("     compiled+saved; re-compiling would drop the native Mesh skeletal-mesh).")
emit_step("compile_and_save_blueprint", "SKIPPED", "BP already compiled+saved by step [8]")

# ---------------------------------------------------------------------------
# Final manifest
# ---------------------------------------------------------------------------
emit("\n[MANIFEST]")
emit("make              = " + VEH_MAKE)
emit("model             = " + VEH_MODEL)
emit("vehicle_blueprint = " + str(created_bp_obj))
emit("anim_bp           = " + str(new_anim_bp_obj))
emit("skel_mesh         = " + new_skel_mesh)
emit("raycast_mesh      = " + new_raycast_mesh)
emit("collision_mesh    = " + new_collision_mesh)
emit("wheel_fl          = " + new_wheel_flw)
emit("wheel_fr          = " + new_wheel_frw)
emit("wheel_rr          = " + new_wheel_rrw)
emit("wheel_rl          = " + new_wheel_rw)
emit("factory           = " + TEMPLATE_ASSETS["factory"])
emit("result_file       = " + RESULT_PATH)

emit("\nADD_VEHICLE_END")
_f.close()
