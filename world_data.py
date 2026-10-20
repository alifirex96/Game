"""Static game rules and the schematic map of Russia. Python 3.7+, standard library only."""
VERSION = '0.2.1'
WORLD_SIZE = (20000, 10000)
FACTIONS = {'survivors': 'Выжившие', 'bandits': 'Бандиты'}
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
BASES = {'survivors': 'shabrovsky', 'bandits': 'pervouralsk'}
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
    'Западная Сибирь': {'biome':'taiga','cold':2}, 'Сибирь': {'biome':'taiga','cold':2},
    'Прибайкалье': {'biome':'taiga','cold':2}, 'Якутия': {'biome':'tundra','cold':3},
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
POI_KINDS = {
    'factory': {'name':'Заброшенный завод','loot':{'metal':16,'stone':6},'guards':3},
    'gas': {'name':'Заправка','loot':{'fuel':16,'food':4},'guards':1},
    'military': {'name':'Воинская часть','loot':{'metal':22,'fuel':8},'guards':4},
    'farm': {'name':'Брошенный колхоз','loot':{'food':20,'wood':6},'guards':1},
    'village': {'name':'Пустая деревня','loot':{'wood':12,'food':8},'guards':1},
    'oil': {'name':'Нефтебаза','loot':{'fuel':24},'guards':3},
    'mine': {'name':'Рудник','loot':{'stone':16,'metal':10},'guards':2},
    'rail': {'name':'Железнодорожная станция','loot':{'metal':10,'food':10,'fuel':6},'guards':2},
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
BUILDINGS = {
    'depot': {'name':'Опорный пункт','cost':{'wood':24,'stone':14,'metal':8},
              'desc':'Центр поселения и штаб обороны. Его уровень открывает улучшения остальных зданий.','workers':0},
    'house': {'name':'Жилой дом','cost':{'wood':20,'stone':14,'metal':6},
              'desc':'За каждый уровень в поселение возвращаются восемь жителей.','workers':0},
    'sawmill': {'name':'Лесопилка','cost':{'wood':18,'stone':12,'metal':8},
                'desc':'Бригада заготавливает древесину для общего запаса фракции.','workers':3,'output':['wood',5]},
    'quarry': {'name':'Карьер','cost':{'wood':20,'stone':16,'metal':10},
               'desc':'Камень для ремонта домов и укреплений.','workers':3,'output':['stone',5]},
    'workshop': {'name':'Мастерская','cost':{'wood':26,'stone':20,'metal':16},
                 'desc':'Восстанавливает металл и изготавливает оружие и броню.','workers':3,'output':['metal',4]},
    'farm': {'name':'Ферма','cost':{'wood':16,'stone':10,'metal':5},
             'desc':'Теплицы и огороды: продовольствие для рабочих, походов и переговоров.','workers':2,'output':['food',6]},
    'garage': {'name':'Гараж','cost':{'wood':24,'stone':16,'metal':16},
               'desc':'Добывает топливо, чинит машины. Гараж убежища ускоряет и укрепляет машины фракции.','workers':2,'output':['fuel',3]},
    'warehouse': {'name':'Склад','cost':{'wood':22,'stone':18,'metal':8},
                  'desc':'Каждый уровень увеличивает предельный запас каждого ресурса фракции на 250.','workers':1},
    'radio': {'name':'Радиостанция','cost':{'wood':30,'stone':24,'metal':25},
              'desc':'Связь помогает переговорам: +5% за уровень. Второй уровень в убежище нужен для победы.','workers':0},
    'guard': {'name':'Сторожевая вышка','cost':{'wood':22,'stone':16,'metal':14},
              'desc':'Снижает шанс чужого захвата, вышка стреляет по врагам и мародёрам рядом с поселением.','workers':0},
}
# Buildings surround an open square. Coordinates are relative to the town centre.
# The cross streets (x = 0 and y = 0) stay free: they continue the highways to the square.
SLOTS = [('depot',-185,-150),('house',145,-155),('sawmill',-360,100),
         ('quarry',350,100),('workshop',-185,185),('farm',160,190),
         ('garage',-360,285),('radio',350,285),('guard',95,-340),('warehouse',160,335)]
TOWN_GATE = (480, 420)             # highways meet the town streets at these edge points
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
WEAPONS = [
    {'name':'Пистолет','dmg':16,'cd':.45,'range':420,'ammo':.12,'cost':{}},
    {'name':'Охотничье ружьё','dmg':32,'cd':.95,'range':540,'ammo':.25,'cost':{'metal':30,'wood':12},'workshop':1},
    {'name':'Автомат','dmg':13,'cd':.15,'range':470,'ammo':.08,'cost':{'metal':70,'fuel':12},'workshop':2},
]
ARMOR = [
    {'name':'Куртка','reduce':0,'cost':{}},
    {'name':'Разгрузка с пластинами','reduce':.2,'cost':{'metal':26,'food':6},'workshop':1},
    {'name':'Бронежилет','reduce':.36,'cost':{'metal':64,'stone':10},'workshop':3},
]
NPC_TYPES = {
    'marauder': {'name':'Мародёр','hp':45,'speed':118,'dmg':8,'range':330,'cd':1.5,'loot':{'metal':3,'food':2}},
    'raider': {'name':'Боец бандитов','hp':70,'speed':125,'dmg':11,'range':360,'cd':1.2,'loot':{'metal':4}},
    'ranger': {'name':'Дружинник','hp':70,'speed':125,'dmg':11,'range':360,'cd':1.2,'loot':{'food':4}},
    'militia': {'name':'Ополченец','hp':55,'speed':110,'dmg':9,'range':340,'cd':1.4,'loot':{'food':2}},
    'convoy': {'name':'Грузовик','hp':150,'speed':165,'dmg':0,'range':0,'cd':0,'loot':{}},
}
POSTS = {
    'survivors': {'name':'Сторожевой пост','desc':'Лечит союзников рядом, защищает колонны, добавляет репутацию.'},
    'bandits': {'name':'Блокпост','desc':'Собирает пошлину с дороги и берёт четверть груза чужих колонн.'},
}
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
QUESTS = [
 {'kind':'harvest','name':'Запас на первое время','text':'Собери ресурсы в окрестностях 3 раза. Подойди к дереву, камням или ящикам и нажми E.','target':3,'reward':{'wood':16,'metal':8}},
 {'kind':'build','name':'Вернуть свет в окна','text':'Восстанови или улучши любое здание своей фракции.','target':1,'reward':{'stone':16,'food':12}},
 {'kind':'event','name':'Голос в эфире','text':'Успешно разреши одно происшествие. Ищи жёлтый знак вопроса на площади.','target':1,'reward':{'metal':14,'fuel':10}},
 {'kind':'explore','name':'Дальше знакомой дороги','text':'Впервые посети ещё одно поселение. Используй машину и карту M.','target':1,'reward':{'fuel':16,'food':8}},
 {'kind':'deliver','name':'Нужны припасы','text':'Доставь 12 припасов на площадь указанного поселения. Доставка гарантирована, если ты добрался.','target':1,'reward':{'metal':20,'wood':14}},
 {'kind':'capture','name':'Новая точка опоры','text':'Установи контроль над одним поселением. Начни с нейтрального.','target':1,'reward':{'wood':35,'stone':25,'fuel':16}},
 {'kind':'aid','name':'Плечом к плечу','text':'Поддержи жителей своего поселения через меню площади.','target':1,'reward':{'metal':12,'food':18}},
 {'kind':'kills','name':'Чистая дорога','text':'Обезвредь двух мародёров. Они собираются у заброшенных заводов и заправок.','target':2,'reward':{'metal':16,'food':10}},
 {'kind':'loot','name':'Старые тайники','text':'Обыщи тайник в заброшенном месте: завод, деревня, нефтебаза. Отмечены на карте.','target':1,'reward':{'fuel':10,'stone':12}},
 {'kind':'trade','name':'Рыночный день','text':'Соверши обмен у торговцев на площади нейтрального или своего поселения.','target':1,'reward':{'food':12,'wood':10}},
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
      'kill_player':35,'kill_convoy':30,'loot':25,'airdrop':20,'extinguish':15,'trade':3,'post':20,'craft':10}
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

WORLD_EVENTS = ['refugees', 'fire', 'marauders', 'airdrop', 'weather']
WEATHER = {'clear':'Ясно', 'rain':'Дождь', 'fog':'Туман', 'storm':'Гроза', 'snow':'Снег'}
DAY_SECONDS = 1440 / 1.4           # one in-game day in real seconds

def config():
    return {'version':VERSION,'width':WORLD_SIZE[0],'height':WORLD_SIZE[1],
            'factions':FACTIONS,'resources':RESOURCES,'buildings':BUILDINGS,
            'bases':BASES,'roads':ROADS,'regions':REGIONS,'rivers':RIVERS,'lakes':LAKES,'hills':HILLS,
            'poi_kinds':POI_KINDS,'weapons':WEAPONS,'armor':ARMOR,'npc_types':NPC_TYPES,'posts':POSTS,
            'post_cost':POST_COST,'prices':PRICES,'build_time':BUILD_TIME,'weather_names':WEATHER,
            'storage':[STORAGE_BASE,STORAGE_PER_WAREHOUSE],'day_seconds':DAY_SECONDS,
            'perks':PERKS,'landmarks':{k:{'name':v[0],'w':v[1],'h':v[2],'x':LANDMARK_POS[0],'y':LANDMARK_POS[1]} for k, v in LANDMARKS.items()},'max_level':MAX_LEVEL,'xp_table':[xp_to_next(n) for n in range(1, MAX_LEVEL + 1)],
            'towns':[dict(id=t[0],name=t[1],x=t[2],y=t[3],region=t[4]) for t in TOWNS]}
