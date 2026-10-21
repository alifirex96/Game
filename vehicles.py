"""Car physics for player cars: throttle, brakes, steering, grip and drift, surfaces, collisions and ramming.

Mixed into server.World. Runs on the host inside the world lock, once per tick for every driving player.
Units: world pixels and seconds. Input: steer and throttle in -1..1, handbrake on Shift.
"""
import math
from world_data import CARS, CAR_TANK, REGIONS, STARTER_CARS

BRAKE = 520          # px/s² of a full brake
HANDBRAKE = 380
ROLL = 55            # rolling resistance with no throttle
CRASH_SPEED = 150    # impacts faster than this damage the car
RAM_SPEED = 110      # hitting someone faster than this hurts them


class VehicleMixin:
    def car_spec(self, p):
        model = p['car'].get('model', 2)
        return CARS[model if isinstance(model, int) and 0 <= model < len(CARS) else 2]

    def car_tank(self, p):
        return self.car_spec(p)['tank'] if 'model' in p['car'] else CAR_TANK

    def new_car(self, x, y, angle, fuel, model=None):
        model = model if model is not None else self.rng.choice(STARTER_CARS)
        return {'x':x,'y':y,'angle':angle,'hp':100.0,'wrecked_until':0.0,'fuel':fuel,'model':model,
                'vx':0.0,'vy':0.0,'steer':0.0,'brake':False,'slip':False}

    def _car_circles(self, spec, x, y, a):
        """Two circles along the body: enough for buildings, water and other solid things."""
        r = spec['wid'] * .45; off = spec['len'] / 2 - r
        c, s = math.cos(a), math.sin(a)
        return [(x + c * off, y + s * off, r), (x - c * off, y - s * off, r)]

    def _car_blocked(self, spec, x, y, a):
        for cx, cy, r in self._car_circles(spec, x, y, a):
            if self.blocked(cx, cy, r):
                return True
            # Rivers and lakes stop cars; bridges are part of the road.
            if self.terrain.water(cx, cy, 4) and not self.terrain.on_road(cx, cy, 70):
                return True
        return False

    def car_exit_spot(self, p):
        """The driver's door is on the left; then the right side, then behind and in front."""
        car = p['car']; spec = self.car_spec(p); a = car['angle']
        hx, hy = math.cos(a), math.sin(a); lx, ly = hy, -hx
        side = spec['wid'] / 2 + 14; fwd = spec['door'] * spec['len']
        for sx, sy in ((lx * side + hx * fwd, ly * side + hy * fwd), (-lx * side + hx * fwd, -ly * side + hy * fwd),
                       (-hx * (spec['len'] / 2 + 16), -hy * (spec['len'] / 2 + 16)), (hx * (spec['len'] / 2 + 16), hy * (spec['len'] / 2 + 16))):
            x, y = car['x'] + sx, car['y'] + sy
            if not self.blocked(x, y, 11):
                return x, y
        return None

    def drive(self, p, dt, steer, throttle, handbrake, garage):
        car = p['car']; spec = self.car_spec(p)
        x, y, a = car['x'], car['y'], car['angle']
        hx, hy = math.cos(a), math.sin(a); nx, ny = -hy, hx
        vx, vy = car.get('vx', 0.0), car.get('vy', 0.0)
        fwd = vx * hx + vy * hy; lat = vx * nx + vy * ny
        if car.get('fuel', 0) <= .01:
            throttle = 0
        # Surface and weather decide top speed and grip.
        road = self.terrain.on_road(x, y, 60) or self.terrain.in_town(x, y, 0)
        town = min(self.towns.values(), key=lambda t: (t['x'] - x) ** 2 + (t['y'] - y) ** 2)
        snowy_ground = REGIONS[town['region']]['cold'] >= 2
        top = spec['max'] * (1 + .06 * garage) * (1 if road else spec['offroad'])
        grip = spec['grip'] * (1 if road else .85)
        weather = self.weather['kind']
        if weather in ('rain', 'storm'):
            grip *= .75
        if weather == 'snow' or (snowy_ground and not road):
            grip *= .6; top *= .9
        accel = spec['accel'] * (1 + .05 * garage)
        braking = False
        if throttle > 0:
            if fwd < -5:
                fwd = min(0.0, fwd + BRAKE * dt); braking = True
            elif fwd < top:
                fwd = min(top, fwd + accel * throttle * dt * (1 - .55 * max(0.0, fwd) / top))
        elif throttle < 0:
            if fwd > 5:
                fwd = max(0.0, fwd - BRAKE * dt); braking = True
            elif fwd > -top * .35:
                fwd = max(-top * .35, fwd + accel * .6 * throttle * dt)
        else:
            fwd -= math.copysign(min(abs(fwd), ROLL * dt), fwd)
        if fwd > top:      # leaving the asphalt at speed: the field slows the car down
            fwd -= (fwd - top) * min(1, 2.2 * dt)
        if handbrake and abs(fwd) > 1:
            fwd -= math.copysign(min(abs(fwd), HANDBRAKE * dt), fwd); grip = min(grip, 1.4); braking = True
        # Bicycle steering: lock shrinks with speed, the car turns about its rear axle.
        lock = steer * spec['steer'] / (1 + abs(fwd) / 320)
        car['steer'] = car.get('steer', 0.0) + (lock - car.get('steer', 0.0)) * min(1, dt * 7)
        yaw = fwd / (spec['len'] * .62) * math.tan(car['steer'])
        lat *= math.exp(-grip * dt)
        vx = hx * fwd + nx * lat; vy = hy * fwd + ny * lat
        na = a + yaw * dt
        if self._car_blocked(spec, x, y, na):
            na = a
        level = garage
        if car.get('fuel', 0) > .01:
            car['fuel'] = max(0.0, car['fuel'] - dt * (.025 + .16 * abs(throttle) * (.5 + .5 * min(1, abs(fwd) / spec['max']))) * (1 - .1 * level))
        tx, ty = x + vx * dt, y + vy * dt
        speed = math.hypot(vx, vy)
        if self._car_blocked(spec, tx, ty, na):
            # Slide along the obstacle if one axis is free; otherwise stop with a jolt.
            if not self._car_blocked(spec, tx, y, na):
                ty = y; vy *= -.2
            elif not self._car_blocked(spec, x, ty, na):
                tx = x; vx *= -.2
            else:
                tx, ty = x, y; vx *= -.25; vy *= -.25
            self._crash(p, speed, spec)
        car.update(x=tx, y=ty, angle=na, vx=vx, vy=vy, brake=braking, slip=abs(lat) > 70 or (handbrake and abs(fwd) > 80))
        p['x'], p['y'], p['angle'] = tx, ty, na
        if speed > RAM_SPEED:
            self._ram(p, spec, speed)

    def _crash(self, p, speed, spec):
        if speed < CRASH_SPEED or self.elapsed - p['car'].get('crash_at', -10) < .5:
            return
        car = p['car']; car['crash_at'] = self.elapsed
        car['hp'] = max(0.0, car.get('hp', 100) - (speed - CRASH_SPEED) * .12 / spec['armor'])
        self.effects.append({'id':'c%x' % int(self.elapsed * 1000), 'kind':'crash', 'x':car['x'], 'y':car['y'], 'ex':car['x'], 'ey':car['y'],
                             'until':self.elapsed + .5, 'faction':None, 'power':round(min(1, (speed - CRASH_SPEED) / 250), 2)})
        if speed > 230:
            self._damage(p, (speed - 230) * .06)
        if car['hp'] <= 0:
            self._wreck_car(p)

    def _ram(self, p, spec, speed):
        car = p['car']; reach = spec['wid'] * .55 + 12
        for o in self._nearby(car['x'], car['y'], spec['len']):
            if o is p or o.get('vehicle') or o.get('type') == 'convoy' or o['hp'] <= 0:
                continue
            if math.hypot(o['x'] - car['x'], o['y'] - car['y']) > reach:
                continue
            if not self.hostile_shot(p, o) or o.get('rammed_until', 0) > self.elapsed:
                continue
            o['rammed_until'] = self.elapsed + .8
            self.hurt(o, speed * .09, p)
            car['vx'] *= .7; car['vy'] *= .7
