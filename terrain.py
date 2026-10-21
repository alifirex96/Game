"""World geometry shared by the simulation: water, roads, collisions and road routes."""
import heapq
import math
from world_data import (ROAD_HALF, WORLD_SIZE, TOWNS, ROADS, RIVERS, LAKES, POIS, POI_KINDS, ROADSIDE_EVERY, ROADSIDE_KINDS, ROADSIDE_NAMES,
                        RESOURCES, SLOTS, BUILDINGS, TOWN_GATE, LANDMARKS, LANDMARK_POS, POPULATION, town_size)

CELL = 1000
RECT_CELL = 250               # finer buckets for walls and buildings: cities have hundreds of houses
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

# Footprints of ruins at each kind of point of interest: (dx, dy, w, h, sprite).
POI_LAYOUTS = {
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
            self.towns[t[0]] = {'id':t[0],'x':t[2],'y':t[3],'r':r,'h':h}
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
        self.graph = {t: [] for t in self.towns}
        for a, b in ROADS:
            d = math.hypot(self.towns[a]['x'] - self.towns[b]['x'], self.towns[a]['y'] - self.towns[b]['y'])
            self.graph[a].append((b, d)); self.graph[b].append((a, d))

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
        pop = POPULATION.get(t['id'], 60)
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
        public = [b for b in town_buildings(t['id'], tx, ty)]
        lm = landmark_rect(t['id'], tx, ty)
        if lm: public.append(dict(lm, w=lm['w'] / .6, h=lm['h'] / .5))
        edges_x = sorted({-R} | {-d for d in xs} | {0} | set(xs) | {R}); edges_y = sorted({-H} | {-d for d in ys} | {0} | set(ys) | {H})
        rnd = _seeded(t['id'])
        for i in range(len(edges_x) - 1):
            for j in range(len(edges_y) - 1):
                bx0, bx1, by0, by1 = edges_x[i], edges_x[i + 1], edges_y[j], edges_y[j + 1]
                far = max(abs(bx0 + bx1) / 2 / R, abs(by0 + by1) / 2 / H)
                panel = pop >= 250 and far < .8
                tries = 2 if panel else 4
                for k in range(tries):
                    if panel:
                        horiz = rnd() < .5; w, h = (150 + rnd() * 50, 62) if horiz else (62, 150 + rnd() * 50); kind = 'panel'
                    else:
                        w, h = 56 + rnd() * 18, 46 + rnd() * 12; kind = 'izba' if pop < 400 or far > .8 else 'house2'
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
        return False

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


def town_buildings(tid, x, y):
    out = []
    for kind, dx, dy in SLOTS:
        small = kind == 'guard'
        out.append({'id':tid+':'+kind,'town':tid,'kind':kind,'x':x+dx,'y':y+dy,
                    'w':64 if small else 116,'h':64 if small else 86})
    return out


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


def landmark_rect(tid, x, y):
    if tid not in LANDMARKS:
        return None
    name, w, h = LANDMARKS[tid]
    # The solid core is smaller than the drawing: people can walk around the plinth.
    return {'id':tid+':landmark','x':x+LANDMARK_POS[0],'y':y+LANDMARK_POS[1],'w':w*.6,'h':h*.5}


def resource_nodes(terrain):
    """Deterministic harvest points: around towns, near ruins and along every road."""
    nodes = {}
    kinds = list(RESOURCES)
    amounts = {'wood':4,'stone':4,'metal':2,'food':3,'fuel':3}   # scarce on purpose

    def place(nid, kind, x, y, amount=None):
        for step in range(12):
            nx = x + math.cos(step * 2.1) * step * 35; ny = y + math.sin(step * 2.1) * step * 35
            if terrain.free_spot(nx, ny, 26):
                nodes[nid] = {'id':nid,'kind':kind,'x':round(nx,1),'y':round(ny,1),'amount':amount or amounts[kind]}
                return

    for tid, name, x, y, region in TOWNS:
        # Guaranteed nearby supplies prevent an empty-fuel or empty-resource softlock.
        for n in range(24):
            angle = n * 2.39996
            radius = 490 + (n % 4) * 85
            place(tid+':n'+str(n), kinds[n % 5], x + math.cos(angle) * radius, y + math.sin(angle) * radius)
        place(tid+':first', 'wood', x + 70, y + 100)
    for pid, poi in terrain.pois.items():
        for n in range(3):
            angle = n * 2.1 + 0.6
            kind = list(POI_KINDS[poi['kind']]['loot'])[n % len(POI_KINDS[poi['kind']]['loot'])]
            place(pid+':n'+str(n), kind, poi['x'] + math.cos(angle) * 290, poi['y'] + math.sin(angle) * 290)
    counter = 0
    for ax, ay, bx, by, a, b in terrain.road_segments:
        length = math.hypot(bx - ax, by - ay)
        steps = int(length // 1500)
        for s in range(1, steps + 1):
            u = s / (steps + 1.0)
            nx = -(by - ay) / length; ny = (bx - ax) / length
            side = 1 if s % 2 else -1
            place('road'+str(counter), kinds[counter % 5], ax + (bx - ax) * u + nx * (ROAD_HALF + 100) * side,
                  ay + (by - ay) * u + ny * (ROAD_HALF + 100) * side)
            counter += 1
    return nodes
