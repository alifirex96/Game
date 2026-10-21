#!/usr/bin/env python3
"""A game server for checks and screenshots: a fresh world, fixed room code 123456 and a /debug endpoint.

Usage: python3 tools/devserver.py [port] [--lan]
POST /debug with JSON, for example {"weather": "fog"}, {"teleport": [x, y]} or {"exec": "p = ...; w.spawn_npc(...)"};
`exec` runs Python with `w` bound to the World. Never ship this: it is not in the package, and it listens only
on 127.0.0.1 unless --lan is given (for a second browser on another address in the same machine or network).
"""
import json
import random
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import GameServer, Handler, World  # noqa: E402


class DebugHandler(Handler):
    def do_POST(self):
        if self.path != '/debug':
            return super().do_POST()
        if not self._local():
            self._json(403, {'error': 'debug is local only'}); return
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        w = self.server.world
        with w.lock:
            if 'elapsed' in data: w.elapsed = data['elapsed']
            if 'weather' in data: w.weather = {'kind': data['weather'], 'until': w.elapsed + 9999}
            if 'teleport' in data:
                for p in w.players.values():
                    p['x'], p['y'] = data['teleport']; p['car'].update(x=data['teleport'][0] + 80, y=data['teleport'][1])
            if 'stock' in data:
                for f in w.stocks: w.stocks[f].update(data['stock'])
            if 'spawn' in data:
                for kind, faction, x, y in data['spawn']: w.spawn_npc(kind, faction, x, y)
            if 'gear' in data:
                for p in w.players.values(): p['gear'].update(data['gear'])
            if 'exec' in data: exec(data['exec'], {'w': w})
        self._json(200, {'ok': True})


def main():
    port = int(next((a for a in sys.argv[1:] if a.isdigit()), 8800))
    world = World(None, rng=random.Random(1)); world.room_code = '123456'
    srv = GameServer(('0.0.0.0' if '--lan' in sys.argv else '127.0.0.1', port), world, '123456')
    srv.RequestHandlerClass = DebugHandler

    def simulation():
        before = time.monotonic()
        while True:
            time.sleep(.05); now = time.monotonic()
            with world.lock: world.tick(now - before)
            before = now
    threading.Thread(target=simulation, daemon=True).start()
    print('http://127.0.0.1:%d  (room code 123456)' % port, flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
