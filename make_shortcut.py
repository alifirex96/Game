#!/usr/bin/env python3
"""Create a launcher only in the current user's desktop and applications directory."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

def quote(value):
    # Desktop Entry Exec quoting, not shell quoting. Percent signs are field codes.
    return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'

def main():
    root=Path(__file__).resolve().parent
    python=shutil.which('python3') or sys.executable
    try:
        desktop=Path(subprocess.check_output(['xdg-user-dir','DESKTOP'],universal_newlines=True).strip())
        if not desktop.is_absolute():raise ValueError()
    except (OSError,ValueError,subprocess.CalledProcessError):
        desktop=Path.home()/'Desktop'
    target=Path.home()/'.local/share/applications'
    text='[Desktop Entry]\nType=Application\nName=После тишины\nComment=Россия: восстановление поселений, одиночная игра и LAN\nExec='+quote(python)+' '+quote(root/'launcher.py')+'\nIcon='+str(root/'web/icon.svg')+'\nTerminal=false\nCategories=Game;\nStartupNotify=true\n'
    for folder in (desktop,target):
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/'after-silence.desktop'
        path.write_text(text,encoding='utf-8');path.chmod(0o755)
    print('Ярлык «После тишины» создан на рабочем столе и в меню пользователя.')
    if '--quiet' in sys.argv:
        return 0
    try:
        import tkinter as tk
        from tkinter import messagebox
        w=tk.Tk();w.withdraw();messagebox.showinfo('После тишины','Ярлык создан на рабочем столе.\nНе перемещай папку игры после создания ярлыка.');w.destroy()
    except Exception:pass
    return 0

if __name__=='__main__':raise SystemExit(main())
