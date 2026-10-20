"""Static, fictional game rules. Python 3.7+, standard library only."""
VERSION = '0.1.0'
WORLD_SIZE = (20000, 10000)
FACTIONS = {'survivors': 'Выжившие', 'bandits': 'Бандиты'}
RESOURCES = {'wood': 'Древесина', 'stone': 'Камень', 'metal': 'Металл',
             'food': 'Припасы', 'fuel': 'Топливо'}
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
]
BASES = {'survivors': 'shabrovsky', 'bandits': 'pervouralsk'}
ROADS = [('petersburg','moscow'),('moscow','nizhny'),('nizhny','kazan'),
         ('kazan','pervouralsk'),('pervouralsk','perm'),('pervouralsk','ekaterinburg'),
         ('pervouralsk','shabrovsky'),('shabrovsky','ekaterinburg'),
         ('ekaterinburg','tyumen'),('tyumen','novosibirsk'),
         ('novosibirsk','krasnoyarsk'),('krasnoyarsk','irkutsk'),
         ('irkutsk','yakutsk'),('irkutsk','khabarovsk'),('khabarovsk','vladivostok')]
BUILDINGS = {
    'depot': {'name':'Опорный пункт','cost':{'wood':24,'stone':14,'metal':8},
              'desc':'Склад и центр поселения. Его уровень открывает улучшения остальных зданий.','workers':0},
    'house': {'name':'Жилой блок','cost':{'wood':20,'stone':14,'metal':6},
              'desc':'За каждый уровень в поселение возвращаются восемь жителей.','workers':0},
    'sawmill': {'name':'Лесопилка','cost':{'wood':18,'stone':12,'metal':8},
                'desc':'Бригада заготавливает древесину для общего запаса фракции.','workers':3,'output':['wood',5]},
    'quarry': {'name':'Карьер','cost':{'wood':20,'stone':16,'metal':10},
               'desc':'Камень для ремонта домов и укреплений.','workers':3,'output':['stone',5]},
    'workshop': {'name':'Мастерская','cost':{'wood':26,'stone':20,'metal':16},
                 'desc':'Разбор завалов и восстановление пригодного металла.','workers':3,'output':['metal',4]},
    'farm': {'name':'Теплица','cost':{'wood':16,'stone':10,'metal':5},
             'desc':'Продовольствие для рабочих, путешествий и переговоров.','workers':2,'output':['food',6]},
    'garage': {'name':'Топливный склад','cost':{'wood':24,'stone':16,'metal':16},
               'desc':'Поисковая бригада собирает топливо в окрестностях.','workers':2,'output':['fuel',3]},
    'radio': {'name':'Радиостанция','cost':{'wood':30,'stone':24,'metal':25},
              'desc':'Связь помогает переговорам: +5% за уровень. Второй уровень нужен для победы.','workers':0},
    'guard': {'name':'Сторожевая вышка','cost':{'wood':22,'stone':16,'metal':14},
              'desc':'Увеличивает оборону поселения и снижает шанс чужого захвата.','workers':0},
}
# Buildings surround an open square. All coordinates are deliberately schematic.
SLOTS = [('depot',-185,-150),('house',145,-155),('sawmill',-360,35),
         ('quarry',350,20),('workshop',-185,185),('farm',160,190),
         ('garage',-360,280),('radio',350,285),('guard',0,-340)]
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
]
QUESTS = [
 {'kind':'harvest','name':'Запас на первое время','text':'Собери ресурсы в окрестностях 3 раза. Подойди к дереву, камням или ящикам и нажми E.','target':3,'reward':{'wood':16,'metal':8}},
 {'kind':'build','name':'Вернуть свет в окна','text':'Восстанови или улучши любое здание своей фракции.','target':1,'reward':{'stone':16,'food':12}},
 {'kind':'event','name':'Голос в эфире','text':'Успешно разреши одно происшествие. Ищи жёлтый знак вопроса на площади.','target':1,'reward':{'metal':14,'fuel':10}},
 {'kind':'explore','name':'Дальше знакомой дороги','text':'Впервые посети ещё одно поселение. Используй машину и карту M.','target':1,'reward':{'fuel':16,'food':8}},
 {'kind':'deliver','name':'Нужны припасы','text':'Доставь 12 припасов на площадь указанного поселения. Доставка гарантирована, если ты добрался.','target':1,'reward':{'metal':20,'wood':14}},
 {'kind':'capture','name':'Новая точка опоры','text':'Установи контроль над одним поселением. Начни с нейтрального.','target':1,'reward':{'wood':35,'stone':25,'fuel':16}},
 {'kind':'aid','name':'Плечом к плечу','text':'Поддержи жителей своего поселения через меню площади.','target':1,'reward':{'metal':12,'food':18}},
]

def config():
    return {'version':VERSION,'width':WORLD_SIZE[0],'height':WORLD_SIZE[1],
            'factions':FACTIONS,'resources':RESOURCES,'buildings':BUILDINGS,
            'bases':BASES,'roads':ROADS,'towns':[dict(id=t[0],name=t[1],x=t[2],y=t[3],region=t[4]) for t in TOWNS]}
