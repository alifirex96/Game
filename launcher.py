#!/usr/bin/env python3
"""User-space launcher: single player, hosting a LAN room or joining one by code.

A small Tk window when Tk is present, a text menu or plain LAN hosting otherwise.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 8765
DISCOVERY_PORT = 8766
URL = 'http://127.0.0.1:' + str(PORT)
DATA = Path.home() / '.local/share/after-silence'
BG, INK, MUTED, ACCENT, PANEL = '#15231b', '#d8dfcc', '#a5b49a', '#e7a568', '#1d2e25'

# Chromium-family browsers can open a page as a standalone app window (no tabs or address bar).
APP_BROWSERS = ('chromium', 'chromium-browser', 'chromium-gost', 'chromium-gost-stable', 'yandex-browser',
                'yandex-browser-stable', 'google-chrome', 'google-chrome-stable', 'microsoft-edge', 'brave-browser', 'vivaldi')
FIREFOX_PREFS = '''user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.aboutwelcome.enabled", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("media.autoplay.default", 0);
'''

def load_prefs():
    try:
        return json.loads((DATA / 'launcher.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'app_window': True}

def save_prefs(prefs):
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / 'launcher.json').write_text(json.dumps(prefs), encoding='utf-8')
    except OSError:
        pass

def open_game(url, app_window=True):
    """Open the game as its own window when a suitable browser exists; returns the window process.

    Everything runs from the user's home folder: a separate browser profile, no installation
    and no administrator rights.
    """
    if app_window:
        for name in APP_BROWSERS:
            exe = shutil.which(name)
            if exe:
                profile = DATA / 'window'
                profile.mkdir(parents=True, exist_ok=True)
                try:
                    return subprocess.Popen([exe, '--app=' + url, '--user-data-dir=' + str(profile), '--window-size=1600,900',
                                             '--no-first-run', '--no-default-browser-check', '--class=AfterSilence',
                                             '--autoplay-policy=no-user-gesture-required'],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except OSError:
                    continue
        exe = shutil.which('firefox') or shutil.which('firefox-esr')
        if exe:
            profile = DATA / 'firefox-window'
            try:
                profile.mkdir(parents=True, exist_ok=True)
                (profile / 'user.js').write_text(FIREFOX_PREFS, encoding='utf-8')
                return subprocess.Popen([exe, '--no-remote', '--profile', str(profile), '--kiosk', url],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
    webbrowser.open(url)
    return None

def existing_game():
    try:
        with urllib.request.urlopen(URL + '/api/config', timeout=.7) as response:
            value = json.load(response)
            return value if value.get('version') and value.get('cars') else None
    except (OSError, ValueError):
        return None

def find_rooms(timeout=1.3):
    """Broadcast a search on the local network; hosts answer with their port and name."""
    rooms = {}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(.25)
        for target in ('255.255.255.255', '127.0.0.1'):
            try:
                sock.sendto(b'AFTERSILENCE?', (target, DISCOVERY_PORT))
            except OSError:
                pass
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            try:
                info = json.loads(data.decode('utf-8'))
            except ValueError:
                continue
            if info.get('game') == 'after-silence':
                info['ip'] = addr[0]
                rooms[addr[0] + ':' + str(info.get('port'))] = info
        sock.close()
    except OSError:
        pass
    # The host also answers on loopback; keep its network address when both arrive.
    lan = {(r.get('name'), r.get('port')) for r in rooms.values() if not r['ip'].startswith('127.')}
    return [r for r in rooms.values() if not (r['ip'].startswith('127.') and (r.get('name'), r.get('port')) in lan)]

def server_command(mode):
    if mode == 'solo':
        return [sys.executable, str(ROOT / 'server.py'), '--host', '127.0.0.1', '--save', str(DATA / 'solo.json')]
    return [sys.executable, str(ROOT / 'server.py'), '--save', str(DATA / 'world.json')]

def join_url(address, code):
    address = address.strip()
    if not address.startswith('http'):
        address = 'http://' + address
    if address.count(':') < 2:
        address += ':' + str(PORT)
    return address.rstrip('/') + '/?code=' + ''.join(ch for ch in code if ch.isdigit())[:6]

def console():
    print('ПОСЛЕ ТИШИНЫ\n1 — одиночная игра\n2 — создать комнату в сети\n3 — подключиться к комнате')
    choice = input('Выбор [1]: ').strip() or '1'
    if choice == '3':
        rooms = find_rooms()
        for i, r in enumerate(rooms, 1):
            print(str(i) + ') ' + r['ip'] + ' · ' + r.get('name', '') + ' · игроков: ' + str(r.get('players', 0)))
        pick = input('Номер комнаты или адрес ведущего: ').strip()
        address = rooms[int(pick) - 1]['ip'] + ':' + str(rooms[int(pick) - 1]['port']) if pick.isdigit() and 0 < int(pick) <= len(rooms) else pick
        open_game(join_url(address, input('Код комнаты: ')), load_prefs().get('app_window', True))
        return 0
    server = subprocess.Popen(server_command('solo' if choice == '1' else 'lan'), cwd=str(ROOT))
    for _ in range(60):
        if existing_game():
            break
        time.sleep(.25)
    window = open_game(URL, load_prefs().get('app_window', True))
    print('Игра открыта. Для выхода закрой окно игры' + (' и нажми Ctrl+C.' if choice != '1' else '.'))
    try:
        if window is not None and choice == '1':
            window.wait()
            server.terminate()
        server.wait()
    except KeyboardInterrupt:
        server.terminate()
    return 0

def main():
    if existing_game():
        open_game(URL, load_prefs().get('app_window', True))
        return 0
    try:
        import tkinter as tk
        from tkinter import messagebox
        window = tk.Tk()
    except Exception:
        # Python's HTTP server and browser remain sufficient; Tk is optional.
        if sys.stdin and sys.stdin.isatty():
            return console()
        os.execv(sys.executable, server_command('lan') + ['--open'])
        return 1
    window.title('После тишины')
    window.geometry('600x500'); window.resizable(False, False)
    window.configure(bg=BG)
    state = {'process': None, 'log': None, 'began': 0, 'window': None, 'mode': None}
    prefs = load_prefs()
    app_var = tk.BooleanVar(value=prefs.get('app_window', True))

    def launch(url):
        prefs['app_window'] = bool(app_var.get()); save_prefs(prefs)
        state['window'] = open_game(url, prefs['app_window'])

    def watch_window():
        # Single player ends together with its window; a LAN room keeps running for friends.
        win = state['window']
        if win is not None and win.poll() is not None:
            state['window'] = None
            if state['mode'] == 'solo':
                shutdown(); return
        window.after(1000, watch_window)
    tk.Label(window, text='ПОСЛЕ ТИШИНЫ', font=('Arial', 26, 'bold'), fg=ACCENT, bg=BG).pack(pady=(26, 4))
    tk.Label(window, text='Россия после катастрофы · одиночная игра и сеть 2 × 2', font=('Arial', 11), fg=MUTED, bg=BG).pack()
    body = tk.Frame(window, bg=BG); body.pack(fill='both', expand=True, padx=40, pady=18)

    def button(parent, text, command, primary=False):
        b = tk.Button(parent, text=text, command=command, bg=ACCENT if primary else PANEL, fg='#17241b' if primary else INK,
                      activebackground='#f0b57c', font=('Arial', 12, 'bold' if primary else 'normal'), relief='flat',
                      padx=20, pady=11, cursor='hand2')
        b.pack(fill='x', pady=5)
        return b

    def clear():
        for w in body.winfo_children():
            w.destroy()

    def menu():
        clear()
        button(body, 'Одиночная игра', lambda: start('solo'), True)
        button(body, 'Создать комнату в сети', lambda: start('lan'))
        button(body, 'Подключиться к комнате по коду', join_screen)
        button(body, 'Создать ярлык на рабочем столе', shortcut)
        tk.Checkbutton(body, text='Открывать игру в отдельном окне, как приложение', variable=app_var, bg=BG, fg=INK,
                       selectcolor=PANEL, activebackground=BG, activeforeground=INK, font=('Arial', 10)).pack(pady=(8, 0))
        tk.Label(body, text='Игра запускается в браузере. Права администратора и интернет не нужны.\nПрогресс сохраняется в ' + str(DATA),
                 font=('Arial', 9), fg=MUTED, bg=BG, justify='center').pack(pady=(14, 0))

    def shortcut():
        subprocess.call([sys.executable, str(ROOT / 'make_shortcut.py'), '--quiet'])
        messagebox.showinfo('После тишины', 'Ярлык создан на рабочем столе и в меню.\nНе перемещай папку игры после создания ярлыка.')

    def start(mode):
        clear()
        try:
            DATA.mkdir(parents=True, exist_ok=True)
            state['log'] = (DATA / 'server.log').open('a', encoding='utf-8')
        except OSError:
            state['log'] = None
        state['process'] = subprocess.Popen(server_command(mode), cwd=str(ROOT), stdout=state['log'], stderr=state['log'])
        state['began'] = time.monotonic()
        status = tk.StringVar(value='Мир загружается…')
        tk.Label(body, textvariable=status, justify='center', font=('Arial', 12), fg=INK, bg=BG, wraplength=520).pack(pady=12)
        state['mode'] = mode
        open_button = button(body, 'Открыть игру', lambda: launch(URL), True)
        open_button.configure(state='disabled')
        tk.Label(body, text=('Передай друзьям адрес и код комнаты, либо пусть они нажмут\n«Подключиться к комнате по коду» в своём лаунчере.\nНе закрывай это окно, пока идёт сетевая игра.' if mode == 'lan'
                             else 'Одиночная игра идёт только на этом компьютере.'),
                 font=('Arial', 10), fg=MUTED, bg=BG, justify='center').pack(pady=14)

        def ready():
            data = existing_game()
            if data:
                if mode == 'lan':
                    status.set('Код комнаты: ' + str(data['join_code']) + '\n\n' + '\n'.join(data['lan_addresses'] or ['Сетевой адрес не найден. На этом ПК: ' + URL]))
                else:
                    status.set('Мир готов. Хорошей экспедиции!')
                open_button.configure(state='normal'); launch(URL); window.after(1500, watch_window)
            elif state['process'].poll() is not None or time.monotonic() - state['began'] > 15:
                status.set('Не удалось запустить мир. Возможно, порт ' + str(PORT) + ' занят другой программой.\nПодробности: ' + str(DATA / 'server.log'))
            else:
                window.after(250, ready)
        window.after(200, ready)

    def join_screen():
        clear()
        tk.Label(body, text='Комнаты в локальной сети', font=('Arial', 12, 'bold'), fg=INK, bg=BG).pack(anchor='w')
        listbox = tk.Listbox(body, height=5, bg=PANEL, fg=INK, font=('Arial', 11), relief='flat', selectbackground=ACCENT, highlightthickness=0)
        listbox.pack(fill='x', pady=6)
        found = []

        def scan():
            listbox.delete(0, 'end'); found[:] = find_rooms()
            for r in found:
                listbox.insert('end', '  ' + r.get('name', 'Комната') + ' · ' + r['ip'] + ' · игроков: ' + str(r.get('players', 0)) + ' · ' + r.get('version', ''))
            if not found:
                listbox.insert('end', '  Комнаты не найдены. Введи адрес ведущего вручную.')
        row = tk.Frame(body, bg=BG); row.pack(fill='x', pady=6)
        tk.Label(row, text='Адрес ведущего', fg=MUTED, bg=BG, font=('Arial', 10)).grid(row=0, column=0, sticky='w')
        tk.Label(row, text='Код комнаты', fg=MUTED, bg=BG, font=('Arial', 10)).grid(row=0, column=1, sticky='w', padx=(12, 0))
        address = tk.Entry(row, font=('Arial', 12), bg=PANEL, fg=INK, insertbackground=INK, relief='flat', width=26)
        address.grid(row=1, column=0, sticky='we', ipady=6)
        code = tk.Entry(row, font=('Arial', 12), bg=PANEL, fg=INK, insertbackground=INK, relief='flat', width=10)
        code.grid(row=1, column=1, sticky='we', padx=(12, 0), ipady=6)

        def pick(_event=None):
            sel = listbox.curselection()
            if sel and sel[0] < len(found):
                address.delete(0, 'end'); address.insert(0, found[sel[0]]['ip'] + ':' + str(found[sel[0]]['port']))
        listbox.bind('<<ListboxSelect>>', pick)

        def go():
            if not address.get().strip() or len(''.join(ch for ch in code.get() if ch.isdigit())) != 6:
                messagebox.showwarning('После тишины', 'Выбери комнату или введи адрес ведущего и шестизначный код.')
                return
            launch(join_url(address.get(), code.get()))
        button(body, 'Войти в комнату', go, True)
        nav = tk.Frame(body, bg=BG); nav.pack(fill='x')
        tk.Button(nav, text='Обновить список', command=scan, bg=BG, fg=MUTED, relief='flat', font=('Arial', 10)).pack(side='left')
        tk.Button(nav, text='Назад', command=menu, bg=BG, fg=MUTED, relief='flat', font=('Arial', 10)).pack(side='right')
        window.after(100, scan)

    def shutdown():
        process = state['process']
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        if state['log']:
            state['log'].close()
        window.destroy()

    def stop():
        process = state['process']
        if process and process.poll() is None:
            if not messagebox.askyesno('Завершить игру?', 'Все игроки отключатся. Мир будет сохранён. Закрыть комнату?'):
                return
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        if state['log']:
            state['log'].close()
        window.destroy()
    window.protocol('WM_DELETE_WINDOW', stop)
    menu()
    window.mainloop()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
