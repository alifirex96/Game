"""World geometry shared by the simulation: water, roads, collisions and road routes."""
import heapq
import math
from world_data import (WORLD_SIZE, TOWNS, ROADS, RIVERS, LAKES, POIS, POI_KINDS,
                        RESOURCES, SLOTS, BUILDINGS, TOWN_GATE, LANDMARKS, LANDMARK_POS)

CELL = 1000
TOWN_HALF = (480, 420)        # half-size of the cleared town area

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
        self.towns = {t[0]: {'id':t[0],'x':t[2],'y':t[3]} for t in TOWNS}
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
            for gx in range(int((t['x'] - 1000) // CELL), int((t['x'] + 1000) // CELL) + 1):
                for gy in range(int((t['y'] - 1000) // CELL), int((t['y'] + 1000) // CELL) + 1):
                    self.town_grid.setdefault((gx, gy), []).append(t)
        self.pois = {}
        for pid, name, kind, x, y in POIS:
            parts = [{'x':x+dx,'y':y+dy,'w':w,'h':h,'sprite':s} for dx, dy, w, h, s in POI_LAYOUTS[kind]]
            self.pois[pid] = {'id':pid,'name':name,'kind':kind,'x':x,'y':y,'parts':parts,
                              'kind_name':POI_KINDS[kind]['name']}
        self.rects = []
        self.grid = {}
        self.graph = {t: [] for t in self.towns}
        for a, b in ROADS:
            d = math.hypot(self.towns[a]['x'] - self.towns[b]['x'], self.towns[a]['y'] - self.towns[b]['y'])
            self.graph[a].append((b, d)); self.graph[b].append((a, d))

    def gate(self, tid, other):
        t = self.towns[tid]; o = self.towns[other]
        dx = o['x'] - t['x']; dy = o['y'] - t['y']
        if abs(dx) / TOWN_GATE[0] >= abs(dy) / TOWN_GATE[1]:
            return (t['x'] + (TOWN_GATE[0] if dx > 0 else -TOWN_GATE[0]), t['y'])
        return (t['x'], t['y'] + (TOWN_GATE[1] if dy > 0 else -TOWN_GATE[1]))

    def route_points(self, towns):
        """Waypoints that follow the highways: gate, gate, square for every hop."""
        out = []
        for i in range(len(towns) - 1):
            a, b = towns[i], towns[i + 1]
            out += [list(self.gate(a, b)), list(self.gate(b, a)), [self.towns[b]['x'], self.towns[b]['y']]]
        return out

    def add_rect(self, rect):
        """Index a solid axis-aligned rectangle (dict with x, y, w, h centred)."""
        self.rects.append(rect)
        x0 = int((rect['x'] - rect['w'] / 2 - 40) // CELL); x1 = int((rect['x'] + rect['w'] / 2 + 40) // CELL)
        y0 = int((rect['y'] - rect['h'] / 2 - 40) // CELL); y1 = int((rect['y'] + rect['h'] / 2 + 40) // CELL)
        for gx in range(x0, x1 + 1):
            for gy in range(y0, y1 + 1):
                self.grid.setdefault((gx, gy), []).append(rect)

    def solid(self, x, y, r):
        for b in self.grid.get((int(x // CELL), int(y // CELL)), ()):
            if abs(x - b['x']) < b['w'] / 2 + r and abs(y - b['y']) < b['h'] / 2 + r:
                return True
        return False

    def in_town(self, x, y, pad=0):
        towns = self.town_grid.get((int(x // CELL), int(y // CELL)), ()) if pad <= 500 else self.towns.values()
        return any(abs(x - t['x']) < TOWN_HALF[0] + pad and abs(y - t['y']) < TOWN_HALF[1] + pad for t in towns)

    def on_road(self, x, y, width=60):
        return any(seg_dist(x, y, s[0], s[1], s[2], s[3]) < width for s in self.road_segments)

    def water(self, x, y, pad=0):
        """True over rivers or lakes. Town areas are embanked and never count as water."""
        cell = self.water_grid.get((int(x // CELL), int(y // CELL)))
        if not cell or self.in_town(x, y):
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
    amounts = {'wood':8,'stone':8,'metal':6,'food':7,'fuel':8}

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
        steps = int(length // 900)
        for s in range(1, steps + 1):
            u = s / (steps + 1.0)
            nx = -(by - ay) / length; ny = (bx - ax) / length
            side = 1 if s % 2 else -1
            place('road'+str(counter), kinds[counter % 5], ax + (bx - ax) * u + nx * 150 * side,
                  ay + (by - ay) * u + ny * 150 * side)
            counter += 1
    return nodes
