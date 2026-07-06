# Visual demo / manual verification: spawn the authored vehicle, hand it to the
# Traffic Manager (autopilot), and keep a chase camera locked behind it while it
# drives through NPC traffic. Meant to be watched in a WINDOWED server
# (WINDOW=1 run_server.sh) on $DISPLAY. Conda client (import carla), NOT UE python.
#
# Usage:
#   conda activate carla-ue4
#   VEH_MAKE=Ford VEH_MODEL=TestCar python drive_demo.py [--port 2000] [--secs 240]
#
# Env / flags:
#   VEH_MAKE / VEH_MODEL  -> vehicle.<make>.<model> to drive (default Ford/TestCar)
#   --port                -> RPC port (default 2000)
#   --secs                -> chase-cam duration (default 240); car stays on autopilot
#   --npc                 -> number of NPC traffic vehicles (default 15)
#
# Notes:
#   * Leaves sticky_control at default — disabling it makes the car ignore control (V15).
#   * ignore_lights_percentage(100) so the hero visibly drives instead of idling at reds.
#   * Destroys leftover vehicles first (V12) so nothing blocks the spawn point.
import argparse
import math
import os
import random
import time

import carla

ap = argparse.ArgumentParser(description="CARLA autopilot chase-cam demo")
ap.add_argument("--host", default=os.environ.get("CARLA_HOST", "127.0.0.1"))
ap.add_argument("--port", type=int, default=int(os.environ.get("CARLA_PORT", "2000")))
ap.add_argument("--secs", type=float, default=240.0)
ap.add_argument("--npc", type=int, default=15)
args = ap.parse_args()

make = os.environ.get("VEH_MAKE", "Ford")
model = os.environ.get("VEH_MODEL", "TestCar")
hero_id = "vehicle.%s.%s" % (make.lower(), model.lower())

client = carla.Client(args.host, args.port)
client.set_timeout(10.0)
world = client.get_world()
bpl = world.get_blueprint_library()
tm = client.get_trafficmanager()

# Clear the map (V12: a car spawned on a leftover gets ejected / blocks the point).
for a in world.get_actors().filter("vehicle.*"):
    try:
        a.destroy()
    except Exception:
        pass
time.sleep(0.5)

spawn_points = world.get_map().get_spawn_points()
hero = world.spawn_actor(bpl.find(hero_id), spawn_points[0])
time.sleep(0.3)
hero.set_autopilot(True, tm.get_port())
tm.ignore_lights_percentage(hero, 100)
tm.vehicle_percentage_speed_difference(hero, -30)  # a touch faster than the limit

# Fill the scene with NPC traffic (4-wheelers only).
npc_bps = [b for b in bpl.filter("vehicle.*")
           if int(b.get_attribute("number_of_wheels")) == 4]
spawned = 0
for tf in spawn_points[1:1 + args.npc]:
    v = world.try_spawn_actor(random.choice(npc_bps), tf)  # noqa: S311 (not crypto)
    if v:
        v.set_autopilot(True, tm.get_port())
        spawned += 1
print("hero %s id=%d on autopilot; %d NPC cars" % (hero_id, hero.id, spawned), flush=True)

spec = world.get_spectator()
t0 = time.time()
while time.time() - t0 < args.secs:
    tr = hero.get_transform()
    loc, yaw = tr.location, math.radians(tr.rotation.yaw)
    spec.set_transform(carla.Transform(
        carla.Location(x=loc.x - 8 * math.cos(yaw), y=loc.y - 8 * math.sin(yaw), z=loc.z + 3.5),
        carla.Rotation(pitch=-14, yaw=tr.rotation.yaw)))
    vel = hero.get_velocity()
    spd = (vel.x * vel.x + vel.y * vel.y + vel.z * vel.z) ** 0.5
    print("t=%3ds  speed=%5.1f km/h  loc=(%.0f,%.0f)" % (
        time.time() - t0, spd * 3.6, loc.x, loc.y), flush=True)
    time.sleep(1.0)
print("chase-cam ended; hero still on autopilot", flush=True)
