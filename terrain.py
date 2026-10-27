"""World geometry shared by the simulation: settlements, water, roads, collisions, loot spots and the coast."""
import heapq
import math
from world_data import (CARS, ROAD_HALF, ROAD_WIDTH, WORLD_SIZE, TOWNS, ROADS, RIVERS, LAKES, POIS, POI_KINDS, ROADSIDE_EVERY, ROADSIDE_KINDS, ROADSIDE_NAMES,
                        SEA_SOUTH, SEA_EAST, town_size, town_population)

CELL = 1000
RECT_CELL = 250               # finer buckets for walls and buildings: cities have hundreds of houses
WRECK_EVERY = 6700            # mean gap between abandoned cars along a highway
TOWN_HALF = (480, 420)        # half-size of the smallest settlement
CORE = (520, 480)             # the square and the ten public buildings; rivers never cross it
WALL = 8                      # thickness of house walls
DOOR = 28

def seg_dist(px, py, ax, ay, bx, by):
    dx = bx - ax; dy = by - ay
    length = dx * dx + dy * dy
    u = 0 if not length else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length))
    return math.hypot(px - ax - u * dx, py - ay - u * dy)

def point_in_poly(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside

# Footprints of buildings at each kind of place: (dx, dy, w, h, sprite). Flat sprites are drawn but never block.
FLAT = ('pump', 'runway')
POI_LAYOUTS = {
    'airfield': [(0,0,1700,130,'runway'),(-560,-300,250,150,'hangar'),(-220,-300,250,150,'hangar'),(120,-300,250,150,'hangar'),
                 (470,-290,70,70,'tower'),(-520,300,160,84,'barracks'),(-260,300,160,84,'barracks'),(20,300,160,84,'barracks')],
    'tents': [(-150,-80,84,58,'tent'),(-20,-80,84,58,'tent'),(110,-80,84,58,'tent'),(-150,70,84,58,'tent'),(-20,70,84,58,'tent'),(140,80,120,70,'barracks')],
    'checkpoint': [(-70,0,84,58,'tent'),(70,0,70,50,'shed')],
    'factory': [(-70,-40,230,140,'hall'),(115,-95,46,46,'chimney'),(110,70,100,74,'shed')],
    'gas': [(0,-80,96,58,'shop'),(0,40,10,10,'pump')],
    'military': [(-110,-60,150,84,'hangar'),(110,-60,150,84,'hangar'),(0,95,90,60,'barracks')],
    'farm': [(-80,-40,140,84,'barn'),(95,-55,48,48,'silo'),(80,75,90,56,'shed')],
    'village': [(-110,-70,70,56,'izba'),(100,-80,70,56,'izba'),(-95,85,70,56,'izba'),(110,75,70,56,'izba')],
    'oil': [(-90,-50,74,74,'tank'),(10,-70,74,74,'tank'),(-60,70,74,74,'tank'),(110,40,40,40,'derrick')],
    'mine': [(-60,-50,80,80,'headframe'),(90,40,120,80,'heap')],
    'rail': [(0,-90,200,62,'station'),(-120,70,110,46,'wagon'),(60,70,110,46,'wagon')],
}

class Terrain:
    def __init__(self):
        self.towns = {}
        for t in TOWNS:
            r, h = town_size(t[0])
            self.towns[t[0]] = {'id':t[0],'x':t[2],'y':t[3],'r':r,'h':h,'kind':t[5]}
        # Highways run between town gates, where the cross streets reach the edge of a settlement.
        self.road_segments = [self.gate(a, b) + self.gate(b, a) + (a, b) for a, b in ROADS]
        self.water_segments = []
        for name, width, points in RIVERS:
            for i in range(len(points) - 1):
                self.water_segments.append((points[i][0], points[i][1], points[i + 1][0], points[i + 1][1], width / 2.0))
        self.lakes = []
        for name, poly in LAKES:
            xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
            self.lakes.append((min(xs), min(ys), max(xs), max(ys), poly))
        # Coarse buckets keep water and town lookups cheap for many moving characters.
        self.water_grid = {}
        for seg in self.water_segments:
            ax, ay, bx, by, half = seg
            for gx in range(int((min(ax, bx) - half - 300) // CELL), int((max(ax, bx) + half + 300) // CELL) + 1):
                for gy in range(int((min(ay, by) - half - 300) // CELL), int((max(ay, by) + half + 300) // CELL) + 1):
                    self.water_grid.setdefault((gx, gy), [[], []])[0].append(seg)
        for lake in self.lakes:
            for gx in range(int((lake[0] - 300) // CELL), int((lake[2] + 300) // CELL) + 1):
                for gy in range(int((lake[1] - 300) // CELL), int((lake[3] + 300) // CELL) + 1):
                    self.water_grid.setdefault((gx, gy), [[], []])[1].append(lake)
        self.town_grid = {}
        for t in self.towns.values():
            for gx in range(int((t['x'] - t['r'] - 600) // CELL), int((t['x'] + t['r'] + 600) // CELL) + 1):
                for gy in range(int((t['y'] - t['h'] - 600) // CELL), int((t['y'] + t['h'] + 600) // CELL) + 1):
                    self.town_grid.setdefault((gx, gy), []).append(t)
        self.pois = {}
        for pid, name, kind, x, y in POIS:
            parts = [{'x':x+dx,'y':y+dy,'w':w,'h':h,'sprite':s} for dx, dy, w, h, s in POI_LAYOUTS[kind]]
            self.pois[pid] = {'id':pid,'name':name,'kind':kind,'x':x,'y':y,'parts':parts,
                              'kind_name':POI_KINDS[kind]['name']}
        self._roadside_stops()
        self.rects = []
        self.grid = {}
        self.streets = []; self.street_grid = {}; self.houses = {}
        for t in self.towns.values():
            self._lay_out_town(t)
        self._road_wrecks()
        self._mark_houses()
        self.coast = self._coast_points()
        self.graph = {t: [] for t in self.towns}
        for a, b in ROADS:
            d = math.hypot(self.towns[a]['x'] - self.towns[b]['x'], self.towns[a]['y'] - self.towns[b]['y'])
            self.graph[a].append((b, d)); self.graph[b].append((a, d))

    # ---- abandoned cars on the highways: rare, and solid -------------------------
    def _road_wrecks(self):
        """Cars stand where the silence caught them. Every client draws the same list; cars and people bump into them."""
        self.wrecks = []; self.wreck_grid = {}
        for ax, ay, bx, by, a, b in self.road_segments:
            length = math.hypot(bx - ax, by - ay)
            if length < 2000:
                continue
            ux, uy = (bx - ax) / length, (by - ay) / length; nx, ny = -uy, ux
            rnd = _seeded('wreck:' + a + ':' + b)
            d = 900 + rnd() * WRECK_EVERY
            while d < length - 900:
                x, y = ax + ux * d, ay + uy * d
                if not self.in_town(x, y, 400) and not self.water(x, y, 160) and \
                        not any(abs(p['x'] - x) < 700 and abs(p['y'] - y) < 700 for p in self.pois.values()):
                    lateral = (rnd() - .5) * ROAD_WIDTH * .76
                    angle = math.atan2(uy, ux) + (rnd() - .5) * 1.1 + (math.pi if rnd() < .5 else 0)
                    bus = rnd() < .12
                    self._add_wreck({'x':round(x + nx * lateral, 1), 'y':round(y + ny * lateral, 1), 'a':round(angle, 3),
                                     'm':int(rnd() * len(CARS)) % len(CARS), 'bus':bus, 'burnt':rnd() < .5})
                d += WRECK_EVERY * (.45 + rnd() * 1.1)

    def _add_wreck(self, w):
        length, width = (110, 34) if w['bus'] else (CARS[w['m']]['len'], CARS[w['m']]['wid'])
        r = width * .5; off = length / 2 - r
        c, s = math.cos(w['a']), math.sin(w['a'])
        w['circles'] = [(w['x'] + c * k, w['y'] + s * k, r) for k in (-off, 0.0, off)]
        self.wrecks.append(w)
        for cx, cy, cr in w['circles']:
            for gx in range(int((cx - cr - 60) // RECT_CELL), int((cx + cr + 60) // RECT_CELL) + 1):
                for gy in range(int((cy - cr - 60) // RECT_CELL), int((cy + cr + 60) // RECT_CELL) + 1):
                    self.wreck_grid.setdefault((gx, gy), []).append((cx, cy, cr))

    def wreck_hit(self, x, y, r):
        return any((x - cx) ** 2 + (y - cy) ** 2 < (cr + r) ** 2 for cx, cy, cr in self.wreck_grid.get((int(x // RECT_CELL), int(y // RECT_CELL)), ()))

    def gate(self, tid, other):
        """Highways enter a town where its main avenues reach the edge."""
        t = self.towns[tid]; o = self.towns[other]
        dx = o['x'] - t['x']; dy = o['y'] - t['y']
        if abs(dx) / t['r'] >= abs(dy) / t['h']:
            return (t['x'] + (t['r'] if dx > 0 else -t['r']), t['y'])
        return (t['x'], t['y'] + (t['h'] if dy > 0 else -t['h']))

    # ---- settlements: avenues, a street grid and abandoned houses ------------
    def _add_street(self, x1, y1, x2, y2, width):
        s = (x1, y1, x2, y2, width); self.streets.append(s)
        for gx in range(int((min(x1, x2) - width) // CELL), int((max(x1, x2) + width) // CELL) + 1):
            for gy in range(int((min(y1, y2) - width) // CELL), int((max(y1, y2) + width) // CELL) + 1):
                self.street_grid.setdefault((gx, gy), []).append(s)

    def on_street(self, x, y, pad=0):
        return any(seg_dist(x, y, s[0], s[1], s[2], s[3]) < s[4] / 2 + pad for s in self.street_grid.get((int(x // CELL), int(y // CELL)), ()))

    def _lay_out_town(self, t):
        tx, ty, R, H = t['x'], t['y'], t['r'], t['h']
        pop = town_population(t['id'])
        # Two avenues cross at the square and carry on as the highways.
        self._add_street(tx - R, ty, tx + R, ty, 68); self._add_street(tx, ty - H, tx, ty + H, 68)
        step = 300 if pop >= 300 else 250
        xs = [k * step for k in range(1, int(R // step) + 1) if k * step < R - 80]
        ys = [k * step for k in range(1, int(H // step) + 1) if k * step < H - 80]
        for s in (1, -1):
            for d in xs:
                if d < CORE[0]: self._add_street(tx + s * d, ty - H, tx + s * d, ty - CORE[1], 44); self._add_street(tx + s * d, ty + CORE[1], tx + s * d, ty + H, 44)
                else: self._add_street(tx + s * d, ty - H, tx + s * d, ty + H, 44)
            for d in ys:
                if d < CORE[1]: self._add_street(tx - R, ty + s * d, tx - CORE[0], ty + s * d, 44); self._add_street(tx + CORE[0], ty + s * d, tx + R, ty + s * d, 44)
                else: self._add_street(tx - R, ty + s * d, tx + R, ty + s * d, 44)
        # Blocks between the streets fill with houses: wooden izbas in villages and on the outskirts,
        # five-storey panel blocks in cities.
        public = []
        edges_x = sorted({-R} | {-d for d in xs} | {0} | set(xs) | {R}); edges_y = sorted({-H} | {-d for d in ys} | {0} | set(ys) | {H})
        rnd = _seeded(t['id'])
        for i in range(len(edges_x) - 1):
            for j in range(len(edges_y) - 1):
                bx0, bx1, by0, by1 = edges_x[i], edges_x[i + 1], edges_y[j], edges_y[j + 1]
                far = max(abs(bx0 + bx1) / 2 / R, abs(by0 + by1) / 2 / H)
                panel = pop >= 500 and far < .72
                tries = 2 if panel else 4
                for k in range(tries):
                    if panel:
                        horiz = rnd() < .5; w, h = (150 + rnd() * 50, 62) if horiz else (62, 150 + rnd() * 50); kind = 'panel'
                    else:
                        w, h = 56 + rnd() * 18, 46 + rnd() * 12; kind = 'izba' if pop < 100 or far > .85 else 'house2'
                    x = tx + bx0 + 30 + w / 2 + rnd() * max(1, (bx1 - bx0) - 60 - w)
                    y = ty + by0 + 30 + h / 2 + rnd() * max(1, (by1 - by0) - 60 - h)
                    self._try_house(t, kind, x, y, w, h, public)

    def _try_house(self, t, kind, x, y, w, h, public):
        if abs(x - t['x']) + w / 2 > t['r'] - 20 or abs(y - t['y']) + h / 2 > t['h'] - 20:
            return
        if math.hypot(x - t['x'], y - t['y']) < 175 + max(w, h) / 2:
            return
        for b in public:
            if abs(x - b['x']) < (w + b['w']) / 2 + 34 and abs(y - b['y']) < (h + b['h']) / 2 + 40:
                return
        for hx, hy in ((x, y), (x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x - w / 2, y + h / 2), (x + w / 2, y + h / 2)):
            if self.on_street(hx, hy, 18) or self.water(hx, hy, 20):
                return
        for o in self.house_grid_near(x, y):
            if abs(x - o['x']) < (w + o['w']) / 2 + 26 and abs(y - o['y']) < (h + o['h']) / 2 + 26:
                return
        # The door faces the nearest avenue side of the block.
        door = 's' if y < t['y'] else 'n'
        if abs(x - t['x']) > abs(y - t['y']) * 1.4: door = 'e' if x < t['x'] else 'w'
        hid = 'h' + str(len(self.houses))
        house = {'id':hid, 'town':t['id'], 'kind':kind, 'x':round(x), 'y':round(y), 'w':round(w), 'h':round(h), 'door':door}
        house['walls'] = house_walls(house)
        self.houses[hid] = house
        self._house_grid.setdefault((int(x // CELL), int(y // CELL)), []).append(house)
        for r in house['walls']:
            self.add_rect(r)

    def house_grid_near(self, x, y):
        if not hasattr(self, '_house_grid'):
            self._house_grid = {}
        gx, gy = int(x // CELL), int(y // CELL)
        out = []
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                out.extend(self._house_grid.get((gx + i, gy + j), ()))
        return out

    def house_at(self, x, y, pad=0):
        for h in self.house_grid_near(x, y):
            if abs(x - h['x']) < h['w'] / 2 + pad and abs(y - h['y']) < h['h'] / 2 + pad:
                return h
        return None

    def route_points(self, towns):
        """Waypoints that follow the highways: gate, gate, square for every hop."""
        out = []
        for i in range(len(towns) - 1):
            a, b = towns[i], towns[i + 1]
            out += [list(self.gate(a, b)), list(self.gate(b, a)), [self.towns[b]['x'], self.towns[b]['y']]]
        return out

    def _roadside_stops(self):
        """Stops along long highways so the drive between towns has places to search and refuel."""
        n = 0
        for ax, ay, bx, by, a, b in self.road_segments:
            length = math.hypot(bx - ax, by - ay)
            count = int(length // ROADSIDE_EVERY)
            nx = -(by - ay) / length; ny = (bx - ax) / length
            for k in range(count):
                u = (k + 1) / (count + 1.0); side = 1 if (n % 2) else -1
                kind = ROADSIDE_KINDS[n % len(ROADSIDE_KINDS)]
                off = ROAD_HALF + 300 if kind == 'gas' else ROAD_HALF + 580
                x = ax + (bx - ax) * u + nx * off * side; y = ay + (by - ay) * u + ny * off * side
                n += 1
                if not (900 < x < WORLD_SIZE[0] - 900 and 900 < y < WORLD_SIZE[1] - 900):
                    continue
                if self.water(x, y, 320) or self.in_town(x, y, 2500) or any(math.hypot(x - p['x'], y - p['y']) < 3000 for p in self.pois.values()):
                    continue
                pid = 'rs' + str(n)
                name = ROADSIDE_NAMES[(n * 7) % len(ROADSIDE_NAMES)] if kind in ('village', 'farm') else \
                    ('Заправка на трассе' if kind == 'gas' else 'Блокпост на трассе')
                parts = [{'x':x+dx,'y':y+dy,'w':w,'h':h,'sprite':s} for dx, dy, w, h, s in POI_LAYOUTS[kind]]
                self.pois[pid] = {'id':pid,'name':name,'kind':kind,'x':round(x),'y':round(y),'parts':parts,
                                  'kind_name':POI_KINDS[kind]['name']}

    def add_rect(self, rect):
        """Index a solid axis-aligned rectangle (dict with x, y, w, h centred)."""
        self.rects.append(rect)
        for key in self._rect_cells(rect):
            self.grid.setdefault(key, []).append(rect)

    def _rect_cells(self, rect):
        x0 = int((rect['x'] - rect['w'] / 2 - 60) // RECT_CELL); x1 = int((rect['x'] + rect['w'] / 2 + 60) // RECT_CELL)
        y0 = int((rect['y'] - rect['h'] / 2 - 60) // RECT_CELL); y1 = int((rect['y'] + rect['h'] / 2 + 60) // RECT_CELL)
        return [(gx, gy) for gx in range(x0, x1 + 1) for gy in range(y0, y1 + 1)]

    def remove_rect(self, rect):
        if rect in self.rects:
            self.rects.remove(rect)
        for key in self._rect_cells(rect):
            cell = self.grid.get(key)
            if cell and rect in cell:
                cell.remove(rect)

    def solid(self, x, y, r):
        for b in self.grid.get((int(x // RECT_CELL), int(y // RECT_CELL)), ()):
            if abs(x - b['x']) < b['w'] / 2 + r and abs(y - b['y']) < b['h'] / 2 + r:
                return True
        return self.wreck_hit(x, y, r)

    def in_town(self, x, y, pad=0):
        towns = self.town_grid.get((int(x // CELL), int(y // CELL)), ()) if pad <= 500 else self.towns.values()
        return any(abs(x - t['x']) < t['r'] + pad and abs(y - t['y']) < t['h'] + pad for t in towns)

    def in_core(self, x, y):
        """The square and its public buildings, embanked against rivers."""
        return any(abs(x - t['x']) < CORE[0] and abs(y - t['y']) < CORE[1] for t in self.town_grid.get((int(x // CELL), int(y // CELL)), ()))

    def on_road(self, x, y, width=ROAD_HALF + 20):
        return any(seg_dist(x, y, s[0], s[1], s[2], s[3]) < width for s in self.road_segments)

    def water(self, x, y, pad=0):
        """True over rivers or lakes. Rivers flow through cities; only the central square is embanked."""
        cell = self.water_grid.get((int(x // CELL), int(y // CELL)))
        if not cell or self.in_core(x, y):
            return False
        segments, lakes = cell
        for ax, ay, bx, by, half in segments:
            if min(ax, bx) - half - pad <= x <= max(ax, bx) + half + pad and \
               min(ay, by) - half - pad <= y <= max(ay, by) + half + pad and \
               seg_dist(x, y, ax, ay, bx, by) < half + pad:
                return True
        for x0, y0, x1, y1, poly in lakes:
            if x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad and point_in_poly(x, y, poly):
                return True
        return False

    def sea(self, x, y):
        return point_in_poly(x, y, SEA_SOUTH) or point_in_poly(x, y, SEA_EAST)

    # ---- the coast: fresh characters wash up here ------------------------------
    def _coast_points(self):
        """Dry spots a little inland along both coasts, every 1.5 km."""
        out = []
        for poly in (SEA_SOUTH, SEA_EAST):
            for i in range(len(poly) - 1):
                (ax, ay), (bx, by) = poly[i], poly[i + 1]
                if ax in (0, WORLD_SIZE[0]) and bx in (0, WORLD_SIZE[0]) or ay == by == WORLD_SIZE[1] or ay == by == 0:
                    continue           # the edge of the map, not the shore
                length = math.hypot(bx - ax, by - ay)
                for k in range(int(length // 1500) + 1):
                    u = min(1.0, k * 1500 / max(1, length)); x, y = ax + (bx - ax) * u, ay + (by - ay) * u
                    for inland in (360, 520, 700):
                        # Inland is away from the sea corner of the map.
                        px, py = (x, y - inland) if poly is SEA_SOUTH else (x - inland, y)
                        if self.free_spot(px, py, 30) and not self.in_town(px, py, 80):
                            out.append((round(px), round(py))); break
        return out

    # ---- what buildings hold: loot tables by kind ---------------------------------
    def _mark_houses(self):
        """Izbas are rural, other houses residential; some panel blocks in cities are clinics."""
        rnd = _seeded('clinics')
        for h in self.houses.values():
            h['use'] = 'rural' if h['kind'] == 'izba' else 'residential'
            if h['kind'] == 'panel' and rnd() < .08:
                h['use'] = 'medical'

    def loot_spots(self):
        """Every place where loot can lie: (building id, table, [(x, y), ...]). Houses inside, other buildings at the door."""
        out = []
        for h in self.houses.values():
            ax, ay = max(6, h['w'] / 2 - 18), max(6, h['h'] / 2 - 18)
            rnd = _seeded('spot' + h['id'])
            pts = [(round(h['x'] + (rnd() * 2 - 1) * ax), round(h['y'] + (rnd() * 2 - 1) * ay)) for i in range(3)]
            out.append((h['id'], h['use'], h['kind'], pts))
        for poi in self.pois.values():
            table = POI_KINDS[poi['kind']]['loot']
            for i, part in enumerate(poi['parts']):
                if part['sprite'] in FLAT:
                    continue
                x, y = part['x'], part['y'] + part['h'] / 2 + 22
                pts = [(round(x - 26), round(y)), (round(x + 26), round(y + 6))]
                out.append((poi['id'] + ':' + str(i), table, 'poi', pts))
        return out

    def route(self, start, goal):
        """Town ids along the shortest road route, or [] when unreachable."""
        if start == goal:
            return [start]
        best = {start: 0}; prev = {}; queue = [(0, start)]
        while queue:
            d, node = heapq.heappop(queue)
            if node == goal:
                break
            if d > best.get(node, 1e18):
                continue
            for other, length in self.graph[node]:
                nd = d + length
                if nd < best.get(other, 1e18):
                    best[other] = nd; prev[other] = node; heapq.heappush(queue, (nd, other))
        if goal not in prev:
            return []
        path = [goal]
        while path[-1] != start:
            path.append(prev[path[-1]])
        return path[::-1]

    def road_distance(self, start, goal):
        path = self.route(start, goal)
        if not path:
            return 1e18
        return sum(math.hypot(self.towns[path[i]]['x'] - self.towns[path[i + 1]]['x'],
                              self.towns[path[i]]['y'] - self.towns[path[i + 1]]['y']) for i in range(len(path) - 1))

    def free_spot(self, x, y, r=12):
        return 30 < x < WORLD_SIZE[0] - 30 and 30 < y < WORLD_SIZE[1] - 30 and \
            not self.water(x, y, r) and not self.solid(x, y, r)


def _seeded(text):
    state = [sum(ord(c) * (i + 7) for i, c in enumerate(text)) % 2147483646 + 1]
    def rnd():
        state[0] = state[0] * 16807 % 2147483647
        return state[0] / 2147483647.0
    return rnd


def house_walls(h):
    """Four walls with a door gap: houses can be entered, searched and turned into a camp."""
    x0, y0, x1, y1 = h['x'] - h['w'] / 2, h['y'] - h['h'] / 2, h['x'] + h['w'] / 2, h['y'] + h['h'] / 2
    out = []
    def wall(ax, ay, bx, by):
        out.append({'x':(ax + bx) / 2, 'y':(ay + by) / 2, 'w':max(WALL, bx - ax), 'h':max(WALL, by - ay), 'house':h['id']})
    for side, (ax, ay, bx, by) in (('n', (x0, y0, x1, y0 + WALL)), ('s', (x0, y1 - WALL, x1, y1)),
                                  ('w', (x0, y0, x0 + WALL, y1)), ('e', (x1 - WALL, y0, x1, y1))):
        if side != h['door']:
            wall(ax, ay, bx, by); continue
        if side in ('n', 's'):
            mid = (x0 + x1) / 2; wall(ax, ay, mid - DOOR / 2, by); wall(mid + DOOR / 2, ay, bx, by)
        else:
            mid = (y0 + y1) / 2; wall(ax, ay, bx, mid - DOOR / 2); wall(ax, mid + DOOR / 2, bx, by)
    return out


def resource_nodes(terrain):
    """Deterministic harvest points: trees to cut (an axe gives planks), scrap heaps and berry bushes."""
    nodes = {}
    kinds = ['wood', 'metal', 'food', 'wood']
    amounts = {'wood':2,'metal':1,'food':2}

    def place(nid, kind, x, y, amount=None):
        for step in range(12):
            nx = x + math.cos(step * 2.1) * step * 35; ny = y + math.sin(step * 2.1) * step * 35
            if terrain.free_spot(nx, ny, 26):
                nodes[nid] = {'id':nid,'kind':kind,'x':round(nx,1),'y':round(ny,1),'amount':amount or amounts[kind]}
                return

    for t in TOWNS:
        tid = t[0]; town = terrain.towns[tid]
        for n in range(8):
            angle = n * 2.39996
            radius = max(town['r'], town['h']) + 260 + (n % 3) * 120
            place(tid+':n'+str(n), kinds[n % len(kinds)], town['x'] + math.cos(angle) * radius, town['y'] + math.sin(angle) * radius)
    for pid, poi in terrain.pois.items():
        for n in range(2):
            angle = n * 2.1 + 0.6
            place(pid+':n'+str(n), 'metal' if n else 'wood', poi['x'] + math.cos(angle) * 420, poi['y'] + math.sin(angle) * 420)
    counter = 0
    for ax, ay, bx, by, a, b in terrain.road_segments:
        length = math.hypot(bx - ax, by - ay)
        steps = int(length // 3200)
        for s in range(1, steps + 1):
            u = s / (steps + 1.0)
            nx = -(by - ay) / length; ny = (bx - ax) / length
            side = 1 if s % 2 else -1
            place('road'+str(counter), kinds[counter % len(kinds)], ax + (bx - ax) * u + nx * (ROAD_HALF + 100) * side,
                  ay + (by - ay) * u + ny * (ROAD_HALF + 100) * side)
            counter += 1
    return nodes
