# Conda-side CARLA spawn test for a newly-registered vehicle.
# Python 3.10, `import carla` (CARLA RPC client) — NOT UE editor Python.
# Verifies that a vehicle added via add_vehicle.py actually appears in the
# blueprint library and spawns/moves correctly in a running CARLA server.
#
# Usage:
#   python3 spawn_test.py [--host HOST] [--port PORT] [--filter FILTER]
#
# Env vars (used when --filter is not given):
#   VEH_MAKE   - vehicle make  (default: Mustang)  -> lower-cased for blueprint id
#   VEH_MODEL  - vehicle model (default: Mustang66) -> lower-cased for blueprint id
#   Blueprint id built as: vehicle.<make_lower>.<model_lower>
#
# Explicit override:
#   --filter   - exact blueprint id or glob pattern (e.g. "vehicle.ford.mustang")
#
# Writes: spawn_test_result.txt (ascii) next to this script (or SPAWN_RESULT env).
# Exit codes: 0 = PASS, 1 = FAIL.
import argparse
import os
import sys
import time

import carla  # unresolved in plain python3 — py_compile still passes (syntax only)

# ---------------------------------------------------------------------------
# Result file (ascii; written throughout for crash-proofing)
# ---------------------------------------------------------------------------
RESULT_PATH = os.environ.get(
    "SPAWN_RESULT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "spawn_test_result.txt"),
)
_f = open(RESULT_PATH, "w")


def emit(s=""):
    line = str(s)
    _f.write(line + "\n")
    _f.flush()
    print(line)


def fail(reason):
    emit("VERDICT FAIL  " + reason)
    emit("SPAWN_TEST_END")
    _f.close()
    sys.exit(1)


def done():
    emit("VERDICT PASS")
    emit("SPAWN_TEST_END")
    _f.close()
    sys.exit(0)


# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
ap = argparse.ArgumentParser(description="CARLA vehicle spawn/move verification")
ap.add_argument("--host",   default=os.environ.get("CARLA_HOST", "127.0.0.1"))
ap.add_argument("--port",   default=int(os.environ.get("CARLA_PORT", "2000")), type=int)
ap.add_argument("--filter", default=None,
                help="Blueprint id or glob (overrides VEH_MAKE/VEH_MODEL)")
args = ap.parse_args()

veh_make  = os.environ.get("VEH_MAKE",  "Mustang")
veh_model = os.environ.get("VEH_MODEL", "Mustang66")

# CARLA blueprint ids are lower-cased: vehicle.<make>.<model>
bp_filter = args.filter or ("vehicle.%s.%s" % (veh_make.lower(), veh_model.lower()))

emit("SPAWN_TEST_BEGIN")
emit("host=%s port=%d filter=%s" % (args.host, args.port, bp_filter))

# ---------------------------------------------------------------------------
# Connect
# ---------------------------------------------------------------------------
emit("\n[1] Connecting to CARLA server")
try:
    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)
    world = client.get_world()
    emit("  server version: " + client.get_server_version())
    emit("  client version: " + client.get_client_version())
    emit("  map: " + world.get_map().name)
except Exception as e:
    fail("CONNECTION_ERROR %r" % e)

# ---------------------------------------------------------------------------
# Find blueprint
# ---------------------------------------------------------------------------
emit("\n[2] Looking up blueprint: %s" % bp_filter)
bpl = world.get_blueprint_library()

# Try exact id first, then filter glob.
# NOTE: bpl.find() RAISES IndexError when the id is absent (it does NOT return
# None) — so guard it, or a missing vehicle aborts with a traceback instead of
# the diagnostic "available blueprints" listing below.
bp = None
if not any(c in bp_filter for c in ("*", "?")):
    try:
        bp = bpl.find(bp_filter)
    except (IndexError, RuntimeError):
        bp = None
if bp is None:
    matches = list(bpl.filter(bp_filter))
    if matches:
        bp = matches[0]
        emit("  matched via filter: %s" % bp.id)
    else:
        # Key assertion: if the vehicle isn't here, registration failed.
        emit("  BLUEPRINT NOT FOUND: %s" % bp_filter)
        emit("  Available vehicle.* blueprints:")
        for b in sorted(bpl.filter("vehicle.*"), key=lambda b: b.id):
            emit("    " + b.id)
        fail("BLUEPRINT_NOT_REGISTERED filter=%s" % bp_filter)
else:
    emit("  found: %s" % bp.id)

# IMPORTANT: do NOT set sticky_control=false. With it disabled the vehicle ignores
# apply_control entirely (verified: 0.00 m/s vs 17.8 m/s with the default), even if
# you re-apply every tick. Leave sticky_control at its default (true) so manual
# throttle is held across ticks. (This once masked a perfectly drivable car as a
# "did not move" failure.)

# ---------------------------------------------------------------------------
# Clean up leftover vehicles (V12): a car spawned on top of an existing actor is
# ejected/wedged by PhysX and reads ~0 m/s — a FALSE "did not move". Destroy any
# vehicles left from a prior run so the spawn point is clear.
# ---------------------------------------------------------------------------
emit("\n[3a] Clearing leftover vehicles")
_left = world.get_actors().filter("vehicle.*")
_n = 0
for _a in _left:
    try:
        _a.destroy(); _n += 1
    except Exception:
        pass
emit("  destroyed %d leftover vehicle(s)" % _n)

# ---------------------------------------------------------------------------
# Pick spawn point
# ---------------------------------------------------------------------------
emit("\n[3] Selecting spawn point")
spawn_points = world.get_map().get_spawn_points()
if not spawn_points:
    fail("NO_SPAWN_POINTS map has no recommended spawn transforms")
spawn_tf = spawn_points[0]
emit("  using spawn point 0: x=%.1f y=%.1f z=%.1f" % (
    spawn_tf.location.x, spawn_tf.location.y, spawn_tf.location.z))

# ---------------------------------------------------------------------------
# Spawn, drive, verify movement, destroy
# ---------------------------------------------------------------------------
actor = None
try:
    emit("\n[4] Spawning actor")
    actor = world.spawn_actor(bp, spawn_tf)
    if actor is None:
        fail("SPAWN_RETURNED_NONE blueprint=%s" % bp.id)
    emit("  actor id=%d type=%s" % (actor.id, actor.type_id))

    # Let the spawn transform propagate before sampling. IMPORTANT: get_location()
    # immediately after spawn returns ~(0,0,0) (transform not yet replicated), so a
    # displacement computed against it measures the spawn point's distance from the
    # world origin — NOT motion. That artifact once masked a car that never moved as
    # a "142 m PASS". Settle first, then rely on VELOCITY, not displacement. (V12)
    time.sleep(0.5)
    loc0 = actor.get_location()
    emit("  loc0 (settled): x=%.3f y=%.3f z=%.3f" % (loc0.x, loc0.y, loc0.z))
    if loc0.z < -50.0:
        fail("ACTOR_SUNK_ON_SPAWN z=%.3f" % loc0.z)

    emit("\n[5] Driving under AUTOPILOT / Traffic Manager (default test)")
    # The real integration check: hand the vehicle to the Traffic Manager and confirm
    # it actually drives itself. This exercises the full stack (registration + PhysX
    # wheeled-vehicle init + TM control), which is what production spawns use.
    # Metric is peak VELOCITY (not displacement — that has a spawn-origin artifact,
    # V12). sticky_control is left at its default (=true); disabling it makes the
    # vehicle ignore control entirely (V15).
    SPEED_MIN = 1.0     # m/s; a TM-driven car clears this within a few seconds
    OBSERVE_S = 20.0    # generous window (TM may pause at a light before pulling off)
    tm = client.get_trafficmanager()
    actor.set_autopilot(True, tm.get_port())
    used_autopilot = True
    emit("  autopilot ON via Traffic Manager (port %d); observing up to %.0fs" % (
        tm.get_port(), OBSERVE_S))

    peak_speed = 0.0
    t_start = time.time()
    while time.time() - t_start < OBSERVE_S:
        time.sleep(0.2)
        vel = actor.get_velocity()
        s = (vel.x * vel.x + vel.y * vel.y + vel.z * vel.z) ** 0.5
        if s > peak_speed:
            peak_speed = s
        if peak_speed >= SPEED_MIN:      # clearly moving — no need to wait longer
            break

    loc1 = actor.get_location()
    dx, dy, dz = loc1.x - loc0.x, loc1.y - loc0.y, loc1.z - loc0.z
    dist = (dx * dx + dy * dy + dz * dz) ** 0.5
    emit("  loc1: x=%.3f y=%.3f z=%.3f" % (loc1.x, loc1.y, loc1.z))
    emit("  peak_speed(autopilot): %.3f m/s   displacement: %.3f m" % (peak_speed, dist))

    emit("\n[6] Movement assertion (autopilot/TM, velocity-based)")
    if peak_speed >= SPEED_MIN:
        emit("  OK: vehicle drove itself under Traffic Manager "
             "(peak %.3f m/s, moved %.3f m)" % (peak_speed, dist))
    else:
        # Diagnostic fallback: did the car fail to DRIVE, or did the TM just not route
        # it (e.g. stuck at a light)? A manual full-throttle burst tells them apart.
        emit("  autopilot showed no motion; probing with manual throttle to diagnose")
        actor.set_autopilot(False, tm.get_port())
        manual_peak = 0.0
        for _ in range(15):
            actor.apply_control(carla.VehicleControl(throttle=1.0, steer=0.0,
                                                     brake=0.0, hand_brake=False))
            time.sleep(0.2)
            vel = actor.get_velocity()
            s = (vel.x * vel.x + vel.y * vel.y + vel.z * vel.z) ** 0.5
            if s > manual_peak:
                manual_peak = s
        emit("  manual-throttle peak: %.3f m/s" % manual_peak)
        if manual_peak >= SPEED_MIN:
            fail("AUTOPILOT_NO_MOTION but manual throttle moved it (%.3f m/s) — "
                 "vehicle drivetrain OK; Traffic Manager did not route it "
                 "(re-run; possibly stuck at a light/yield at this spawn)" % manual_peak)
        else:
            fail("VEHICLE_DID_NOT_MOVE autopilot peak=%.3f manual peak=%.3f m/s — "
                 "spawns but no wheel drive; check registration went through the "
                 "shipped VehicleFactory (LESSONS V14), not a custom factory"
                 % (peak_speed, manual_peak))

finally:
    if actor is not None:
        emit("\n[7] Destroying actor id=%d" % actor.id)
        actor.destroy()
        emit("  destroyed OK")

# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
emit("\n[MANIFEST]")
emit("blueprint  = " + bp.id)
emit("actor_id   = " + str(actor.id if actor else "N/A"))
emit("loc0       = %.3f %.3f %.3f" % (loc0.x, loc0.y, loc0.z))
emit("loc1       = %.3f %.3f %.3f" % (loc1.x, loc1.y, loc1.z))
emit("moved_m    = %.3f" % dist)
emit("result     = " + RESULT_PATH)

done()
