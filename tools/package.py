#!/usr/bin/env python3
"""Build a redistributable user-space Astra Linux tarball with executable scripts."""
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = '0.1.0'
DIST = ROOT / 'dist'
FILES = (
    'server.py', 'world_data.py', 'launcher.py', 'make_shortcut.py',
    'Играть.sh', 'Создать-ярлык.sh', 'README.md',
    'web/game.js', 'web/icon.svg', 'web/index.html', 'web/style.css',
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
