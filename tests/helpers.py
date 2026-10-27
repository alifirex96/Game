"""Shared setup for the tests: a quiet world and a few places on the map."""
import math
import random
import time
from server import World
from world_data import CAMP_HALF, ROAD_HALF


def quiet_world(seed=1):
    """A world without random wildlife; the infected appear only when a test asks for them."""
    w = World(rng=random.Random(seed))
    w._spawn_creatures = lambda people: None
    w._tick_zones = lambda dt, people: None
    return w


def act(w, token, op, **data):
    data.update(op=op, request_id='r' + str(random.random()))
    return w.command(token, data)


def run(w, seconds, players=()):
    for i in range(int(seconds / .05)):
        now = time.monotonic()
        for p in players:
            p['last_seen'] = p['last_input'] = now
        w.tick(.05)


def open_ground(w):
    """A flat spot outside towns with room for a camp."""
    t = w.towns['kamenka']
    for r in range(900, 6000, 150):
        for k in range(24):
            a = k * math.pi / 12
            x, y = t['x'] + math.cos(a) * r, t['y'] + math.sin(a) * r
            ok = all(not w.terrain.solid(x + dx, y + dy, 8) and not w.terrain.water(x + dx, y + dy, 6)
                     and not w.terrain.on_road(x + dx, y + dy, ROAD_HALF + 10) and not w.terrain.on_street(x + dx, y + dy, 6)
                     for dx in (-CAMP_HALF - 40, 0, CAMP_HALF + 40) for dy in (-CAMP_HALF - 40, 0, CAMP_HALF + 40))
            if ok and not w.terrain.in_town(x, y, 300) and not any(math.hypot(n['x'] - x, n['y'] - y) < 300 for n in w.nodes.values()):
                return x, y
    raise AssertionError('no open ground')
