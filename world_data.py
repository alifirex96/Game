"""Static game rules and the map of the region. Python 3.7+, standard library only.

From 0.8 the game follows DayZ, seen from above: one compact coastal region, infected in every settlement,
loot lying in buildings, no levels, quests, coins or shops. Fresh characters wash up on the coast with
next to nothing; everything a player has is found, crafted or taken from the dead.
"""
VERSION = '0.8.0'
# One region of about 14 km: a person is ~38 px tall, so 1 m is ~21 px. The sea lies to the south and the east.
WORLD_SCALE = 1
WORLD_SIZE = (300000, 300000)
MAX_PLAYERS = 25
SIDE_COLORS = ['#e7a568', '#7fb2d0', '#a7c46a', '#d79cb7', '#e0d46a', '#9b8fd6', '#6ad0b8', '#f08a6a', '#c9c9c9', '#b98a5a',
               '#5fa0e0', '#e06a9a', '#8ad06a', '#d0a0e0', '#e0b0a0', '#70c0c0', '#c0c060', '#a0a0f0', '#f0c040', '#60e090',
               '#e07050', '#90b0d0', '#d090c0', '#b0d090', '#f0e0a0', '#80a080', '#c08060']
REGION_NAME = 'Белогорье'
# Settlements: id, name, x, y, region, kind (city, town or village). Inspired by a Black Sea coast, invented names.
_K = 1000
TOWNS = [
    ('svetlogorsk', 'Светлогорск', 62 * _K, 266 * _K, 'Белогорье', 'city'),
    ('severogorsk', 'Северогорск', 132 * _K, 58 * _K, 'Северное Белогорье', 'city'),
    ('zavodskoy', 'Заводской', 196 * _K, 267 * _K, 'Белогорье', 'town'),
    ('beregovoy', 'Береговой', 266 * _K, 176 * _K, 'Белогорье', 'town'),
    ('starysobor', 'Старый Собор', 141 * _K, 165 * _K, 'Белогорье', 'town'),
    ('vyazniki', 'Вязники', 76 * _K, 150 * _K, 'Белогорье', 'town'),
    ('severnoe', 'Северное', 262 * _K, 56 * _K, 'Северное Белогорье', 'town'),
    ('kamenka', 'Каменка', 22 * _K, 272 * _K, 'Белогорье', 'village'),
    ('rybatskoe', 'Рыбацкое', 112 * _K, 274 * _K, 'Белогорье', 'village'),
    ('solnechnoe', 'Солнечное', 151 * _K, 272 * _K, 'Белогорье', 'village'),
    ('kamyshovo', 'Камышово', 238 * _K, 271 * _K, 'Белогорье', 'village'),
    ('primorskoe', 'Приморское', 261 * _K, 234 * _K, 'Белогорье', 'village'),
    ('sosnovybor', 'Сосновый Бор', 268 * _K, 120 * _K, 'Белогорье', 'village'),
    ('taezhny', 'Таёжный', 234 * _K, 26 * _K, 'Северное Белогорье', 'village'),
    ('ozernoe', 'Озёрное', 205 * _K, 96 * _K, 'Белогорье', 'village'),
    ('lipovka', 'Липовка', 70 * _K, 94 * _K, 'Северное Белогорье', 'village'),
    ('lesnoe', 'Лесное', 28 * _K, 128 * _K, 'Белогорье', 'village'),
    ('zarechye', 'Заречье', 30 * _K, 196 * _K, 'Белогорье', 'village'),
    ('sosnovka', 'Сосновка', 56 * _K, 226 * _K, 'Белогорье', 'village'),
    ('pokrovka', 'Покровка', 108 * _K, 216 * _K, 'Белогорье', 'village'),
    ('dubrovka', 'Дубровка', 172 * _K, 226 * _K, 'Белогорье', 'village'),
    ('gulyaevo', 'Гуляево', 222 * _K, 214 * _K, 'Белогорье', 'village'),
    ('gremyachy', 'Гремячий', 202 * _K, 160 * _K, 'Белогорье', 'village'),
    ('olkhovka', 'Ольховка', 98 * _K, 36 * _K, 'Северное Белогорье', 'village'),
    ('krasnyyar', 'Красный Яр', 176 * _K, 34 * _K, 'Северное Белогорье', 'village'),
]
ROADS = [('kamenka','svetlogorsk'),('svetlogorsk','rybatskoe'),('rybatskoe','solnechnoe'),('solnechnoe','zavodskoy'),
         ('zavodskoy','kamyshovo'),('kamyshovo','primorskoe'),('primorskoe','beregovoy'),('beregovoy','sosnovybor'),
         ('sosnovybor','severnoe'),('severnoe','taezhny'),('taezhny','krasnyyar'),('krasnyyar','severogorsk'),
         ('severogorsk','olkhovka'),('olkhovka','lipovka'),('lipovka','lesnoe'),('lesnoe','zarechye'),('zarechye','sosnovka'),
         ('sosnovka','svetlogorsk'),('svetlogorsk','pokrovka'),('pokrovka','vyazniki'),('vyazniki','lipovka'),
         ('vyazniki','starysobor'),('starysobor','severogorsk'),('starysobor','gremyachy'),('gremyachy','beregovoy'),
         ('solnechnoe','dubrovka'),('dubrovka','starysobor'),('zavodskoy','gulyaevo'),('gulyaevo','gremyachy'),
         ('gremyachy','ozernoe'),('ozernoe','severogorsk'),('ozernoe','sosnovybor'),('pokrovka','dubrovka')]
# Climate: the north is colder and darker in its forests.
REGIONS = {'Белогорье': {'biome':'mixed','cold':0}, 'Северное Белогорье': {'biome':'taiga','cold':1}}
# Water blocks vehicles except on bridges; people wade slowly. [name, width, points]
RIVERS = [
    ['Белая', 70, [(150*_K,0),(146*_K,30*_K),(158*_K,72*_K),(152*_K,112*_K),(136*_K,150*_K),(144*_K,196*_K),(128*_K,236*_K),(132*_K,284*_K)]],
    ['Ключевая', 45, [(46*_K,60*_K),(52*_K,110*_K),(44*_K,160*_K),(50*_K,205*_K),(40*_K,250*_K),(44*_K,284*_K)]],
]
# The sea is two polygons (south and east coasts) so water lookups stay cheap; lakes are small.
SEA_SOUTH = [(0,288*_K),(18*_K,285*_K),(40*_K,284*_K),(62*_K,280*_K),(84*_K,283*_K),(110*_K,285*_K),(132*_K,286*_K),
             (152*_K,284*_K),(176*_K,283*_K),(196*_K,280*_K),(218*_K,283*_K),(240*_K,284*_K),(258*_K,282*_K),(274*_K,279*_K),
             (300*_K,279*_K),(300*_K,300*_K),(0,300*_K)]
SEA_EAST = [(274*_K,279*_K),(277*_K,262*_K),(276*_K,246*_K),(279*_K,230*_K),(281*_K,210*_K),(278*_K,190*_K),
            (280*_K,170*_K),(283*_K,150*_K),(281*_K,128*_K),(284*_K,106*_K),(282*_K,84*_K),(279*_K,64*_K),
            (283*_K,44*_K),(286*_K,22*_K),(285*_K,0),(300*_K,0),(300*_K,279*_K)]
LAKES = [
    ['Студёное море', SEA_SOUTH],
    ['Студёное море', SEA_EAST],
    ['Чёрное озеро', [(90*_K,64*_K),(99*_K,62*_K),(104*_K,70*_K),(98*_K,78*_K),(89*_K,75*_K)]],
    ['Лесное озеро', [(212*_K,114*_K),(222*_K,112*_K),(226*_K,121*_K),(218*_K,128*_K),(210*_K,123*_K)]],
]
# Ridges are drawn as rocky ground; they never block movement. (name, x, y, rx, ry)
HILLS = [('Северный кряж', 112 * _K, 110 * _K, 22 * _K, 12 * _K), ('Красная гряда', 205 * _K, 58 * _K, 18 * _K, 10 * _K),
         ('Сосновые холмы', 92 * _K, 196 * _K, 14 * _K, 9 * _K)]
# Places outside the settlements. 'loot' names the table for what lies inside, 'infected' how many walk there.
POI_KINDS = {
    'airfield': {'name':'Аэродром','loot':'military','infected':14},
    'military': {'name':'Воинская часть','loot':'military','infected':10},
    'tents': {'name':'Палаточный лагерь','loot':'military','infected':8},
    'checkpoint': {'name':'Блокпост','loot':'military','infected':4},
    'factory': {'name':'Завод','loot':'industrial','infected':8},
    'rail': {'name':'Железнодорожная станция','loot':'industrial','infected':6},
    'oil': {'name':'Нефтебаза','loot':'industrial','infected':5},
    'mine': {'name':'Карьер','loot':'industrial','infected':4},
    'farm': {'name':'Колхоз','loot':'farm','infected':5},
    'gas': {'name':'Заправка','loot':'gas','infected':2},
    'village': {'name':'Хутор','loot':'rural','infected':3},
}
POIS = [
    ('airfield','Аэродром «Северный»','airfield',38*_K,40*_K), ('base_sobor','Воинская часть у Старого Собора','military',176*_K,124*_K),
    ('base_north','Воинская часть «Кедр»','military',150*_K,26*_K), ('tents_east','Палаточный лагерь','tents',236*_K,142*_K),
    ('tents_west','Палаточный лагерь у Лесного','tents',52*_K,136*_K), ('cp_pokrovka','Блокпост на Покровской дороге','checkpoint',100*_K,196*_K),
    ('cp_zavod','Блокпост у Заводского','checkpoint',214*_K,244*_K),
    ('plant','Механический завод','factory',212*_K,256*_K), ('plant_north','Лесопильный завод','factory',116*_K,72*_K),
    ('rail_sobor','Станция Собор','rail',160*_K,188*_K), ('rail_coast','Станция Приморская','rail',88*_K,262*_K),
    ('oil','Нефтебаза','oil',250*_K,252*_K), ('quarry','Карьер','mine',92*_K,120*_K),
    ('kolkhoz_south','Колхоз «Заря»','farm',130*_K,240*_K), ('kolkhoz_west','Колхоз «Победа»','farm',48*_K,178*_K),
    ('farm_east','Ферма у Гремячего','farm',216*_K,186*_K), ('farm_north','Ферма у Озёрного','farm',190*_K,82*_K),
    ('hutor_1','Хутор Лесничего','village',18*_K,92*_K), ('hutor_2','Хутор у Белой','village',160*_K,108*_K),
]
# Long highways get roadside filling stations.
ROADSIDE_EVERY = 42000
ROAD_WIDTH = 240
ROAD_HALF = ROAD_WIDTH // 2
ROADSIDE_KINDS = ['gas', 'gas', 'farm', 'gas']
ROADSIDE_NAMES = ['Берёзовка', 'Сосновка', 'Ивановка', 'Каменка', 'Озёрное', 'Заречье', 'Липовка', 'Покровка',
                  'Никольское', 'Ольховка', 'Дубки', 'Красный Яр', 'Михайловка', 'Вязовка', 'Горки', 'Луговое']
# Half sizes of settlements in px and how they are built: villages of izbas, towns of houses, cities of panel blocks.
TOWN_SIZES = {'city': (2800, 2500), 'town': (1500, 1350), 'village': (640, 580)}
TOWN_GATE = TOWN_SIZES['village']
POPULATION = {'city': 600, 'town': 300, 'village': 40}
TOWN_KIND = {t[0]: t[5] for t in TOWNS}
TOWN_INFECTED = {'city': 22, 'town': 13, 'village': 6}

def town_size(tid):
    """Half width and half height of a settlement in world px."""
    return TOWN_SIZES[TOWN_KIND.get(tid, 'village')]

def town_population(tid):
    return POPULATION[TOWN_KIND.get(tid, 'village')]

# Weapons. Indices 0-6 are firearms and match the hero's frames; 7-10 are melee. 'noise' is how far a shot is heard.
# mag: rounds in a magazine; reload: seconds. Switching weapons takes SWAP_TIME. Fists are always at hand.
SWAP_TIME = .5
WEAPONS = [
    {'name':'Пистолет Макарова','ammo_item':'ammo9','mag':8,'reload':1.4,'dmg':16,'cd':.45,'range':420,'width':20,'noise':900},
    {'name':'Помповое ружьё','ammo_item':'shells','mag':5,'reload':2.6,'dmg':34,'cd':.95,'range':500,'width':28,'noise':1300},
    {'name':'Автомат Калашникова','ammo_item':'ammo762','mag':30,'reload':2.3,'dmg':17,'cd':.15,'range':470,'width':20,'spread':.05,'noise':1350},
    {'name':'Обрез','ammo_item':'shells','mag':2,'reload':1.8,'dmg':44,'cd':1.1,'range':300,'width':38,'noise':1200},
    {'name':'Карабин СКС','ammo_item':'ammo762','mag':10,'reload':2.0,'dmg':38,'cd':.7,'range':600,'width':20,'noise':1350},
    {'name':'Снайперская винтовка СВД','ammo_item':'ammo54','mag':10,'reload':2.6,'dmg':72,'cd':1.6,'range':780,'width':16,'noise':1700},
    {'name':'Пулемёт ПКМ','ammo_item':'ammo54','mag':100,'reload':4.5,'dmg':15,'cd':.1,'range':520,'width':22,'spread':.08,'noise':1700},
    {'name':'Кулаки','melee':True,'dmg':7,'cd':.6,'range':46,'noise':0},
    {'name':'Нож','melee':True,'dmg':18,'cd':.55,'range':48,'noise':0},
    {'name':'Топор','melee':True,'dmg':36,'cd':1.0,'range':58,'noise':0,'chop':True},
    {'name':'Лом','melee':True,'dmg':28,'cd':.85,'range':56,'noise':0},
]
FISTS = 7
MAX_GUNS = 3          # firearms carried at once (on the back and in hand); melee weapons do not count
# Gear tiers. 'warm' lowers cold exposure, 'slots' is how many items fit, 'reduce' is the share of damage stopped.
ARMOR = [
    {'name':'Без жилета','reduce':0},
    {'name':'Разгрузка с пластинами','reduce':.2},
    {'name':'Бронежилет','reduce':.36},
]
CLOTHES = [
    {'name':'Ветровка','warm':0},
    {'name':'Ватник','warm':15},
    {'name':'Охотничья куртка','warm':30},
    {'name':'Армейский бушлат','warm':45},
]
BACKPACKS = [
    {'name':'Карманы','slots':8},
    {'name':'Самодельная сумка','slots':12},
    {'name':'Туристический рюкзак','slots':20},
    {'name':'Армейский рюкзак','slots':30},
]
# Things a person carries. Backpack items take slots ('stack' share one slot). Items with 'gear' are worn and
# items with 'weapon' are carried in hand or on the back: they never go into the backpack.
ITEMS = {
    'canned': {'stack':3,'name':'Тушёнка','desc':'Сытость +40.','food':40},
    'beans': {'stack':3,'name':'Консервированная фасоль','desc':'Сытость +35.','food':35},
    'crackers': {'stack':5,'name':'Сухари','desc':'Сытость +20, жажда +5.','food':20,'water':-5},
    'apple': {'stack':5,'name':'Яблоко','desc':'Сытость +12, жажда +8.','food':12,'water':8},
    'water': {'stack':2,'name':'Бутылка воды','desc':'Жажда утолена на 45.','water':45},
    'soda': {'stack':3,'name':'Газировка','desc':'Жажда +30, сытость +5.','water':30,'food':5},
    'tea': {'name':'Термос с чаем','desc':'Жажда +25, тепло +35.','water':25,'warmth':35},
    'bandage': {'stack':5,'name':'Бинт','desc':'Останавливает кровотечение, +5 здоровья.','hp':5,'stop_bleed':True},
    'medkit': {'name':'Аптечка','desc':'+60 здоровья и останавливает кровотечение.','hp':60,'stop_bleed':True},
    'pills': {'stack':5,'name':'Тетрациклин','desc':'Лечит отравление и заражение.','cure':True},
    'repairkit': {'name':'Ремкомплект','desc':'Чинит машину (R рядом с машиной).'},
    'canister': {'name':'Канистра бензина','desc':'+20 топлива в бак машины рядом (T).'},
    'meat_raw': {'stack':4,'name':'Сырое мясо','desc':'Сытость +25, но можно отравиться. Пожарь у костра.','food':25,'risk':.35},
    'meat': {'stack':4,'name':'Жареное мясо','desc':'Сытость +45.','food':45},
    # Materials for crafting and building: several fit in one backpack slot.
    'planks': {'name':'Доски','desc':'Для стен, мебели и ящиков. Из дерева — топором.','stack':10,'mat':True},
    'nails': {'name':'Гвозди','desc':'Для любой постройки.','stack':30,'mat':True},
    'scrap': {'name':'Металлолом','desc':'Ремонт, гвозди, ограда.','stack':10,'mat':True},
    'cloth': {'name':'Ткань','desc':'Бинты, верёвка, сумка.','stack':10,'mat':True},
    'rope': {'name':'Верёвка','desc':'Для сумок и одежды.','stack':5,'mat':True},
    'herbs': {'name':'Травы','desc':'Чай.','stack':10,'mat':True},
    'hide': {'name':'Шкура','desc':'Тёплая одежда.','stack':5,'mat':True},
    'tape': {'name':'Изолента','desc':'Ремонт машин.','stack':5,'mat':True},
    # Ammunition loads magazines on reload (X); without it a gun is useless.
    'ammo9': {'name':'Патроны 9×18','desc':'Для пистолета Макарова.','stack':40,'ammo':True},
    'shells': {'name':'Патроны 12 калибра','desc':'Для ружья и обреза.','stack':20,'ammo':True},
    'ammo762': {'name':'Патроны 7,62×39','desc':'Для автомата и карабина СКС.','stack':30,'ammo':True},
    'ammo54': {'name':'Патроны 7,62×54R','desc':'Для СВД и пулемёта ПКМ.','stack':30,'ammo':True},
    # Worn gear: picking it up puts it on, the old one falls to the ground.
    'vatnik': {'name':'Ватник','desc':'Тепло +15.','gear':('clothes', 1)},
    'hunter': {'name':'Охотничья куртка','desc':'Тепло +30.','gear':('clothes', 2)},
    'peacoat': {'name':'Армейский бушлат','desc':'Тепло +45.','gear':('clothes', 3)},
    'bag': {'name':'Самодельная сумка','desc':'12 мест.','gear':('backpack', 1)},
    'pack': {'name':'Туристический рюкзак','desc':'20 мест.','gear':('backpack', 2)},
    'army_pack': {'name':'Армейский рюкзак','desc':'30 мест.','gear':('backpack', 3)},
    'vest': {'name':'Разгрузка с пластинами','desc':'Пули теряют 20% урона.','gear':('armor', 1)},
    'armor': {'name':'Бронежилет','desc':'Пули теряют 36% урона.','gear':('armor', 2)},
    # Weapons lying on the ground or on a body.
    'w_pm': {'name':'Пистолет Макарова','desc':'Патроны 9×18.','weapon':0},
    'w_shotgun': {'name':'Помповое ружьё','desc':'Патроны 12 калибра.','weapon':1},
    'w_ak': {'name':'Автомат Калашникова','desc':'Патроны 7,62×39.','weapon':2},
    'w_sawnoff': {'name':'Обрез','desc':'Патроны 12 калибра.','weapon':3},
    'w_sks': {'name':'Карабин СКС','desc':'Патроны 7,62×39.','weapon':4},
    'w_svd': {'name':'Снайперская винтовка СВД','desc':'Патроны 7,62×54R.','weapon':5},
    'w_pkm': {'name':'Пулемёт ПКМ','desc':'Патроны 7,62×54R.','weapon':6},
    'w_knife': {'name':'Нож','desc':'Тихое оружие ближнего боя.','weapon':8},
    'w_axe': {'name':'Топор','desc':'Оружие и инструмент: рубит деревья на доски.','weapon':9},
    'w_crowbar': {'name':'Лом','desc':'Тяжёлое оружие ближнего боя.','weapon':10},
}
WEAPON_ITEM = {v['weapon']: k for k, v in ITEMS.items() if 'weapon' in v}
GEAR_ITEM = {v['gear']: k for k, v in ITEMS.items() if 'gear' in v}
# What lies in buildings: (item, weight, min, max). One table per kind of building.
LOOT_TABLES = {
    'rural': [('canned',5,1,1),('beans',4,1,1),('crackers',5,1,2),('apple',6,1,3),('water',5,1,1),('soda',3,1,1),('cloth',5,1,3),
              ('rope',3,1,1),('bandage',3,1,1),('planks',3,1,4),('nails',3,4,12),('herbs',3,1,3),('shells',2,2,5),
              ('w_axe',1.4,1,1),('w_knife',1.2,1,1),('w_shotgun',.35,1,1),('w_sawnoff',.25,1,1),('vatnik',1.2,1,1),('bag',.6,1,1)],
    'residential': [('canned',5,1,1),('beans',4,1,1),('crackers',5,1,2),('water',6,1,1),('soda',4,1,1),('cloth',4,1,2),
                    ('bandage',4,1,2),('pills',1.5,1,2),('tea',1,1,1),('tape',2,1,1),('ammo9',2.5,3,8),('shells',1,2,4),
                    ('w_knife',1,1,1),('w_crowbar',.8,1,1),('w_pm',.6,1,1),('vatnik',1,1,1),('hunter',.5,1,1),('pack',.5,1,1)],
    'medical': [('bandage',8,1,3),('pills',5,1,3),('medkit',3,1,1),('water',3,1,1),('cloth',3,1,2)],
    'industrial': [('scrap',6,1,3),('nails',5,5,15),('tape',4,1,2),('planks',4,2,5),('rope',2,1,2),('canister',1.5,1,1),
                   ('repairkit',1,1,1),('water',2,1,1),('canned',2,1,1),('w_crowbar',1.6,1,1),('w_axe',1.2,1,1),('ammo9',1,2,6)],
    'farm': [('canned',3,1,1),('apple',5,2,4),('herbs',4,1,3),('rope',3,1,2),('planks',3,2,5),('cloth',3,1,2),('shells',2.5,2,6),
             ('w_axe',1.8,1,1),('w_shotgun',.8,1,1),('w_sawnoff',.4,1,1),('hunter',.6,1,1),('meat_raw',1,1,2)],
    'gas': [('canister',4,1,1),('tape',3,1,1),('scrap',2,1,2),('crackers',3,1,2),('soda',3,1,2),('water',3,1,1),('repairkit',1,1,1),('w_crowbar',1,1,1)],
    'military': [('ammo762',6,6,20),('ammo54',3,4,12),('ammo9',3,4,12),('shells',2,3,8),('canned',3,1,1),('water',2,1,1),
                 ('bandage',3,1,2),('medkit',1,1,1),('w_ak',1.2,1,1),('w_sks',1.6,1,1),('w_svd',.3,1,1),('w_pkm',.15,1,1),
                 ('w_shotgun',.6,1,1),('w_pm',1,1,1),('vest',1,1,1),('armor',.35,1,1),('army_pack',.7,1,1),('peacoat',.6,1,1)],
}
# Buildings refill this long after their loot was spawned (DayZ-style restock), and how many items they hold.
LOOT_RESTOCK = 1500
LOOT_LIFETIME = 2400        # untouched loot disappears and spawns anew somewhere else
LOOT_RANGE = 1700           # loot is spawned in buildings this close to a player
LOOT_PER_HOUSE = {'izba': 2, 'house2': 2, 'panel': 3}
LOOT_PER_POI_PART = 2
# Crafting: 'at' is where it can be made — by hand anywhere, at a fire, or at a workbench in a camp.
RECIPES = [
    {'id':'bandage','name':'Бинт из ткани','at':'hand','needs':{'cloth':2},'makes':{'bandage':1}},
    {'id':'rope','name':'Верёвка','at':'hand','needs':{'cloth':3},'makes':{'rope':1}},
    {'id':'meat','name':'Жареное мясо','at':'fire','needs':{'meat_raw':1},'makes':{'meat':1}},
    {'id':'tea','name':'Чай на травах','at':'fire','needs':{'herbs':2,'water':1},'makes':{'tea':1}},
    {'id':'nails','name':'Гвозди','at':'bench','needs':{'scrap':1},'makes':{'nails':10}},
    {'id':'repairkit','name':'Ремкомплект','at':'bench','needs':{'scrap':3,'tape':1,'nails':5},'makes':{'repairkit':1}},
    {'id':'bag','name':'Самодельная сумка','at':'hand','needs':{'cloth':5,'rope':2},'gear':('backpack',1)},
    {'id':'hunter','name':'Куртка из шкур','at':'bench','needs':{'hide':4,'cloth':4,'rope':2},'gear':('clothes',2)},
    {'id':'sawnoff','name':'Обрез из ружья','at':'bench','needs':{'tape':1},'weapon_from':(1, 3)},
]
# Pieces of a camp. Open-ground camps stand inside a square fence; a camp in an abandoned house uses its walls.
CAMP_PARTS = {
    'fire': {'name':'Костёр','house_name':'Печка','needs':{'planks':2},'hp':150,'desc':'Тепло, готовка, чай. Рядом заживают раны.'},
    'stash': {'name':'Ящик','needs':{'planks':6,'nails':10},'hp':300,'desc':'Хранит вещи (40 мест). Чужие откроют, если пробьют стены.'},
    'bench': {'name':'Верстак','needs':{'planks':8,'nails':12,'scrap':4},'hp':250,'desc':'Гвозди, ремкомплекты, одежда, обрез.'},
    'collector': {'name':'Сборник дождевой воды','needs':{'scrap':3,'cloth':2},'hp':120,'desc':'Чистая вода раз в две минуты.'},
    'wall': {'name':'Частокол','needs':{'planks':5,'nails':8},'hp':400,'desc':'Секция ограды. Восемь секций и ворота закрывают лагерь.'},
    'gate': {'name':'Ворота','house_name':'Дверь','needs':{'planks':6,'nails':10,'scrap':2},'hp':500,'desc':'Пропускает тебя и клан, остальных — нет.'},
}
CAMP_HALF = 100           # half size of an open-ground camp's fence
CAMP_STASH_SLOTS = 40
HOUSE_WALL_HP = 900
BODY_TIME = 1800          # a dead player's body with everything on it lies this long
# Computer-controlled creatures. Infected hunt by sight and sound; animals live in the forest.
NPC_TYPES = {
    'infected': {'name':'Заражённый','hp':60,'speed':62,'run':205,'dmg':7,'range':40,'cd':1.3,'melee':True,'sight':430,'bleed':.25},
    'infected_soldier': {'name':'Заражённый солдат','hp':100,'speed':62,'run':200,'dmg':9,'range':42,'cd':1.2,'melee':True,'sight':450,'bleed':.3},
    'wolf': {'name':'Волк','hp':40,'speed':178,'dmg':9,'range':34,'cd':1.0,'melee':True,'aggro':430,'meat':1},
    'bear': {'name':'Медведь','hp':170,'speed':142,'dmg':26,'range':46,'cd':1.6,'melee':True,'aggro':300,'meat':3},
    'boar': {'name':'Кабан','hp':60,'speed':160,'dmg':12,'range':34,'cd':1.2,'melee':True,'aggro':230,'meat':2},
    'elk': {'name':'Лось','hp':75,'speed':195,'dmg':0,'range':0,'cd':0,'passive':True,'flee':400,'meat':3},
}
NPC_FACTION = {'infected':'infected','infected_soldier':'infected','wolf':'wild','bear':'wild','boar':'wild','elk':'game'}
WILDLIFE = {'mixed':['boar','elk','wolf','elk','boar'],'taiga':['wolf','bear','elk','elk','boar']}
# Looks of the infected, cells of web/assets/characters.png drawn darker: civilians, workers and soldiers.
INFECTED_LOOKS = {'infected':[0,1,2,10,13,18],'infected_soldier':[6,7,8,9]}
MAX_INFECTED = 140
# Cars stand in the world and belong to nobody. Drawn in web/assets/cars.png (one 128 x 224 cell each, front up).
# max — top speed on asphalt (px/s), accel — px/s², offroad — share of top speed off the road, grip — how fast
# sideways sliding dies out, steer — steering lock (rad), armor — divides damage, len/wid — body size in world px.
CARS = [
    {'id':'uaz','name':'УАЗ-469','max':360,'accel':240,'offroad':.86,'grip':7.0,'steer':.62,'armor':1.5,'tank':60,'len':93,'wid':54,'door':.18,'seats':4,'color':'#59603f'},
    {'id':'bukhanka','name':'УАЗ «Буханка»','max':330,'accel':205,'offroad':.8,'grip':6.0,'steer':.55,'armor':1.7,'tank':70,'len':100,'wid':56,'door':.12,'seats':8,'color':'#7d8b93'},
    {'id':'vaz2101','name':'ВАЗ-2101','max':400,'accel':270,'offroad':.52,'grip':7.4,'steer':.66,'armor':1.0,'tank':39,'len':92,'wid':50,'door':.12,'seats':4,'color':'#d9cfb2'},
    {'id':'vaz2107','name':'ВАЗ-2107','max':420,'accel':290,'offroad':.52,'grip':7.6,'steer':.66,'armor':1.05,'tank':39,'len':93,'wid':52,'door':.12,'seats':4,'color':'#3f5f8c'},
    {'id':'vaz2109','name':'ВАЗ-2109','max':445,'accel':330,'offroad':.5,'grip':8.2,'steer':.7,'armor':.95,'tank':43,'len':86,'wid':53,'door':.12,'seats':4,'color':'#9c3e34'},
    {'id':'niva','name':'«Нива»','max':380,'accel':290,'offroad':.92,'grip':8.0,'steer':.7,'armor':1.25,'tank':42,'len':81,'wid':56,'door':.16,'seats':4,'color':'#3e5a3a'},
    {'id':'moskvich','name':'«Москвич»','max':385,'accel':250,'offroad':.55,'grip':7.0,'steer':.64,'armor':1.0,'tank':46,'len':89,'wid':52,'door':.12,'seats':4,'color':'#c79a52'},
    {'id':'volga','name':'ГАЗ-24 «Волга»','max':455,'accel':270,'offroad':.48,'grip':6.6,'steer':.6,'armor':1.3,'tank':55,'len':96,'wid':54,'door':.12,'seats':4,'color':'#2a2826'},
]
WORLD_CARS = 28           # cars standing in the region; a wrecked one is replaced somewhere else after a while
CAR_RESPAWN = 1200
# A fresh character: what they wake up with on the shore.
START_ITEMS = {'bandage':1, 'apple':1}
RESPAWN_TIME = 7
WEATHER = {'clear':'Ясно', 'rain':'Дождь', 'fog':'Туман', 'storm':'Гроза', 'snow':'Снег'}
DAY_SECONDS = 1440 / 1.4           # one in-game day in real seconds

def config():
    return {'version':VERSION,'width':WORLD_SIZE[0],'height':WORLD_SIZE[1],'scale':WORLD_SCALE,'region_name':REGION_NAME,
            'max_players':MAX_PLAYERS,'roads':ROADS,'regions':REGIONS,'rivers':RIVERS,'lakes':LAKES,'hills':HILLS,
            'poi_kinds':POI_KINDS,'weapons':WEAPONS,'fists':FISTS,'max_guns':MAX_GUNS,'armor':ARMOR,'npc_types':NPC_TYPES,
            'weather_names':WEATHER,'day_seconds':DAY_SECONDS,'side_colors':SIDE_COLORS,'infected_looks':INFECTED_LOOKS,
            'recipes':RECIPES,'road_width':ROAD_WIDTH,'camp_parts':CAMP_PARTS,'camp_half':CAMP_HALF,'stash_slots':CAMP_STASH_SLOTS,
            'cars':CARS,'items':ITEMS,'clothes':CLOTHES,'backpacks':BACKPACKS,'weapon_item':WEAPON_ITEM,
            'landmarks':{},'respawn_time':RESPAWN_TIME,
            'towns':[dict(id=t[0],name=t[1],x=t[2],y=t[3],region=t[4],kind=t[5]) for t in TOWNS]}
