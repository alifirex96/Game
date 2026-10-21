"""Static game rules and the schematic map of Russia. Python 3.7+, standard library only."""
VERSION = '0.5.0'
# Map coordinates below are written at 1:1 and stretched by WORLD_SCALE, so settlements are far apart
# while roads and rivers keep their real width. At 24 neighbouring towns are 25–78 thousand px apart:
# one to three minutes by car, several minutes on foot.
WORLD_SCALE = 24
WORLD_SIZE = (20000 * WORLD_SCALE, 10000 * WORLD_SCALE)
# Everyone plays for themselves. Each player is a side with a home settlement; computer clans are sides too.
MAX_PLAYERS = 25
SIDE_COLORS = ['#e7a568', '#7fb2d0', '#a7c46a', '#d79cb7', '#e0d46a', '#9b8fd6', '#6ad0b8', '#f08a6a', '#c9c9c9', '#b98a5a',
               '#5fa0e0', '#e06a9a', '#8ad06a', '#d0a0e0', '#e0b0a0', '#70c0c0', '#c0c060', '#a0a0f0', '#f0c040', '#60e090',
               '#e07050', '#90b0d0', '#d090c0', '#b0d090', '#f0e0a0', '#80a080', '#c08060']
# Computer clans: id, name, colour, home, fighter type, preferred capture method.
AI_SIDES = [('ai_scar', 'Банда Шрама', '#c0503c', 'pervouralsk', 'raider', 'assault'),
            ('ai_dawn', 'Община «Рассвет»', '#5f9a7a', 'tyumen', 'ranger', 'talk')]
RESOURCES = {'wood': 'Древесина', 'stone': 'Камень', 'metal': 'Металл',
             'food': 'Припасы', 'fuel': 'Топливо'}
# The first fifteen settlements are the 0.1 map; ids and coordinates stay stable for old saves.
TOWNS = [
    ('petersburg', 'Санкт-Петербург', 1500, 1600, 'Северо-Запад'),
    ('moscow', 'Москва', 1800, 4000, 'Центральная Россия'),
    ('nizhny', 'Нижний Новгород', 3300, 3850, 'Поволжье'),
    ('kazan', 'Казань', 4800, 4500, 'Поволжье'),
    ('perm', 'Пермь', 5700, 2200, 'Урал'),
    ('pervouralsk', 'Первоуральск', 6000, 3600, 'Урал'),
    ('shabrovsky', 'Шабровский', 7300, 5200, 'Урал'),
    ('ekaterinburg', 'Екатеринбург', 7900, 3650, 'Урал'),
    ('tyumen', 'Тюмень', 9400, 3500, 'Западная Сибирь'),
    ('novosibirsk', 'Новосибирск', 11100, 5200, 'Сибирь'),
    ('krasnoyarsk', 'Красноярск', 13000, 4100, 'Сибирь'),
    ('irkutsk', 'Иркутск', 14600, 5700, 'Прибайкалье'),
    ('yakutsk', 'Якутск', 16400, 2500, 'Якутия'),
    ('khabarovsk', 'Хабаровск', 17800, 5900, 'Дальний Восток'),
    ('vladivostok', 'Владивосток', 17800, 7900, 'Дальний Восток'),
    # 0.2: the North, more of the Urals and the road to Magadan.
    ('murmansk', 'Мурманск', 2700, 450, 'Север'),
    ('arkhangelsk', 'Архангельск', 3700, 1300, 'Север'),
    ('vorkuta', 'Воркута', 8000, 900, 'Север'),
    ('norilsk', 'Норильск', 12400, 900, 'Крайний Север'),
    ('tagil', 'Нижний Тагил', 7100, 2300, 'Урал'),
    ('revda', 'Ревда', 6300, 4600, 'Урал'),
    ('polevskoy', 'Полевской', 6600, 6300, 'Урал'),
    ('omsk', 'Омск', 10200, 4600, 'Западная Сибирь'),
    ('magadan', 'Магадан', 19300, 3400, 'Дальний Восток'),
]
ROADS = [('petersburg','moscow'),('moscow','nizhny'),('nizhny','kazan'),
         ('kazan','pervouralsk'),('pervouralsk','perm'),('pervouralsk','ekaterinburg'),
         ('shabrovsky','ekaterinburg'),
         ('ekaterinburg','tyumen'),('tyumen','omsk'),('omsk','novosibirsk'),
         ('novosibirsk','krasnoyarsk'),('krasnoyarsk','irkutsk'),
         ('irkutsk','yakutsk'),('irkutsk','khabarovsk'),('khabarovsk','vladivostok'),
         ('petersburg','murmansk'),('moscow','arkhangelsk'),('perm','tagil'),
         ('tagil','ekaterinburg'),('tagil','vorkuta'),('pervouralsk','revda'),
         ('revda','shabrovsky'),('shabrovsky','polevskoy'),('krasnoyarsk','norilsk'),
         ('yakutsk','magadan')]
# Climate: visual biome and how harsh the weather may get.
REGIONS = {
    'Северо-Запад': {'biome':'mixed','cold':1}, 'Центральная Россия': {'biome':'mixed','cold':0},
    'Поволжье': {'biome':'steppe','cold':0}, 'Урал': {'biome':'ural','cold':1},
    'Западная Сибирь': {'biome':'snowtaiga','cold':2}, 'Сибирь': {'biome':'snowtaiga','cold':2},
    'Прибайкалье': {'biome':'snowtaiga','cold':2}, 'Якутия': {'biome':'tundra','cold':3},
    'Дальний Восток': {'biome':'taiga','cold':1}, 'Север': {'biome':'tundra','cold':3},
    'Крайний Север': {'biome':'tundra','cold':3},
}
# Water blocks vehicles except on bridges; people wade slowly. [name, width, points]
RIVERS = [
    ['Волга', 110, [(600,3000),(1300,3250),(2400,3200),(3000,3150),(3900,3300),(4100,3700),
                    (4050,4300),(4050,5000),(4300,6000),(4100,7200),(4500,8600),(4300,9990)]],
    ['Кама', 80, [(5150,1400),(4950,2300),(5050,3200),(4600,3700),(4100,3850)]],
    ['Исеть', 55, [(8450,4150),(9000,4300),(9500,5300),(9300,6500)]],
    ['Иртыш', 90, [(10500,8000),(10300,5600),(9300,4500),(8700,3000),(8900,1800),(10150,2050)]],
    ['Обь', 120, [(12000,7500),(11500,6200),(11800,5400),(11700,4200),(11000,3000),(10200,2000),(10000,500),(10200,0)]],
    ['Енисей', 130, [(13300,7000),(13500,5000),(13700,4100),(13300,2600),(12900,1500),(13100,700),(12800,0)]],
    ['Ангара', 90, [(15200,5700),(14600,4800),(13900,4400),(13700,4100)]],
    ['Лена', 110, [(15200,4300),(15500,3400),(15650,2500),(15900,1400),(16400,400),(16300,0)]],
    ['Амур', 120, [(15000,8400),(16300,7900),(17000,6900),(17150,6200),(17400,5100),(18200,4500),(19100,4400),(19990,4100)]],
]
LAKES = [
    ['Ладожское озеро', [(2250,1200),(2650,1100),(2950,1400),(2800,1800),(2350,1780),(2200,1450)]],
    ['Байкал', [(15300,6000),(15600,5500),(16200,4900),(16600,4500),(16800,4600),(16300,5300),(15800,5900),(15400,6300)]],
]
# Ridges are drawn as rocky ground; they never block movement.
HILLS = [('Уральские горы', 6650, 3000, 380, 2600), ('Хибины', 2300, 250, 500, 180),
         ('Саяны', 13900, 7200, 1200, 450), ('Верхоянский хребет', 17500, 1800, 1300, 500),
         ('Сихотэ-Алинь', 18900, 7000, 380, 1400)]
# Abandoned places worth exploring. Caches restock; marauders gather nearby.
_S = WORLD_SCALE
TOWNS = [(t[0], t[1], t[2] * _S, t[3] * _S, t[4]) for t in TOWNS]
RIVERS = [[n, w, [(x * _S, y * _S) for x, y in pts]] for n, w, pts in RIVERS]
LAKES = [[n, [(x * _S, y * _S) for x, y in pts]] for n, pts in LAKES]
HILLS = [(n, x * _S, y * _S, rx * _S, ry * _S) for n, x, y, rx, ry in HILLS]
POI_KINDS = {
    'factory': {'name':'Заброшенный завод','loot':{'metal':8,'stone':3},'guards':3},
    'gas': {'name':'Заправка','loot':{'fuel':8,'food':2},'guards':1},
    'military': {'name':'Воинская часть','loot':{'metal':11,'fuel':4},'guards':4},
    'farm': {'name':'Брошенный колхоз','loot':{'food':10,'wood':3},'guards':1},
    'village': {'name':'Пустая деревня','loot':{'wood':6,'food':4},'guards':1},
    'oil': {'name':'Нефтебаза','loot':{'fuel':12},'guards':3},
    'mine': {'name':'Рудник','loot':{'stone':8,'metal':5},'guards':2},
    'rail': {'name':'Железнодорожная станция','loot':{'metal':5,'food':5,'fuel':3},'guards':2},
}
POIS = [
    ('revda_plant','Медеплавильный завод','factory',7100,4150),('sysert','Сысерть','village',8300,4900),
    ('aramil','Арамиль','gas',8950,5000),('chusovoy','Чусовой','factory',6810,3110),
    ('kungur','Кунгур','village',4600,2700),('miass','Миасс','mine',6400,5500),
    ('zlatoust','Златоуст','factory',5600,5900),('elan','Воинская часть у Елани','military',8900,5800),
    ('irbit','Ирбит','farm',9100,2700),('tobolsk','Тобольск','oil',9590,2260),
    ('barabinsk','Барабинск','farm',10700,6300),('tomsk','Нефтебаза под Томском','oil',12300,3300),
    ('kansk','Канск','village',13810,5640),('angarsk','Ангарск','factory',14100,6600),
    ('slyudyanka','Слюдянка','village',14800,7000),('bodaybo','Бодайбо','mine',16200,3800),
    ('mirny','Мирный','mine',14600,2700),('birobidzhan','Биробиджан','village',16500,6400),
    ('ussuriysk','Уссурийск','farm',17000,8700),('nakhodka','Находка','gas',18700,8500),
    ('tver','Тверь','village',1100,2700),('vladimir','Владимир','factory',2700,4700),
    ('vologda','Вологда','farm',2900,2400),('kotlas','Котлас','rail',4700,800),
    ('ukhta','Ухта','oil',6300,1200),('pechora','Печора','village',7000,700),
    ('dudinka','Дудинка','gas',11600,1700),('cheboksary','Чебоксары','farm',3500,5300),
    ('izhevsk','Ижевск','factory',5450,5230),('chelyabinsk','Челябинск','factory',7500,7000),
    ('kurgan','Курган','farm',9000,7200),('orenburg','Оренбург','gas',5800,7600),
    ('samara','Самара','rail',3500,7000),('yeniseysk','Енисейск','rail',14300,3300),
]
POIS = [(p[0], p[1], p[2], p[3] * _S, p[4] * _S) for p in POIS]
# Long highways get roadside stops of their own: filling stations, villages, farms and checkpoints.
ROADSIDE_EVERY = 18000
ROADSIDE_KINDS = ['gas', 'village', 'gas', 'farm', 'village', 'military', 'gas', 'village']
ROADSIDE_NAMES = ['Берёзовка', 'Сосновка', 'Ивановка', 'Каменка', 'Озёрное', 'Заречье', 'Липовка', 'Покровка',
                  'Никольское', 'Ольховка', 'Дубки', 'Красный Яр', 'Михайловка', 'Вязовка', 'Горки', 'Луговое',
                  'Борки', 'Новосёлки', 'Ключи', 'Таёжный', 'Ельники', 'Кедровка', 'Сухой Лог', 'Белый Ключ']
BUILDINGS = {
    'depot': {'name':'Опорный пункт','cost':{'wood':24,'stone':14,'metal':8},
              'desc':'Центр поселения и штаб обороны. Его уровень открывает улучшения остальных зданий.','workers':0},
    'house': {'name':'Жилой дом','cost':{'wood':20,'stone':14,'metal':6},
              'desc':'За каждый уровень в поселение возвращаются восемь жителей.','workers':0},
    'sawmill': {'name':'Лесопилка','cost':{'wood':18,'stone':12,'metal':8},
                'desc':'Бригада заготавливает древесину для общего запаса фракции.','workers':3,'output':['wood',2]},
    'quarry': {'name':'Карьер','cost':{'wood':20,'stone':16,'metal':10},
               'desc':'Камень для ремонта домов и укреплений.','workers':3,'output':['stone',2]},
    'workshop': {'name':'Мастерская','cost':{'wood':26,'stone':20,'metal':16},
                 'desc':'Восстанавливает металл и изготавливает оружие и броню.','workers':3,'output':['metal',2]},
    'farm': {'name':'Ферма','cost':{'wood':16,'stone':10,'metal':5},
             'desc':'Теплицы и огороды: продовольствие для рабочих, походов и переговоров.','workers':2,'output':['food',3]},
    'garage': {'name':'Гараж','cost':{'wood':24,'stone':16,'metal':16},
               'desc':'Добывает топливо, чинит машины. Гараж убежища ускоряет и укрепляет машины фракции.','workers':2,'output':['fuel',1]},
    'warehouse': {'name':'Склад','cost':{'wood':22,'stone':18,'metal':8},
                  'desc':'Каждый уровень увеличивает предельный запас каждого ресурса фракции на 250.','workers':1},
    'radio': {'name':'Радиостанция','cost':{'wood':30,'stone':24,'metal':25},
              'desc':'Связь помогает переговорам: +5% за уровень. Радиостанция второго уровня нужна для победы.','workers':0},
    'guard': {'name':'Сторожевая вышка','cost':{'wood':22,'stone':16,'metal':14},
              'desc':'Снижает шанс чужого захвата, вышка стреляет по врагам и мародёрам рядом с поселением.','workers':0},
}
# Buildings surround an open square. Coordinates are relative to the town centre.
# The cross streets (x = 0 and y = 0) stay free: they continue the highways to the square.
SLOTS = [('depot',-185,-150),('house',145,-155),('sawmill',-360,100),
         ('quarry',350,100),('workshop',-185,185),('farm',160,190),
         ('garage',-360,285),('radio',350,285),('guard',95,-340),('warehouse',160,335)]
TOWN_GATE = (480, 420)             # the smallest town's half size; bigger towns grow with their population
# Real population in thousands: it decides how far a city spreads (blocks, streets, abandoned houses).
POPULATION = {'petersburg':5600,'moscow':13000,'nizhny':1230,'kazan':1310,'perm':1030,'pervouralsk':115,
              'shabrovsky':2,'ekaterinburg':1540,'tyumen':850,'novosibirsk':1630,'krasnoyarsk':1200,'irkutsk':620,
              'yakutsk':360,'khabarovsk':610,'vladivostok':600,'murmansk':270,'arkhangelsk':300,'vorkuta':55,
              'norilsk':175,'tagil':330,'revda':60,'polevskoy':60,'omsk':1110,'magadan':90}

def town_size(tid):
    """Half width and half height of a settlement in world px."""
    pop = POPULATION.get(tid, 60)
    half = int(max(TOWN_GATE[0], min(2600, 540 * (pop / 60.0) ** .28)))
    return half, int(max(TOWN_GATE[1], half * .9))
# Every settlement has a real landmark of the city or its surroundings in the north-west block.
LANDMARK_POS = (-345, -290)
LANDMARKS = {
    'petersburg': ('Адмиралтейство', 170, 110), 'moscow': ('Спасская башня', 150, 130),
    'nizhny': ('Дмитриевская башня', 170, 120), 'kazan': ('Мечеть Кул-Шариф', 160, 130),
    'perm': ('Спасо-Преображенский собор', 150, 120), 'pervouralsk': ('Обелиск «Европа — Азия»', 140, 120),
    'shabrovsky': ('Тальков камень', 170, 130), 'ekaterinburg': ('Храм на Крови', 150, 130),
    'tyumen': ('Мост влюблённых', 170, 120), 'novosibirsk': ('Оперный театр', 170, 130),
    'krasnoyarsk': ('Часовня Параскевы Пятницы', 140, 120), 'irkutsk': ('Ледокол «Ангара»', 170, 110),
    'yakutsk': ('Башня Якутского острога', 140, 120), 'khabarovsk': ('Амурский утёс', 160, 130),
    'vladivostok': ('Золотой мост', 170, 120), 'murmansk': ('Памятник «Алёша»', 130, 120),
    'arkhangelsk': ('Церковь Вознесения, Малые Корелы', 140, 120), 'vorkuta': ('Копёр шахты «Воркутинская»', 140, 120),
    'norilsk': ('Трубы Медного завода', 150, 120), 'tagil': ('Памятник танку Т-34', 140, 110),
    'revda': ('Плотина Ревдинского пруда', 170, 110), 'polevskoy': ('Хозяйка Медной горы', 140, 120),
    'omsk': ('Тарские ворота', 160, 100), 'magadan': ('Маска скорби', 140, 130),
}
BUILD_TIME = [12, 28, 50]          # seconds to finish level 1, 2, 3
STORAGE_BASE = 320
STORAGE_PER_WAREHOUSE = 250
# Indices 0-2 are the 0.2 weapons and stay stable for old saves. 'price' is in coins (shop),
# 'cost' in faction resources (workshop), 'level' is the character level needed to buy.
# mag: rounds before an automatic reload; reload: seconds. Switching weapons takes SWAP_TIME.
SWAP_TIME = .5
WEAPONS = [
    {'name':'Пистолет Макарова','ammo_item':'ammo9','mag':8,'reload':1.4,'dmg':16,'cd':.45,'range':420,'ammo':.12,'cost':{},'price':0,'level':1,'width':20},
    {'name':'Охотничье ружьё','ammo_item':'shells','mag':2,'reload':2.0,'dmg':32,'cd':.95,'range':540,'ammo':.25,'cost':{'metal':30,'wood':12},'workshop':1,'price':180,'level':1,'width':28},
    {'name':'Автомат Калашникова','ammo_item':'ammo762','mag':30,'reload':2.3,'dmg':13,'cd':.15,'range':470,'ammo':.08,'cost':{'metal':70,'fuel':12},'workshop':2,'price':630,'level':6,'width':20,'spread':.05},
    {'name':'Обрез','ammo_item':'shells','mag':2,'reload':1.8,'dmg':44,'cd':1.1,'range':300,'ammo':.3,'price':120,'level':2,'width':38},
    {'name':'Карабин СКС','ammo_item':'ammo762','mag':10,'reload':2.0,'dmg':38,'cd':.7,'range':600,'ammo':.2,'price':360,'level':4,'width':20},
    {'name':'Снайперская винтовка СВД','ammo_item':'ammo54','mag':10,'reload':2.6,'dmg':72,'cd':1.6,'range':780,'ammo':.4,'price':1020,'level':12,'width':16},
    {'name':'Пулемёт ПКМ','ammo_item':'ammo54','mag':100,'reload':4.5,'dmg':15,'cd':.1,'range':520,'ammo':.1,'price':1425,'level':18,'width':22,'spread':.08},
]
ARMOR = [
    {'name':'Куртка','reduce':0,'cost':{},'price':0,'level':1},
    {'name':'Разгрузка с пластинами','reduce':.2,'cost':{'metal':26,'food':6},'workshop':1,'price':240,'level':3},
    {'name':'Бронежилет','reduce':.36,'cost':{'metal':64,'stone':10},'workshop':3,'price':780,'level':10},
]
# Shop goods besides weapons and armor. Coins are earned for quests and story chapters.
# Survival gear bought for coins. 'warm' lowers cold exposure, 'slots' is how many items fit.
CLOTHES = [
    {'name':'Ветровка','warm':0,'price':0,'level':1},
    {'name':'Ватник','warm':15,'price':135,'level':1},
    {'name':'Овчинный тулуп','warm':30,'price':330,'level':4},
    {'name':'Арктический комплект','warm':45,'price':720,'level':10},
]
BACKPACKS = [
    {'name':'Карманы','slots':8,'price':0,'level':1},
    {'name':'Сумка через плечо','slots':12,'price':90,'level':1},
    {'name':'Туристический рюкзак','slots':20,'price':270,'level':3},
    {'name':'Армейский рюкзак','slots':30,'price':600,'level':8},
]
# Personal items: each takes one slot in the backpack.
ITEMS = {
    'canned': {'stack':3,'name':'Тушёнка','desc':'Сытость +40.','price':20,'food':40},
    'crackers': {'stack':5,'name':'Сухари','desc':'Сытость +20, жажда +5.','price':10,'food':20,'water':-5},
    'water': {'stack':2,'name':'Бутылка воды','desc':'Жажда утолена на 45.','price':15,'water':45},
    'tea': {'name':'Термос с чаем','desc':'Жажда +25, тепло +35.','price':40,'water':25,'warmth':35},
    'bandage': {'stack':5,'name':'Бинт','desc':'Останавливает кровотечение, +5 здоровья.','price':20,'hp':5,'stop_bleed':True},
    'medkit': {'name':'Аптечка','desc':'+60 здоровья и останавливает кровотечение.','price':50,'hp':60,'stop_bleed':True},
    'pills': {'stack':5,'name':'Антибиотики','desc':'Лечат отравление.','price':45,'cure':True},
    'repairkit': {'name':'Ремкомплект','desc':'Чинит машину в любом месте (R рядом с машиной).','price':70},
    'canister': {'name':'Канистра бензина','desc':'+20 топлива в бак твоей машины (T рядом с машиной).','price':40},
    'meat_raw': {'stack':4,'name':'Сырое мясо','desc':'Сытость +25, но можно отравиться. Пожарь у костра своего поселения.','price':0,'food':25,'risk':.35},
    'meat': {'stack':4,'name':'Жареное мясо','desc':'Сытость +45.','price':0,'food':45},
    # Materials for crafting: several fit in one backpack slot ('stack').
    'planks': {'name':'Доски','desc':'Для стен, мебели и ящиков.','price':6,'stack':10,'mat':True},
    'nails': {'name':'Гвозди','desc':'Для любой постройки.','price':2,'stack':30,'mat':True},
    'scrap': {'name':'Металлолом','desc':'Из него делают патроны, гвозди, броню.','price':8,'stack':10,'mat':True},
    'cloth': {'name':'Ткань','desc':'Бинты, верёвка, одежда, спальник.','price':6,'stack':10,'mat':True},
    'rope': {'name':'Верёвка','desc':'Для одежды, рюкзаков и брони.','price':10,'stack':5,'mat':True},
    'gunpowder': {'name':'Порох','desc':'Для патронов на верстаке.','price':15,'stack':20,'mat':True},
    'herbs': {'name':'Травы','desc':'Чай и аптечки.','price':5,'stack':10,'mat':True},
    'hide': {'name':'Шкура','desc':'Тёплая одежда и рюкзаки.','price':12,'stack':5,'mat':True},
    'tape': {'name':'Изолента','desc':'Ремонт машин и самодельное оружие.','price':10,'stack':5,'mat':True},
    # Ammunition loads magazines on reload (X); without it a gun is useless.
    'ammo9': {'name':'Патроны 9×18','desc':'Для пистолета Макарова.','price':2,'stack':40,'ammo':True},
    'shells': {'name':'Патроны 12 калибра','desc':'Для ружья и обреза.','price':4,'stack':20,'ammo':True},
    'ammo762': {'name':'Патроны 7,62×39','desc':'Для автомата и карабина СКС.','price':3,'stack':30,'ammo':True},
    'ammo54': {'name':'Патроны 7,62×54R','desc':'Для СВД и пулемёта ПКМ.','price':5,'stack':30,'ammo':True},
}
# Where materials turn up: ruins by kind, houses, animals.
POI_MATERIALS = {
    'factory':['scrap','nails','tape','gunpowder','scrap'], 'gas':['tape','scrap','rope'], 'military':['ammo762','gunpowder','cloth','ammo9','ammo54'],
    'farm':['rope','cloth','planks','herbs'], 'village':['planks','cloth','herbs','nails','shells'], 'oil':['gunpowder','scrap','tape'],
    'mine':['scrap','gunpowder','nails'], 'rail':['nails','scrap','cloth','planks'],
}
HOUSE_FINDS = ['cloth','nails','planks','rope','tape','herbs','scrap','ammo9','cloth','canned','water','bandage','crackers','gunpowder','shells','pills']
HOUSE_SEARCH_COOLDOWN = 900
# Crafting: 'at' is where it can be made — by hand anywhere, at a fire, or at a workbench in a camp.
# 'res' takes the side's shared resources; 'gear' sets equipment; 'part' builds a piece of the camp.
RECIPES = [
    {'id':'bandage','name':'Бинт','at':'hand','needs':{'cloth':2},'makes':{'bandage':1}},
    {'id':'rope','name':'Верёвка','at':'hand','needs':{'cloth':3},'makes':{'rope':1}},
    {'id':'meat','name':'Жареное мясо','at':'fire','needs':{'meat_raw':1},'makes':{'meat':1}},
    {'id':'tea','name':'Чай на травах','at':'fire','needs':{'herbs':2,'water':1},'makes':{'tea':1}},
    {'id':'planks','name':'Доски из брёвен','at':'bench','res':{'wood':4},'makes':{'planks':2}},
    {'id':'scrap','name':'Металлолом из металла','at':'bench','res':{'metal':3},'makes':{'scrap':2}},
    {'id':'nails','name':'Гвозди','at':'bench','needs':{'scrap':1},'makes':{'nails':10}},
    {'id':'gunpowder','name':'Порох из селитры и топлива','at':'bench','needs':{'herbs':1},'res':{'fuel':4},'makes':{'gunpowder':1}},
    {'id':'ammo9','name':'Патроны 9×18 ×10','at':'bench','needs':{'gunpowder':1,'scrap':1},'makes':{'ammo9':10}},
    {'id':'shells','name':'Патроны 12 калибра ×6','at':'bench','needs':{'gunpowder':1,'scrap':1,'cloth':1},'makes':{'shells':6}},
    {'id':'ammo762','name':'Патроны 7,62×39 ×10','at':'bench','needs':{'gunpowder':2,'scrap':2},'makes':{'ammo762':10}},
    {'id':'ammo54','name':'Патроны 7,62×54R ×10','at':'bench','needs':{'gunpowder':3,'scrap':2},'makes':{'ammo54':10}},
    {'id':'medkit','name':'Аптечка','at':'bench','needs':{'bandage':2,'herbs':3},'makes':{'medkit':1}},
    {'id':'repairkit','name':'Ремкомплект','at':'bench','needs':{'scrap':3,'tape':1,'nails':5},'makes':{'repairkit':1}},
    {'id':'canister','name':'Канистра','at':'bench','needs':{'scrap':5},'makes':{'canister':1}},
    {'id':'sawnoff','name':'Обрез','at':'bench','level':2,'needs':{'scrap':10,'planks':3,'nails':6,'tape':2},'gear':('weapon',3)},
    {'id':'vest','name':'Разгрузка с пластинами','at':'bench','level':3,'needs':{'scrap':10,'cloth':6,'rope':2},'gear':('armor',1)},
    {'id':'vatnik','name':'Ватник','at':'bench','needs':{'cloth':8,'rope':1},'gear':('clothes',1)},
    {'id':'tulup','name':'Овчинный тулуп','at':'bench','level':4,'needs':{'hide':4,'cloth':4,'rope':2},'gear':('clothes',2)},
    {'id':'bag','name':'Сумка','at':'bench','needs':{'cloth':5,'rope':2},'gear':('backpack',1)},
    {'id':'pack','name':'Туристический рюкзак','at':'bench','level':3,'needs':{'cloth':8,'rope':4,'hide':2},'gear':('backpack',2)},
]
# Pieces of a camp. Open-ground camps stand inside a square fence; a camp in an abandoned house uses its walls.
CAMP_PARTS = {
    'fire': {'name':'Костёр','house_name':'Печка','needs':{'planks':2,'scrap':1},'hp':150,'desc':'Тепло, готовка, чай. Рядом заживают раны.'},
    'bed': {'name':'Спальник','needs':{'cloth':4,'planks':2},'hp':120,'desc':'После гибели очнёшься здесь.'},
    'stash': {'name':'Ящик','needs':{'planks':6,'nails':10},'hp':300,'desc':'Хранит вещи (40 мест) и монеты. Чужие откроют, если пробьют стены.'},
    'bench': {'name':'Верстак','needs':{'planks':8,'nails':12,'scrap':4},'hp':250,'desc':'Патроны, снаряжение, ремкомплекты.'},
    'collector': {'name':'Сборник дождевой воды','needs':{'scrap':3,'cloth':2},'hp':120,'desc':'Чистая вода раз в две минуты.'},
    'wall': {'name':'Частокол','needs':{'planks':5,'nails':8},'hp':400,'desc':'Секция ограды. Восемь секций и ворота закрывают лагерь.'},
    'gate': {'name':'Ворота','house_name':'Дверь','needs':{'planks':6,'nails':10,'scrap':2},'hp':500,'desc':'Пропускает тебя и клан, остальных — нет.'},
}
CAMP_HALF = 100           # half size of an open-ground camp's fence
CAMP_STASH_SLOTS = 40
HOUSE_WALL_HP = 900
BODY_TIME = 900           # a body with its backpack lies this long
LOOT_ITEMS = ['canned', 'crackers', 'water', 'water', 'bandage', 'crackers', 'pills', 'canned', 'tea', 'medkit', 'canister']
# Shop goods paid in coins that go straight to the faction stock.
SHOP_ITEMS = {
    'supplies': {'name':'Ящик снабжения','desc':'+20 припасов и +15 топлива в запас фракции.','price':90},
    'materials': {'name':'Стройматериалы','desc':'+30 древесины, +25 камня, +15 металла фракции.','price':135},
}
STORY_COINS = 120
NPC_TYPES = {
    'marauder': {'name':'Мародёр','hp':45,'speed':118,'dmg':8,'range':330,'cd':1.5,'loot':{'metal':3,'food':2}},
    'raider': {'name':'Боец бандитов','hp':70,'speed':125,'dmg':11,'range':360,'cd':1.2,'loot':{'metal':4}},
    'ranger': {'name':'Дружинник','hp':70,'speed':125,'dmg':11,'range':360,'cd':1.2,'loot':{'food':4}},
    'militia': {'name':'Ополченец','hp':55,'speed':110,'dmg':9,'range':340,'cd':1.4,'loot':{'food':2}},
    # Settlement garrisons stay inside the town.
    'occupier': {'name':'Мародёр','hp':40,'speed':110,'dmg':7,'range':320,'cd':1.6,'loot':{'metal':1,'food':1},'zone':470,'aggro':420},
    'occupier_elite': {'name':'Головорез','hp':110,'speed':120,'dmg':14,'range':420,'cd':1.1,'loot':{'metal':3},'zone':470,'aggro':470},
    'defender': {'name':'Охранник','hp':100,'speed':120,'dmg':12,'range':440,'cd':1.0,'loot':{},'zone':470,'aggro':470},
    'bandit': {'name':'Бандит','hp':70,'speed':130,'dmg':11,'range':380,'cd':1.2,'loot':{'metal':2},'aggro':480},
    'convoy': {'name':'Грузовик','hp':150,'speed':165,'dmg':0,'range':0,'cd':0,'loot':{}},
    # Wild animals: melee predators and a shy elk worth hunting. Meat goes into the hunter's backpack.
    'wolf': {'name':'Волк','hp':40,'speed':178,'dmg':9,'range':34,'cd':1.0,'melee':True,'aggro':430,'loot':{'food':3},'meat':1},
    'bear': {'name':'Медведь','hp':170,'speed':142,'dmg':26,'range':46,'cd':1.6,'melee':True,'aggro':300,'loot':{'food':8},'meat':3},
    'boar': {'name':'Кабан','hp':60,'speed':160,'dmg':12,'range':34,'cd':1.2,'melee':True,'aggro':230,'loot':{'food':5},'meat':2},
    'elk': {'name':'Лось','hp':75,'speed':195,'dmg':0,'range':0,'cd':0,'passive':True,'flee':400,'loot':{'food':6},'meat':3},
    # Mutants come out of ruined plants and the cold North, more of them at night.
    'mutant': {'name':'Мутант','hp':65,'speed':168,'dmg':14,'range':36,'cd':.9,'melee':True,'aggro':520,'loot':{'metal':3}},
    'spitter': {'name':'Кислотник','hp':50,'speed':120,'dmg':12,'range':300,'cd':1.8,'acid':True,'aggro':480,'loot':{'fuel':3}},
    'brute': {'name':'Громила','hp':260,'speed':108,'dmg':32,'range':50,'cd':2.0,'melee':True,'aggro':380,'loot':{'metal':10,'stone':6}},
}
NPC_FACTION = {'bandit':'outlaws','wolf':'wild','bear':'wild','boar':'wild','elk':'game','mutant':'mutants','spitter':'mutants','brute':'mutants'}
WILDLIFE = {'tundra':['wolf','wolf','elk','bear'],'snowtaiga':['wolf','wolf','bear','elk','elk'],'taiga':['wolf','bear','elk','elk','boar'],
            'ural':['wolf','boar','elk','elk','bear'],'mixed':['boar','elk','wolf','elk'],'steppe':['boar','wolf','boar']}
CAR_TANK = 45          # tank of old saves' cars; each model has its own
# Player cars, drawn in web/assets/cars.png (one 128 x 224 cell each, front up). Speeds in world px/s:
# max — top speed on asphalt, accel — px/s², offroad — share of top speed off the road, grip — how fast sideways
# sliding dies out, steer — steering lock (rad), armor — divides damage, len/wid — body size in world px.
CARS = [
    {'id':'uaz','name':'УАЗ-469','max':360,'accel':240,'offroad':.86,'grip':7.0,'steer':.62,'armor':1.5,'tank':60,'len':93,'wid':54,'price':520,'level':6,'door':.18,'color':'#59603f'},
    {'id':'bukhanka','name':'УАЗ «Буханка»','max':330,'accel':205,'offroad':.8,'grip':6.0,'steer':.55,'armor':1.7,'tank':70,'len':100,'wid':56,'price':600,'level':8,'door':.12,'color':'#7d8b93'},
    {'id':'vaz2101','name':'ВАЗ-2101','max':400,'accel':270,'offroad':.52,'grip':7.4,'steer':.66,'armor':1.0,'tank':39,'len':92,'wid':50,'price':0,'level':1,'door':.12,'color':'#d9cfb2'},
    {'id':'vaz2107','name':'ВАЗ-2107','max':420,'accel':290,'offroad':.52,'grip':7.6,'steer':.66,'armor':1.05,'tank':39,'len':93,'wid':52,'price':150,'level':2,'door':.12,'color':'#3f5f8c'},
    {'id':'vaz2109','name':'ВАЗ-2109','max':445,'accel':330,'offroad':.5,'grip':8.2,'steer':.7,'armor':.95,'tank':43,'len':86,'wid':53,'price':260,'level':4,'door':.12,'color':'#9c3e34'},
    {'id':'niva','name':'«Нива»','max':380,'accel':290,'offroad':.92,'grip':8.0,'steer':.7,'armor':1.25,'tank':42,'len':81,'wid':56,'price':380,'level':5,'door':.16,'color':'#3e5a3a'},
    {'id':'moskvich','name':'«Москвич»','max':385,'accel':250,'offroad':.55,'grip':7.0,'steer':.64,'armor':1.0,'tank':46,'len':89,'wid':52,'price':0,'level':1,'door':.12,'color':'#c79a52'},
    {'id':'volga','name':'ГАЗ-24 «Волга»','max':455,'accel':270,'offroad':.48,'grip':6.6,'steer':.6,'armor':1.3,'tank':55,'len':96,'wid':54,'price':450,'level':7,'door':.12,'color':'#2a2826'},
]
STARTER_CARS = [2, 6]   # a worn «копейка» or «Москвич» to start with
POST = {'name':'Пост на трассе','desc':'Лечит тебя рядом, стреляет по врагам, собирает пошлину с дороги и забирает четверть груза чужих колонн.'}
POST_COST = {'wood':30,'stone':20,'metal':15}
# Relative trade value of a unit of each resource in each region.
PRICES = {
    'default': {'wood':1.0,'stone':1.0,'metal':1.8,'food':1.2,'fuel':1.6},
    'Урал': {'wood':1.0,'stone':.8,'metal':1.3,'food':1.4,'fuel':1.8},
    'Сибирь': {'wood':.7,'stone':1.0,'metal':1.9,'food':1.4,'fuel':1.5},
    'Западная Сибирь': {'wood':.8,'stone':1.0,'metal':1.8,'food':1.3,'fuel':1.0},
    'Дальний Восток': {'wood':.8,'stone':1.1,'metal':2.0,'food':.9,'fuel':1.7},
    'Север': {'wood':1.3,'stone':1.0,'metal':1.6,'food':2.0,'fuel':1.3},
    'Крайний Север': {'wood':1.6,'stone':1.0,'metal':1.2,'food':2.2,'fuel':1.4},
    'Якутия': {'wood':1.2,'stone':1.0,'metal':1.4,'food':2.0,'fuel':1.7},
    'Поволжье': {'wood':1.1,'stone':1.1,'metal':1.9,'food':.85,'fuel':1.5},
    'Центральная Россия': {'wood':1.1,'stone':1.0,'metal':1.6,'food':1.1,'fuel':1.6},
}
EVENTS = [
 {'name':'Караван у старой трассы','text':'У караванщиков заканчивается еда. Они готовы отдать часть груза за помощь. Можно договориться, сопроводить их или рискнуть нападением.',
  'options':[
    {'name':'Обменять припасы','chance':95,'cost':{'food':8},'reward':{'fuel':12},'rep':3,'risk':0},
    {'name':'Провести через опасный участок','chance':72,'cost':{'fuel':3},'reward':{'metal':18,'food':10},'rep':7,'risk':15},
    {'name':'Ограбить караван','chance':52,'cost':{'metal':3},'reward':{'fuel':20,'metal':15},'rep':-10,'risk':30,'violent':True}]},
 {'name':'Люди под завалами','text':'Из полуразрушенного дома слышны голоса. Перекрытия неустойчивы: тщательная подготовка безопаснее, но потребует материалов.',
  'options':[
    {'name':'Укрепить перекрытия и помочь','chance':90,'cost':{'wood':8,'metal':3},'reward':{'food':14},'rep':12,'risk':8},
    {'name':'Пробраться через подвал','chance':58,'cost':{},'reward':{'metal':12,'food':8},'rep':8,'risk':25},
    {'name':'Разобрать доступные завалы','chance':95,'cost':{'food':2},'reward':{'stone':16},'rep':0,'risk':0}]},
 {'name':'Сигнал из радиорубки','text':'Старая радиостанция ещё подаёт признаки жизни. В журнале оператора могут быть сведения о поселении.',
  'options':[
    {'name':'Восстановить питание','chance':82,'cost':{'metal':5,'fuel':2},'reward':{'wood':10},'rep':4,'risk':10,'intel':20},
    {'name':'Настроить связь наугад','chance':48,'cost':{},'reward':{'metal':8},'rep':2,'risk':12,'intel':15},
    {'name':'Снять запасные детали','chance':95,'cost':{},'reward':{'metal':10},'rep':-3,'risk':0}]},
 {'name':'Запертый склад','text':'На двери свежие царапины. Внутри могут быть полезные запасы, но никто не знает, выдержит ли старая лестница.',
  'options':[
    {'name':'Подготовить безопасный проход','chance':88,'cost':{'wood':6,'metal':4},'reward':{'food':22,'fuel':7},'rep':2,'risk':10},
    {'name':'Быстро вскрыть дверь','chance':58,'cost':{'metal':2},'reward':{'metal':18,'food':14},'rep':0,'risk':25},
    {'name':'Осмотреть только двор','chance':95,'cost':{},'reward':{'wood':7,'stone':5},'rep':0,'risk':0}]},
 {'name':'Сломанный водяной насос','text':'Посёлок теряет запасы воды. Местные запомнят того, кто поможет восстановить насос.',
  'options':[
    {'name':'Заменить изношенные узлы','chance':86,'cost':{'metal':6,'wood':4},'reward':{'food':18},'rep':10,'risk':5},
    {'name':'Собрать временную конструкцию','chance':60,'cost':{'wood':3},'reward':{'food':12},'rep':6,'risk':15},
    {'name':'Доставить запасную воду','chance':95,'cost':{'fuel':4},'reward':{'stone':14},'rep':7,'risk':0}]},
 {'name':'Заброшенный медпункт','text':'В медпункте остались лекарства и запечатанные ящики. За стеной что-то скрипит.',
  'options':[
    {'name':'Осторожно обследовать комнаты','chance':85,'cost':{'food':4},'reward':{'food':14},'rep':4,'risk':10,'heal':35},
    {'name':'Вскрыть дальний ящик','chance':55,'cost':{'metal':2},'reward':{'metal':15,'fuel':8},'rep':0,'risk':25,'heal':20},
    {'name':'Забрать аптечку у входа','chance':95,'cost':{},'reward':{},'rep':1,'risk':0,'heal':20}]},
 {'name':'Беженцы у ворот','text':'Семьи из соседнего района просят приюта. Еды мало, но рабочие руки нужны всем.',
  'options':[
    {'name':'Принять всех','chance':92,'cost':{'food':14},'reward':{'wood':10,'stone':10},'rep':14,'risk':0,'loyalty':10},
    {'name':'Принять только мастеров','chance':80,'cost':{'food':6},'reward':{'metal':12},'rep':3,'risk':0},
    {'name':'Забрать у них оружие и прогнать','chance':70,'cost':{},'reward':{'metal':16},'rep':-12,'risk':12,'violent':True,'loyalty':-8}]},
 {'name':'Вспышка лихорадки','text':'Несколько жителей слегли с жаром. Если не помочь, болезнь пойдёт дальше.',
  'options':[
    {'name':'Устроить карантин и лечить','chance':84,'cost':{'food':10,'fuel':3},'reward':{},'rep':10,'risk':5,'loyalty':12},
    {'name':'Искать лекарства в аптеке','chance':55,'cost':{},'reward':{'food':6},'rep':6,'risk':20,'loyalty':6},
    {'name':'Закрыть заболевших в бараке','chance':90,'cost':{},'reward':{},'rep':-8,'risk':0,'loyalty':-10}]},
 {'name':'Волки у окраины','text':'Стая подходит к огородам. Ночью пропал телёнок, люди боятся выходить.',
  'options':[
    {'name':'Устроить облаву','chance':68,'cost':{'metal':4},'reward':{'food':16},'rep':6,'risk':22},
    {'name':'Поставить изгородь','chance':93,'cost':{'wood':12},'reward':{'food':6},'rep':5,'risk':0,'loyalty':5},
    {'name':'Отдать скот и уйти','chance':95,'cost':{'food':6},'reward':{},'rep':-2,'risk':0}]},
 {'name':'Застрявшая цистерна','text':'На переезде брошен бензовоз. Под ним провалился асфальт, кабина заперта.',
  'options':[
    {'name':'Вытащить тросом','chance':74,'cost':{'fuel':4,'metal':3},'reward':{'fuel':26},'rep':2,'risk':10},
    {'name':'Слить топливо вёдрами','chance':90,'cost':{},'reward':{'fuel':10},'rep':0,'risk':5},
    {'name':'Разобрать на металл','chance':90,'cost':{'food':2},'reward':{'metal':16},'rep':0,'risk':0}]},
 {'name':'Перебежчики','text':'Трое бойцов чужой стороны хотят уйти от своих и предлагают сведения о поселении.',
  'options':[
    {'name':'Принять и расспросить','chance':78,'cost':{'food':6},'reward':{'metal':6},'rep':4,'risk':10,'intel':25},
    {'name':'Выдать их обратно за выкуп','chance':85,'cost':{},'reward':{'fuel':12,'metal':8},'rep':-9,'risk':0},
    {'name':'Отпустить на все четыре стороны','chance':95,'cost':{},'reward':{},'rep':3,'risk':0}]},
 {'name':'Старая скважина','text':'Насос на окраине можно запустить: внизу остатки нефти, но конструкция ржавая.',
  'options':[
    {'name':'Перебрать насос','chance':76,'cost':{'metal':8,'wood':4},'reward':{'fuel':22,'stone':6},'rep':3,'risk':12},
    {'name':'Запустить как есть','chance':45,'cost':{},'reward':{'fuel':18},'rep':0,'risk':28},
    {'name':'Снять трубы','chance':95,'cost':{},'reward':{'metal':9},'rep':0,'risk':0}]},
]
# Quests come only from people in settlements. 'giver' is the kind of person who offers and accepts them.
QUESTS = [
 {'kind':'harvest','giver':'mechanic','coins':20,'name':'Металлолом','target':4,'reward':{'metal':4},
  'text':'Собери ресурсы на четырёх точках в окрестностях: брёвна, камни, ящики, железо.',
  'intro':'Станок стоит — нечем кормить. Притащи хоть что-нибудь: доски, железо, камень. Мне всё сгодится.',
  'done':'Вот это дело. Держи, честно заработал.'},
 {'kind':'loot','giver':'mechanic','coins':35,'name':'Старые тайники','target':1,'reward':{'fuel':4},
  'text':'Обыщи тайник в заброшенном месте: завод, нефтебаза, деревня. Отмечены ромбами на карте.',
  'intro':'Перед тишиной склады набивали под завязку. Кто дошёл — тот и богат. Сходи, проверь хоть один.',
  'done':'Живой вернулся — уже удача. Держи свою долю.'},
 {'kind':'build','giver':'elder','coins':30,'name':'Вернуть свет в окна','target':1,'reward':{'stone':4,'food':3},
  'text':'Начни восстановление любого здания в своём поселении.',
  'intro':'Люди живут в подвалах, как крысы. Подними хоть одну крышу — и они поверят, что жить можно.',
  'done':'Видел свет в окнах этой ночью. Спасибо тебе.'},
 {'kind':'aid','giver':'elder','coins':25,'name':'Плечом к плечу','target':1,'reward':{'food':4},
  'text':'Помоги жителям своего поселения через меню площади.',
  'intro':'Еды до весны не хватит. Если у тебя есть свои люди — поддержи их, они это запомнят.',
  'done':'Дети сегодня легли сытыми. Это дорогого стоит.'},
 {'kind':'deliver','giver':'trader','coins':40,'name':'Посылка','target':1,'reward':{'metal':3,'wood':3},
  'text':'Доставь 6 припасов на площадь указанного поселения.',
  'intro':'Есть груз, есть адрес, нет охраны. Довезёшь — заплачу. Не довезёшь — значит, не судьба.',
  'done':'Дошло, значит. Хорошо. Держи, как договаривались.'},
 {'kind':'trade','giver':'trader','coins':20,'name':'Рыночный день','target':1,'reward':{'food':3},
  'text':'Соверши обмен у торговцев на площади нейтрального или своего поселения.',
  'intro':'Рынок держится на тех, кто меняется. Сделай хоть одну сделку — и я тебя запомню.',
  'done':'Вот теперь ты свой на этом рынке.'},
 {'kind':'explore','giver':'trader','coins':30,'name':'Дальше знакомой дороги','target':1,'reward':{'fuel':3},
  'text':'Впервые доберись до ещё одного поселения.',
  'intro':'Говорят, за рекой ещё живут люди. Съезди, посмотри, что там. Карта — по клавише M.',
  'done':'Значит, не одни мы остались. Хорошие новости дорого стоят.'},
 {'kind':'kills','giver':'major','coins':45,'name':'Чистая дорога','target':3,'reward':{'metal':4},
  'text':'Убей трёх мародёров или бандитов. Они бродят у дорог и сидят в брошенных городах.',
  'intro':'Отставить разговоры. Трасса забита отребьем. Три головы — и считай, что ты на довольствии.',
  'done':'Доклад принят. Трасса стала чище. Свободен.'},
 {'kind':'capture','giver':'major','coins':80,'name':'Новая точка опоры','target':1,'reward':{'wood':6,'stone':5},
  'text':'Очисти поселение от засевших там мародёров и установи над ним контроль.',
  'intro':'Город без хозяина — это город для мародёров. Выбей их и подними свой флаг. Крупные города — не суйся в одиночку.',
  'done':'Флаг видно с дороги. Так держать.'},
 {'kind':'mutants','giver':'major','coins':60,'name':'Тварь из руин','target':2,'reward':{'metal':5},
  'text':'Убей двух мутантов. Они выходят из заводов, шахт и с Севера, ночью их больше.',
  'intro':'Из руин лезет то, чему нет названия. Двух. Без героизма — бей и отходи.',
  'done':'Видел их вблизи? Вот и я больше не сплю. Держи.'},
 {'kind':'hunt','giver':'hunter','coins':30,'name':'Охотничий сезон','target':2,'reward':{'food':5},
  'text':'Добудь двух диких зверей: лося, кабана, волка или медведя.',
  'intro':'Зверь вернулся в леса, пока людей не стало. Принеси мне две туши — научу, как жить с этой земли.',
  'done':'Мясо есть — зиму протянем. Бери, заслужил.'},
 {'kind':'event','giver':'medic','coins':35,'name':'Чужая беда','target':1,'reward':{'food':3},
  'text':'Успешно разреши одно происшествие на площади любого поселения.',
  'intro':'У людей беда за бедой: то лихорадка, то завал. Помоги кому-нибудь — нам всем зачтётся.',
  'done':'Говорят, ты помог. Таких сейчас мало.'},
]
# Faction storylines. Each chapter ends with a choice whose consequences persist.
STORY = {
 'survivors': [
  {'id':'s1','title':'Голос Урала','text':'Обрывок передачи с вышки в Екатеринбурге: кто-то ещё держит связь. Доберитесь до площади города.',
   'goal':{'kind':'visit','town':'ekaterinburg'},
   'choices':[
     {'name':'Передать сигнал всем','text':'Частота станет общей. Люди потянутся к вам, бандиты тоже услышат.','reward':{'food':20},'rep':10,'flag':'open_signal'},
     {'name':'Сохранить частоту в секрете','text':'Только ваши станции знают ключ: переговоры успешнее на 5%.','reward':{'metal':16},'rep':0,'flag':'secret_freq'}]},
  {'id':'s2','title':'Свет в Шабровском','text':'Убежищу нужна связь. Восстановите радиостанцию в Шабровском до первого уровня.',
   'goal':{'kind':'building','building':'radio','level':1},
   'choices':[
     {'name':'Открыть двери беженцам','text':'Ферма даёт на 15% больше, лояльность всех поселений +8.','reward':{'wood':14},'rep':8,'flag':'open_doors','loyalty':8},
     {'name':'Строгий отбор','text':'Только мастера: сразу больше материалов.','reward':{'metal':20,'stone':20},'rep':-3}]},
  {'id':'s3','title':'Дорога жизни','text':'Колонны связывают поселения. Доведите до убежища две колонны с грузом.',
   'goal':{'kind':'convoy','target':2},
   'choices':[
     {'name':'Вооружить колонны','text':'Грузовики крепче на 50%.','reward':{'fuel':16},'rep':2,'flag':'armed_convoys'},
     {'name':'Договориться с мародёрами','text':'Отдать часть еды: мародёров станет меньше.','reward':{},'cost':{'food':20},'rep':4,'flag':'marauder_pact'}]},
  {'id':'s4','title':'Союз городов','text':'Поселения должны держаться вместе. Установите контроль над тремя поселениями, включая убежище.',
   'goal':{'kind':'towns','target':3},
   'choices':[
     {'name':'Совет поселений','text':'Лояльность всех ваших поселений +15, переговоры легче.','reward':{'food':12},'rep':10,'loyalty':15},
     {'name':'Военное положение','text':'Гарнизоны усилены: ополчение +1 в каждом поселении.','reward':{'metal':20},'rep':-4,'flag':'militia'}]},
  {'id':'s5','title':'Большая связь','text':'Последний шаг — радиостанция убежища второго уровня и пять поселений. Тогда эфир услышит вся страна.',
   'goal':{'kind':'victory'},'choices':[]},
 ],
 'bandits': [
  {'id':'b1','title':'Первая дань','text':'Люди должны знать, кто теперь хозяин. Соберите дань в захваченном поселении или ограбьте колонну.',
   'goal':{'kind':'tribute','target':1},
   'choices':[
     {'name':'Делиться с людьми','text':'Дань меньше ранит лояльность.','reward':{'food':10},'rep':6,'flag':'fair_share'},
     {'name':'Забрать всё','text':'Сразу больше добычи, но о вас пойдёт дурная слава.','reward':{'metal':22,'fuel':14},'rep':-8}]},
  {'id':'b2','title':'Хозяин дорог','text':'Кто держит трассу, тот держит регион. Поставьте блокпост на дороге (клавиша B на трассе).',
   'goal':{'kind':'post','target':1},
   'choices':[
     {'name':'Пошлина по совести','text':'Нейтральные поселения меньше боятся вас.','reward':{'wood':12},'rep':5},
     {'name':'Шлагбаум для всех','text':'Блокпосты стреляют сильнее, пошлина выше.','reward':{'metal':16},'rep':-5,'flag':'iron_road'}]},
  {'id':'b3','title':'Охота на колонны','text':'Чужие грузовики везут всё, что нужно. Перехватите два грузовика или три раза победите врагов.',
   'goal':{'kind':'kills','target':3},
   'choices':[
     {'name':'Брать в долю','text':'Перехваченные грузы приносят ещё +20%.','reward':{'fuel':14},'rep':0,'flag':'cargo_cut'},
     {'name':'Устрашение','text':'Штурм успешнее на 8%, дань приносит больше.','reward':{'metal':14},'rep':-6,'flag':'iron_hand'}]},
  {'id':'b4','title':'Железная рука','text':'Под вашим контролем должно быть три поселения, включая убежище.',
   'goal':{'kind':'towns','target':3},
   'choices':[
     {'name':'Договор с местными','text':'Лояльность ваших поселений +15.','reward':{'food':16},'rep':8,'loyalty':15},
     {'name':'Гарнизоны везде','text':'Ополчение +1 в каждом поселении.','reward':{'metal':20},'rep':-3,'flag':'militia'}]},
  {'id':'b5','title':'Свой эфир','text':'Пять поселений и радиостанция второго уровня в Первоуральске — и вся округа будет слушать ваши приказы.',
   'goal':{'kind':'victory'},'choices':[]},
 ],
}
# Character progression: experience for actions, a level gives health and damage, perks unlock.
MAX_LEVEL = 30
XP = {'harvest':4,'build':15,'built':25,'event':20,'event_fail':5,'explore':30,'deliver':25,'aid':10,
      'tax':10,'raid':25,'capture':60,'quest':40,'story':80,'kill_marauder':15,'kill_fighter':20,
      'kill_player':35,'kill_animal':10,'kill_mutant':20,'kill_convoy':30,'loot':25,'airdrop':20,'extinguish':15,'trade':3,'post':20,'craft':10}
PERKS = [
    {'level':5,'name':'Сноровка','desc':'Сбор ресурсов приносит на 2 единицы больше.'},
    {'level':10,'name':'Полевой медик','desc':'Перевязка стоит 3 припаса и лечит на 45.'},
    {'level':15,'name':'Экономный стрелок','desc':'Выстрел тратит на 40% меньше металла.'},
    {'level':20,'name':'Закалка','desc':'Получаемый урон ниже ещё на 10%.'},
    {'level':25,'name':'Авторитет','desc':'Шанс переговоров, подкупа и штурма +5%.'},
]

def xp_to_next(level):
    return 80 + 60 * (level - 1)

def max_hp(level):
    return 100 + 5 * (level - 1)

def hero_look(level):
    """The hero's twenty drawings are one person growing up: a new outfit about every level and a half."""
    return min(len(LOOKS) - 1, (level - 1) * len(LOOKS) // MAX_LEVEL)

# One storyline for every side, built from the chapters above.
STORY_LINE = [dict(STORY['survivors'][0]), dict(STORY['survivors'][1]), dict(STORY['bandits'][1]),
              dict(STORY['survivors'][2]), dict(STORY['survivors'][3]), dict(STORY['survivors'][4])]
STORY_LINE[0]['choices'] = [dict(c, text=c['text'].replace('бандиты тоже', 'соперники тоже')) for c in STORY_LINE[0]['choices']]
STORY_LINE[1].update(title='Свет в убежище', text='Твоему поселению нужна связь. Восстанови радиостанцию в одном из своих поселений до первого уровня.')
STORY_LINE[2]['choices'] = [dict(c, text=c['text'].replace('вас', 'тебя')) for c in STORY_LINE[2]['choices']]
STORY_LINE[3]['text'] = 'Колонны связывают поселения. Доведи до дома две колонны с грузом.'
STORY_LINE[4].update(title='Свои города', text='Установи контроль над тремя поселениями.')
STORY_LINE[5]['text'] = 'Последний шаг — радиостанция второго уровня в одном из твоих поселений и пять поселений под контролем. Тогда эфир услышит вся страна.'
BIG_TOWNS = {'moscow','petersburg','ekaterinburg','novosibirsk','kazan','nizhny','krasnoyarsk','omsk','perm',
             'vladivostok','khabarovsk','irkutsk'}
START_STOCK = {'wood':20.0,'stone':12.0,'metal':8.0,'food':20.0,'fuel':10.0}
NODE_RESPAWN = 240
# Character looks: cells of web/assets/characters.png (5 x 4).
LOOKS = ['Худи','Худи и разгрузка','Худи и плитник','Худи и каска','Рейдер с рюкзаком',
         'Полевая форма','Пехотинец','Камуфляж с кепи','Камуфляж и каска','Тёмный камуфляж',
         'Пустынная кепи','Пустынный штурмовик','Лесной камуфляж','Городской камуфляж','Синяя форма',
         'Зимний маскхалат','Зимний штурмовик','Чёрный спецназ','Бродяга с шарфом','Тяжёлый рейдер']
NPC_LOOKS = {'marauder':[0,1,2],'occupier':[0,1,2,18],'occupier_elite':[3,4,9],'defender':[5,6],
             'bandit':[18,12,13],'raider':[18,19],'ranger':[7,8],'militia':[6],'civil':[0,1]}
NPC_LOOKS_COLD = {'marauder':[15],'occupier':[15,0],'occupier_elite':[16],'bandit':[15,18],'defender':[16,6]}
# People who hand out quests. Dialogue lines may use {town}, {region}, {name}.
# 'art' is the cell in web/assets/givers.png (figure on the square) and web/assets/portraits.jpg (face in dialogues).
GIVERS = {
 'elder': {'role':'Староста','look':13,'art':0,'names':['Михалыч','Петрович','Семёныч','Иваныч','дед Захар','Фёдор Ильич'],
  'greet':['А, путник. Нечасто к нам заходят живые. Чего надо?','Я тут за старшего, пока никого постарше не осталось. Говори.',
           'Тише, люди спят после ночной смены. Ты по делу?'],
  'lore':['В {town} до тишины жило тысяч сто. Теперь — сколько видишь.','Зима в {region} лютая. Кто не запас дров к октябрю — тот не дожил до марта.',
          'Электричество ушло в первую же ночь. Потом ушли и те, кто ждал, что его вернут.']},
 'trader': {'role':'Торговец','look':10,'art':1,'names':['Толик','Вадим','Гоша-Барыга','Степаныч'],
  'greet':['Смотреть — бесплатно, трогать — за деньги. Чего изволишь?','Свежие новости, тушёнка и патроны. Новости — даром.',
           'Ты не из местных. Значит, при деньгах или при беде.'],
  'lore':['По трассе на {town} опять бандиты стоят. Объезжай лесом.','Монета сейчас — то, что на что-то меняется. Остальное — бумага.',
          'Из Сибири везут мясо, с Урала — железо. Кто держит дороги — тот и сыт.']},
 'mechanic': {'role':'Механик','look':2,'art':2,'names':['Колян','Димон','Серёга-Гайка','Палыч'],
  'greet':['Руки не подаю, они в мазуте. Чего?','Если машина не едет — это ко мне. Если едет — тоже ко мне, значит, скоро не поедет.',
           'Тишина ничего не сломала. Сломалось всё само, без присмотра.'],
  'lore':['Бензин в {region} на вес золота. Канистру за пазухой носи.','На заводах ещё лежит металл, но туда ходят не только люди.',
          'Генератор я собрал из трёх. Работает, если пнуть.']},
 'major': {'role':'Отставной майор','look':8,'art':3,'names':['майор Гусев','майор Ткачёв','майор Рябов'],
  'greet':['Стой. Назовись. ...Ладно, свободен — говори по существу.','Порядок держится на тех, кто не боится стрелять. Ты из таких?',
           'Докладывай коротко. Времени мало, патронов ещё меньше.'],
  'lore':['В крупных городах засели серьёзные люди. В одиночку туда — только за смертью.','Убежища охраняют те, кто стреляет без предупреждения второй раз.',
          'Мутанты ночью смелеют. Днём — прячутся по цехам.']},
 'hunter': {'role':'Охотник','look':7,'art':4,'names':['Егорыч','дед Матвей','Савва'],
  'greet':['Тихо ходи — зверя спугнёшь. Чего тебе?','Лес теперь снова хозяин. Мы у него в гостях.',
           'Волки нынче наглые. Человека не боятся — его мало осталось.'],
  'lore':['Медведь в {region} весной голодный. Не стой у него на тропе.','Лося бей с первого выстрела — второго он тебе не даст.',
          'Сырое мясо ешь только с голоду. Лучше у костра обжарь.']},
 'medic': {'role':'Фельдшер','look':0,'art':5,'names':['Анна','Ольга','Лида','Марина'],
  'greet':['Не кашляешь? Не кровишь? Тогда проходи.','Бинтов мало, спирта ещё меньше. С чем пришёл?',
           'Я лечу всех. Даже тех, кто потом стреляет в моих же больных.','Я одна на весь район. Так что болей быстро.'],
  'lore':['Речную воду не пей сырой. Половина моих больных — оттуда.','Холод убивает тише пули. Одевайся теплее, если идёшь на Север.',
          'Антибиотики сейчас дороже золота. Береги, если найдёшь.']},
 'radio': {'role':'Радист','look':1,'art':6,'names':['Кеша','Лёха-Эфир','Боря'],
  'greet':['Шшш... эфир живой. Ты слышишь? Нет? А я слышу.','Связь — это то, что отделяет людей от стаи.',
           'Кто-то держит частоту на Урале. Я хочу знать, кто.'],
  'lore':['Каждую ночь в три часа кто-то передаёт цифры. Никто не знает, кто.','Пять городов на одной частоте — и страна снова заговорит.',
          'Радиостанцию поднять — полдела. Удержать — вот работа.']},
}
GIVER_PLAN = ['elder','trader','mechanic','major','hunter','medic']   # two per settlement, three in big cities
MAX_ACTIVE_QUESTS = 3
WORLD_EVENTS = ['refugees', 'fire', 'marauders', 'airdrop', 'weather']
WEATHER = {'clear':'Ясно', 'rain':'Дождь', 'fog':'Туман', 'storm':'Гроза', 'snow':'Снег'}
DAY_SECONDS = 1440 / 1.4           # one in-game day in real seconds

def config():
    return {'version':VERSION,'width':WORLD_SIZE[0],'height':WORLD_SIZE[1],'scale':WORLD_SCALE,
            'resources':RESOURCES,'buildings':BUILDINGS,'max_players':MAX_PLAYERS,
            'roads':ROADS,'regions':REGIONS,'rivers':RIVERS,'lakes':LAKES,'hills':HILLS,
            'poi_kinds':POI_KINDS,'weapons':WEAPONS,'armor':ARMOR,'npc_types':NPC_TYPES,'post':POST,
            'post_cost':POST_COST,'prices':PRICES,'build_time':BUILD_TIME,'weather_names':WEATHER,
            'storage':[STORAGE_BASE,STORAGE_PER_WAREHOUSE],'day_seconds':DAY_SECONDS,
            'perks':PERKS,'looks':LOOKS,'hero_looks':[hero_look(n) for n in range(1, MAX_LEVEL + 1)],'side_colors':SIDE_COLORS,'npc_looks':NPC_LOOKS,'npc_looks_cold':NPC_LOOKS_COLD,'recipes':RECIPES,'camp_parts':CAMP_PARTS,'camp_half':CAMP_HALF,'stash_slots':CAMP_STASH_SLOTS,'car_tank':CAR_TANK,'cars':CARS,'shop':SHOP_ITEMS,'items':ITEMS,'clothes':CLOTHES,'backpacks':BACKPACKS,'story_coins':STORY_COINS,'landmarks':{k:{'name':v[0],'w':v[1],'h':v[2],'x':LANDMARK_POS[0],'y':LANDMARK_POS[1]} for k, v in LANDMARKS.items()},'max_level':MAX_LEVEL,'xp_table':[xp_to_next(n) for n in range(1, MAX_LEVEL + 1)],
            'towns':[dict(id=t[0],name=t[1],x=t[2],y=t[3],region=t[4]) for t in TOWNS]}
