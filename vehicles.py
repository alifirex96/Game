"""Cars standing in the world: physics, seats, fuel, wrecks and replacements.

Mixed into server.World. Runs on the host inside the world lock. A car belongs to nobody: whoever sits at the
wheel drives it, others ride along while seats last. A burnt-out car is replaced elsewhere after CAR_RESPAWN.
Units: world pixels and seconds. Input: steer and throttle in -1..1, handbrake on Shift.
"""
import math
import secrets
from world_data import CARS, REGIONS, ROAD_HALF, WORLD_CARS, CAR_RESPAWN

BRAKE = 520          # px/s² of a full brake
HANDBRAKE = 380
ROLL = 55            # rolling resistance with no throttle
CRASH_SPEED = 150    # impacts faster than this damage the car
RAM_SPEED = 110      # hitting someone faster than this hurts them
WRECK_TIME = 300     # a burnt car stays on the spot this long before it is towed away by nobody


class VehicleMixin:
    def car_spec(self, car):
        model = car.get('model', 2)
        return CARS[model if isinstance(model, int) and 0 <= model < len(CARS) else 2]

    def new_car(self, x, y, angle, model=None):
        model = model if model is not None else self.rng.randrange(len(CARS))
        tank = CARS[model]['tank']
        cid = 'car' + secrets.token_hex(4)
        # Found cars are rarely in good shape: a little fuel, a few dents.
        car = {'id':cid, 'x':round(x, 1), 'y':round(y, 1), 'angle':angle, 'model':model,
               'hp':float(self.rng.randint(45, 100)), 'fuel':round(tank * self.rng.uniform(0, .45), 1),
               'vx':0.0, 'vy':0.0, 'steer':0.0, 'brake':False, 'slip':False, 'wrecked_at':None}
        self.cars[cid] = car
        return car

    def _car_circles(self, spec, x, y, a):
        """Two circles along the body: enough for buildings, water and other solid things."""
        r = spec['wid'] * .45; off = spec['len'] / 2 - r
        c, s = math.cos(a), math.sin(a)
        return [(x + c * off, y + s * off, r), (x - c * off, y - s * off, r)]

    def _car_blocked(self, spec, x, y, a, faction=None, skip=None):
        for cx, cy, r in self._car_circles(spec, x, y, a):
            if self.blocked(cx, cy, r, faction):
                return True
            # Rivers, lakes and the sea stop cars; bridges are part of the road.
            if self.terrain.water(cx, cy, 4) and not self.terrain.on_road(cx, cy, ROAD_HALF + 10) and not self.terrain.on_street(cx, cy, 10):
                return True
            for other in self.cars.values():
                if other is skip or abs(other['x'] - cx) > 140 or abs(other['y'] - cy) > 140:
                    continue
                for ox, oy, orad in self._car_circles(self.car_spec(other), other['x'], other['y'], other['angle']):
                    if (ox - cx) ** 2 + (oy - cy) ** 2 < (orad + r) ** 2:
                        return True
        return False

    # ---- placing cars in the world -----------------------------------------
    def _car_place(self):
        """A parking spot: the side of a highway or a town street, never inside walls or water."""
        for attempt in range(40):
            if self.rng.random() < .55 and self.terrain.streets:
                x1, y1, x2, y2, width = self.rng.choice(self.terrain.streets)[:5]
                k = self.rng.uniform(.1, .9); x, y = x1 + (x2 - x1) * k, y1 + (y2 - y1) * k
                angle = math.atan2(y2 - y1, x2 - x1); side = width * .32
            else:
                ax, ay, bx, by = self.rng.choice(self.terrain.road_segments)[:4]
                k = self.rng.uniform(.05, .95); x, y = ax + (bx - ax) * k, ay + (by - ay) * k
                angle = math.atan2(by - ay, bx - ax); side = ROAD_HALF * .75
            sign = 1 if self.rng.random() < .5 else -1
            x += -math.sin(angle) * side * sign; y += math.cos(angle) * side * sign
            if self.rng.random() < .5:
                angle += math.pi
            spec = CARS[0]
            if self._car_blocked(spec, x, y, angle) or any(abs(o['x'] - x) < 1500 and abs(o['y'] - y) < 1500 for o in self.cars.values()):
                continue
            if any(abs(p['x'] - x) < 700 and abs(p['y'] - y) < 700 for p in self.players.values()):
                continue
            return x, y, angle
        return None

    def fill_cars(self):
        """Keep WORLD_CARS cars in the region: replace the ones that burnt out long ago."""
        for cid in [k for k, c in self.cars.items() if c['wrecked_at'] is not None and self.elapsed - c['wrecked_at'] > CAR_RESPAWN]:
            if not any(p.get('car') == cid for p in self.players.values()):
                del self.cars[cid]
        while len(self.cars) < WORLD_CARS:
            spot = self._car_place()
            if not spot:
                break
            self.new_car(*spot)

    def load_cars(self, raw):
        self.cars = {}
        for cid, c in raw.items():
            if not isinstance(c, dict):
                continue
            try:
                model = int(c.get('model', 0))
                if not 0 <= model < len(CARS):
                    continue
                self.cars[cid] = {'id':cid, 'x':float(c['x']), 'y':float(c['y']), 'angle':float(c.get('angle', 0)), 'model':model,
                                  'hp':max(0.0, min(100.0, float(c.get('hp', 100)))), 'fuel':max(0.0, min(CARS[model]['tank'], float(c.get('fuel', 0)))),
                                  'vx':0.0, 'vy':0.0, 'steer':0.0, 'brake':False, 'slip':False,
                                  'wrecked_at':float(c['wrecked_at']) if c.get('wrecked_at') is not None else None}
            except (TypeError, ValueError, KeyError):
                continue

    def car_view(self, c):
        out = {k: c[k] for k in ('id', 'model', 'brake', 'slip')}
        out.update(x=round(c['x'], 1), y=round(c['y'], 1), angle=round(c['angle'], 3), hp=round(c['hp']), fuel=round(c['fuel'], 1),
                   vx=round(c['vx']), vy=round(c['vy']), steer=round(c['steer'], 2), wrecked=c['wrecked_at'] is not None)
        d = self.car_driver(c)
        out['driver'] = d['id'] if d else None
        out['riders'] = [q['id'] for q in self.car_riders(c)]
        return out

    # ---- seats -----------------------------------------------------------------
    def car_driver(self, car):
        return next((q for q in self.players.values() if q.get('car') == car['id'] and q.get('seat') == 'driver' and q['vehicle']), None)

    def car_riders(self, car):
        return [q for q in self.players.values() if q.get('car') == car['id'] and q.get('seat') == 'passenger' and q['vehicle']]

    def car_near(self, p, r=110):
        best = None
        for c in self.cars.values():
            spec = self.car_spec(c)
            d = math.hypot(c['x'] - p['x'], c['y'] - p['y'])
            if d <= spec['len'] * .6 + r - 80 and (best is None or d < best[0]):
                best = (d, c)
        return best[1] if best else None

    def enter_car(self, p):
        """Take the wheel of the nearest car, or a passenger seat when someone already drives it."""
        car = self.car_near(p, 110)
        if not car:
            raise self.GameError('Рядом нет машины.')
        if car['wrecked_at'] is not None or car['hp'] <= 0:
            raise self.GameError('Эта машина сгорела.')
        spec = self.car_spec(car)
        if math.hypot(car['vx'], car['vy']) > 80:
            raise self.GameError('Машина едет. Пусть водитель остановится.')
        seat = 'passenger' if self.car_driver(car) else 'driver'
        if seat == 'passenger' and len(self.car_riders(car)) >= spec['seats'] - 1:
            raise self.GameError('Мест нет: в «' + spec['name'] + '» ' + str(spec['seats']) + ' мест' + ('а' if spec['seats'] < 5 else '') + '.')
        p.update(vehicle=True, car=car['id'], seat=seat, x=car['x'], y=car['y'], angle=car['angle'])
        if seat == 'passenger':
            d = self.car_driver(car)
            self._notice(p['name'] + ' сел к тебе в машину', 'Пассажиров: ' + str(len(self.car_riders(car))) + ' из ' + str(spec['seats'] - 1) + '.', player=d['id'])
        return car, seat

    def leave_car(self, p, force=False):
        """Step out; `force` when the car burnt or the player died. The car stays where it stopped."""
        car = self.cars.get(p.get('car'))
        spot = None
        if car:
            if not force and math.hypot(car['vx'], car['vy']) > 80:
                raise self.GameError('Машина едет. Сначала остановись.' if p['seat'] == 'driver' else 'Машина едет. Попроси водителя остановиться.')
            spot = self.car_exit_spot(car, p['seat'] == 'passenger')
            if not spot and not force:
                raise self.GameError('Двери не открыть: рядом стена.')
            if not spot:
                spot = (car['x'], car['y'])
            if p['seat'] == 'driver':
                car.update(vx=0.0, vy=0.0, brake=False, slip=False)
        if spot:
            p['x'], p['y'] = spot
        p.update(vehicle=False, car=None, seat=None)

    def ride(self, p, car):
        """Passengers sit in the car and go where it goes."""
        if car['wrecked_at'] is not None:
            self.leave_car(p, force=True)
            return
        p['x'], p['y'], p['angle'] = car['x'], car['y'], car['angle']

    def car_exit_spot(self, car, passenger=False):
        """The driver's door is on the left; then the right side, then behind and in front."""
        spec = self.car_spec(car); a = car['angle']
        hx, hy = math.cos(a), math.sin(a); lx, ly = hy, -hx
        side = spec['wid'] / 2 + 14; fwd = spec['door'] * spec['len']
        if passenger:
            lx, ly = -lx, -ly; fwd = -spec['len'] * .12
        for sx, sy in ((lx * side + hx * fwd, ly * side + hy * fwd), (-lx * side + hx * fwd, -ly * side + hy * fwd),
                       (-hx * (spec['len'] / 2 + 16), -hy * (spec['len'] / 2 + 16)), (hx * (spec['len'] / 2 + 16), hy * (spec['len'] / 2 + 16))):
            x, y = car['x'] + sx, car['y'] + sy
            if not self.blocked(x, y, 11):
                return x, y
        return None

    def pumps(self):
        """Fuel pumps at the filling stations; they still give fuel."""
        return [[part['x'], part['y']] for poi in self.terrain.pois.values() for part in poi['parts'] if part['sprite'] == 'pump']

    def pump_near(self, obj, r):
        if not hasattr(self, '_pumps'):
            self._pumps = self.pumps()
        return next((q for q in self._pumps if math.hypot(q[0] - obj['x'], q[1] - obj['y']) < r), None)

    # ---- driving -----------------------------------------------------------------
    def drive(self, p, car, dt, steer, throttle, handbrake):
        spec = self.car_spec(car)
        if car['wrecked_at'] is not None:
            self.leave_car(p, force=True)
            return
        if self._car_blocked(spec, car['x'], car['y'], car['angle'], p['faction'], car):
            # Wedged into a wall (a fence built over it): ease the car out instead of freezing it.
            spot = self._car_spot(spec, car, 10, 120)
            if spot:
                car.update(x=spot[0], y=spot[1], vx=0.0, vy=0.0)
        x, y, a = car['x'], car['y'], car['angle']
        hx, hy = math.cos(a), math.sin(a); nx, ny = -hy, hx
        vx, vy = car['vx'], car['vy']
        fwd = vx * hx + vy * hy; lat = vx * nx + vy * ny
        if car['fuel'] <= .01:
            throttle = 0
        # Surface, weather and damage decide top speed and grip.
        road = self.terrain.on_road(x, y, ROAD_HALF + 10) or self.terrain.on_street(x, y, 8)
        town = min(self.towns.values(), key=lambda t: (t['x'] - x) ** 2 + (t['y'] - y) ** 2)
        snowy_ground = REGIONS[town['region']]['cold'] >= 2
        top = spec['max'] * (1 if road else spec['offroad']) * (.6 + .4 * min(1, car['hp'] / 50))
        grip = spec['grip'] * (1 if road else .85)
        weather = self.weather['kind']
        if weather in ('rain', 'storm'):
            grip *= .75
        if weather == 'snow' or (snowy_ground and not road):
            grip *= .6; top *= .9
        accel = spec['accel']
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
        car['steer'] += (lock - car['steer']) * min(1, dt * 7)
        yaw = fwd / (spec['len'] * .62) * math.tan(car['steer'])
        lat *= math.exp(-grip * dt)
        vx = hx * fwd + nx * lat; vy = hy * fwd + ny * lat
        na = a + yaw * dt
        f = p['faction']
        if self._car_blocked(spec, x, y, na, f, car):
            na = a
        if car['fuel'] > .01:
            car['fuel'] = max(0.0, car['fuel'] - dt * (.025 + .16 * abs(throttle) * (.5 + .5 * min(1, abs(fwd) / spec['max']))))
        tx, ty = x + vx * dt, y + vy * dt
        speed = math.hypot(vx, vy)
        if self._car_blocked(spec, tx, ty, na, f, car):
            # Slide along the obstacle if one axis is free; otherwise stop with a jolt.
            if not self._car_blocked(spec, tx, y, na, f, car):
                ty = y; vy *= -.2
            elif not self._car_blocked(spec, x, ty, na, f, car):
                tx = x; vx *= -.2
            else:
                tx, ty = x, y; vx *= -.25; vy *= -.25
            self._crash(p, car, speed, spec)
        car.update(x=tx, y=ty, angle=na, vx=vx, vy=vy, brake=braking, slip=abs(lat) > 70 or (handbrake and abs(fwd) > 80))
        p['x'], p['y'], p['angle'] = tx, ty, na
        # An engine is loud: the infected hear a car from far away.
        if speed > 30 and self.elapsed - car.get('noise_at', -10) > .5:
            car['noise_at'] = self.elapsed
            self.make_noise(tx, ty, 700 + speed, p)
        if speed > RAM_SPEED:
            self._ram(p, car, spec, speed)

    def _car_spot(self, spec, car, rmin, rmax):
        """The nearest place around the car where it fits, searched ring by ring."""
        r = rmin
        while r <= rmax:
            n = max(1, int(2 * math.pi * r / 40))
            for k in range(n):
                a = k * 2 * math.pi / n
                cx, cy = car['x'] + math.cos(a) * r, car['y'] + math.sin(a) * r
                if not self._car_blocked(spec, cx, cy, car['angle'], None, car):
                    return cx, cy
            r += 20
        return None

    def tick_cars(self, dt):
        for car in self.cars.values():
            if car['wrecked_at'] is not None or self.car_driver(car):
                continue
            # A car without a driver rolls to a stop.
            if car['vx'] or car['vy']:
                speed = math.hypot(car['vx'], car['vy'])
                k = max(0.0, speed - BRAKE * .5 * dt) / speed if speed > 1 else 0.0
                car['vx'] *= k; car['vy'] *= k
                spec = self.car_spec(car)
                tx, ty = car['x'] + car['vx'] * dt, car['y'] + car['vy'] * dt
                if self._car_blocked(spec, tx, ty, car['angle'], None, car):
                    car['vx'] = car['vy'] = 0.0
                else:
                    car['x'], car['y'] = tx, ty
                for q in self.car_riders(car):
                    self.ride(q, car)
        self.car_clock = getattr(self, 'car_clock', 0.0) + dt
        if self.car_clock > 20:
            self.car_clock = 0.0
            self.fill_cars()

    def _crash(self, p, car, speed, spec):
        if speed < CRASH_SPEED or self.elapsed - car.get('crash_at', -10) < .5:
            return
        car['crash_at'] = self.elapsed
        car['hp'] = max(0.0, car['hp'] - (speed - CRASH_SPEED) * .12 / spec['armor'])
        self.effects.append({'id':'c%x' % int(self.elapsed * 1000), 'kind':'crash', 'x':car['x'], 'y':car['y'], 'ex':car['x'], 'ey':car['y'],
                             'until':self.elapsed + .5, 'faction':None, 'power':round(min(1, (speed - CRASH_SPEED) / 250), 2)})
        self.make_noise(car['x'], car['y'], 900, p)
        if speed > 230:
            for q in [p] + self.car_riders(car):
                q['hit_by'] = {'kind':'crash', 'name':'', 'at':self.elapsed}
                self._damage(q, (speed - 230) * .06)
        if car['hp'] <= 0:
            self.wreck_car(car)

    def wreck_car(self, car):
        """The car burns out: everybody inside gets out, it stands as a wreck until replaced."""
        car['hp'] = 0.0; car['wrecked_at'] = self.elapsed; car['vx'] = car['vy'] = 0.0; car['fuel'] = 0.0
        self.effects.append({'id':secrets.token_hex(4), 'kind':'boom', 'x':car['x'], 'y':car['y'], 'ex':car['x'], 'ey':car['y'],
                             'until':self.elapsed + 1.4, 'faction':None})
        self.make_noise(car['x'], car['y'], 1400)
        for q in self.players.values():
            if q.get('car') == car['id']:
                self.leave_car(q, force=True)
                self._notice('Машина сгорела', 'Ищи другую: брошенные машины стоят у дорог и во дворах.', player=q['id'], tone='error')

    def _ram(self, p, car, spec, speed):
        reach = spec['wid'] * .55 + 12
        for o in self._nearby(car['x'], car['y'], spec['len']):
            if o is p or o.get('vehicle') or o['hp'] <= 0:
                continue
            if math.hypot(o['x'] - car['x'], o['y'] - car['y']) > reach:
                continue
            if not self.hostile_shot(p, o) or o.get('rammed_until', 0) > self.elapsed:
                continue
            o['rammed_until'] = self.elapsed + .8
            self.hurt(o, speed * .09, p)
            car['vx'] *= .7; car['vy'] *= .7
