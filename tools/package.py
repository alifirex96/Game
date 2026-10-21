#!/usr/bin/env python3
"""Build a redistributable user-space Astra Linux tarball with executable scripts."""
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from world_data import VERSION  # noqa: E402
DIST = ROOT / 'dist'
FILES = (
    'server.py', 'world_data.py', 'terrain.py', 'npc.py', 'vehicles.py', 'launcher.py', 'make_shortcut.py',
    'Играть.sh', 'Создать-ярлык.sh', 'README.md', 'CHANGELOG.md',
    'web/game.js', 'web/render.js', 'web/sprites.js', 'web/audio.js',
    'web/icon.svg', 'web/index.html', 'web/style.css', 'web/assets/characters.png', 'web/assets/givers.png', 'web/assets/portraits.jpg', 'web/assets/cars.png',
)

def normalize(member):
    member.uid = member.gid = 0
    member.uname = member.gname = ''
    member.mode = 0o755 if member.name.endswith('.sh') else 0o644
    return member

def main():
    DIST.mkdir(exist_ok=True)
    output = DIST / ('AfterSilence-Astra-' + VERSION + '.tar.gz')
    with tarfile.open(str(output), 'w:gz') as archive:
        for rel in FILES:
            src = ROOT / rel
            if not src.is_file():
                raise FileNotFoundError(str(src))
            archive.add(str(src), arcname='AfterSilence-Astra-' + VERSION + '/' + rel,
                        recursive=False, filter=normalize)
    print(output)

if __name__ == '__main__':
    main()
