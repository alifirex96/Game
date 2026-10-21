# После тишины — заметки для Claude и агентов

2D-игра о выживании в России после катастрофы: вид сверху, пешком и на машине, одиночная игра и локальная сеть до 25 игроков. Интерфейс и тексты — на русском; комментарии в коде — на английском, коротко, в стиле окружающего кода.

## Жёсткие ограничения
- Целевая система — Astra Linux 1.7 без прав администратора: **Python 3.7+, только стандартная библиотека**, никаких pip-пакетов, Docker, интернета.
- Клиент — браузер, Canvas2D, чистый JavaScript без библиотек и сборки. Вся графика рисуется кодом или берётся из `web/assets/*.png|jpg`; звук и музыка синтезируются в `web/audio.js`.
- Сервер авторитетный: всё считает ведущий, клиент шлёт нажатия и запросы действий.

## Где что лежит
- `server.py` — класс `World` (тик, действия игроков `_act`, снимок состояния `snapshot`, сохранение) и HTTP-сервер.
- `world_data.py` — данные: оружие, предметы, рецепты, машины, NPC, задания, диалоги, города, константы (`VERSION`, `ROAD_WIDTH`…).
- `terrain.py` — карта: города, улицы, дома, дороги, реки, брошенные машины, препятствия.
- `npc.py` — NPC, звери, бой, урон, тела. `vehicles.py` — физика машин, пассажиры. `camps.py` — лагеря, крафт, ящики, тела.
- `web/game.js` — ввод, HUD, окна. `web/render.js` — отрисовка мира. `web/sprites.js` — спрайты, кадры героя (`assets/hero.png`). `web/audio.js` — звук. `web/style.css`, `web/index.html`.
- `tests/` — unittest. `tools/package.py` — архив для Astra. `tools/devserver.py` — сервер для проверок с `/debug`.
- `CHANGELOG.md` — изменения по версиям; `README.md` — описание для игроков.

## Проверка перед коммитом
```
python3 -m unittest discover -s tests
python3 -c "import ast,glob;[ast.parse(open(f).read(),f,feature_version=(3,7)) for f in glob.glob('*.py')+glob.glob('tools/*.py')]"
for f in web/*.js; do node --check "$f"; done
python3 tools/package.py
```
Новый файл игры добавляй в `FILES` в `tools/package.py`, а картинку — ещё и в `STATIC` в `server.py`.

## Релиз
Подними `VERSION` в `world_data.py`, добавь раздел `## X.Y.Z` в начало `CHANGELOG.md` и залей в `main`: workflow `.github/workflows/release.yml` сам соберёт и опубликует релиз.

## Команда агентов (`.claude/agents/`)
game-designer, programmer, artist, animator, writer, ui-ux, sound-designer, qa, producer. Продюсер раскладывает задачу на шаги и роли; остальные делают свою часть и возвращают результат.
