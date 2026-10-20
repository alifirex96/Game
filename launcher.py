#!/usr/bin/env python3
"""User-space launcher: a small window when Tk is present, console fallback otherwise."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8765'

def existing_game():
    try:
        with urllib.request.urlopen(URL+'/api/config',timeout=.7) as response:
            value=json.load(response)
            return value if value.get('version') and value.get('factions') else None
    except (OSError,ValueError):
        return None

def main():
    if existing_game():
        webbrowser.open(URL)
        return 0
    try:
        import tkinter as tk
        from tkinter import messagebox
        window=tk.Tk()
    except Exception:
        # Python's HTTP server and browser remain sufficient; Tk is optional.
        os.execv(sys.executable,[sys.executable,str(ROOT/'server.py'),'--open'])
        return 1
    window.title('После тишины — комната')
    window.geometry('560x410');window.resizable(False,False)
    window.configure(bg='#15231b')
    log_dir=Path.home()/'.local/share/after-silence'
    try:
        log_dir.mkdir(parents=True,exist_ok=True)
        logfile=(log_dir/'server.log').open('a',encoding='utf-8')
    except OSError:
        logfile=None
    process=subprocess.Popen([sys.executable,str(ROOT/'server.py')],cwd=str(ROOT),stdout=logfile,stderr=logfile)
    tk.Label(window,text='ПОСЛЕ ТИШИНЫ',font=('Arial',24,'bold'),fg='#e7a568',bg='#15231b').pack(pady=(27,8))
    tk.Label(window,text='Локальный мир · до четырёх игроков',font=('Arial',11),fg='#c0cbb6',bg='#15231b').pack()
    status=tk.StringVar(value='Мир загружается…')
    tk.Label(window,textvariable=status,justify='center',font=('Arial',12),fg='#d8dfcc',bg='#15231b',wraplength=520).pack(pady=23)
    button=tk.Button(window,text='Открыть игру',command=lambda:webbrowser.open(URL),bg='#e7a568',fg='#17241b',font=('Arial',12,'bold'),relief='flat',padx=30,pady=12,state='disabled')
    button.pack()
    tk.Label(window,text='Передай друзьям адрес и код комнаты.\nОни открывают адрес в браузере — устанавливать игру им не нужно.\nНе закрывай это окно, пока идёт сетевая игра.',font=('Arial',10),fg='#a5b49a',bg='#15231b',justify='center').pack(pady=20)
    began=time.monotonic()
    def ready():
        data=existing_game()
        if data:
            status.set('Код комнаты: '+str(data['join_code'])+'\n\n'+'\n'.join(data['lan_addresses'] or ['Сетевой адрес не найден. На этом ПК: '+URL]))
            button.configure(state='normal');webbrowser.open(URL)
        elif process.poll() is not None or time.monotonic()-began>12:
            status.set('Не удалось запустить мир. Подробности:\n'+str(log_dir/'server.log'))
        else:window.after(250,ready)
    def stop():
        if process.poll() is None and not messagebox.askyesno('Завершить игру?','Все игроки отключатся. Мир будет сохранён. Закрыть комнату?'):return
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill()
        if logfile:logfile.close()
        window.destroy()
    window.protocol('WM_DELETE_WINDOW',stop);window.after(150,ready);window.mainloop()
    return 0

if __name__=='__main__':raise SystemExit(main())
