"""
Farland History Ⅱ — 資料匯入腳本
將 data/*.cgi（Shift_JIS flat-file）匯入 SQLite
"""
import os
import sys

# 加入專案根目錄
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from farland.models import db, Town, Country, Equipment, Technique, Ability, Monster, JobClass

# 原始資料目錄
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'data')


def read_file(filename, encoding='utf-8'):
    """讀取 Shift_JIS 編碼的檔案"""
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        print(f'  [SKIP] {filename} 不存在')
        return []
    try:
        with open(filepath, encoding=encoding, errors='replace') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f'  [ERROR] {filename}: {e}')
        return []


def import_towns():
    """匯入城鎮資料（data/towndata.cgi）"""
    print('匯入城鎮...')
    lines = read_file('towndata.cgi')
    for i, line in enumerate(lines):
        parts = line.split('<>')
        if len(parts) < 14:
            continue
        etc_parts = parts[13].split(',') if len(parts) > 13 else []
        town = Town(
            id=int(parts[0] or i),
            name=parts[1],
            country_id=int(parts[2] or 0),
            element=int(parts[3] or 0),
            gold=int(parts[4] or 0),
            weapon_dev=int(parts[5] or 0),
            armor_dev=int(parts[6] or 0),
            acc_dev=int(parts[7] or 0),
            item_dev=int(parts[8] or 0),
            trade=int(parts[9] or 0),
            special=int(parts[10] or 0),
            x=int(parts[11] or 0),
            y=int(parts[12] or 0),
            town_hp=int(etc_parts[0]) if len(etc_parts) > 0 and etc_parts[0] else 0,
            town_max_hp=int(etc_parts[1]) if len(etc_parts) > 1 and etc_parts[1] else 0,
            town_str=int(etc_parts[2]) if len(etc_parts) > 2 and etc_parts[2] else 0,
            town_def=int(etc_parts[3]) if len(etc_parts) > 3 and etc_parts[3] else 0,
            town_dex=int(etc_parts[4]) if len(etc_parts) > 4 and etc_parts[4] else 0,
            town_flag=etc_parts[5] if len(etc_parts) > 5 else '',
        )
        db.session.add(town)
    db.session.commit()
    print(f'  城鎮匯入完成: {Town.query.count()} 筆')


def import_countries():
    """匯入國家資料（data/country.cgi）"""
    print('匯入國家...')
    lines = read_file('country.cgi')
    for line in lines:
        parts = line.split('<>')
        if len(parts) < 9:
            continue
        country = Country(
            id=int(parts[0] or 0),
            name=parts[1],
            element=int(parts[2] or 0),
            gold=int(parts[3] or 0),
            king_id=parts[4],
            officials=parts[5],
            member_count=int(parts[6] or 0),
            message=parts[7],
            etc=parts[8] if len(parts) > 8 else '',
        )
        db.session.add(country)
    db.session.commit()
    print(f'  國家匯入完成: {Country.query.count()} 筆')


def import_equipment(filename, category):
    """匯入裝備資料"""
    print(f'匯入{category}...')
    lines = read_file(filename)
    count = 0
    for line in lines:
        parts = line.split('<>')
        if len(parts) < 2:
            continue
        # 各檔格式: name<>price<>power<>weight<>element<>hit<>crit<>ability<>type<>flag<>
        fields = parts[0].split(',') if ',' in parts[0] else parts
        if len(fields) < 2:
            continue
        equip = Equipment(
            category=category,
            name=fields[0] if len(fields) > 0 else '',
            price=int(fields[1]) if len(fields) > 1 and fields[1].isdigit() else 0,
            power=int(fields[2]) if len(fields) > 2 and fields[2].lstrip('-').isdigit() else 0,
            weight=int(fields[3]) if len(fields) > 3 and fields[3].isdigit() else 0,
            element=int(fields[4]) if len(fields) > 4 and fields[4].isdigit() else 0,
            hit_rate=int(fields[5]) if len(fields) > 5 and fields[5].isdigit() else 80,
            critical=int(fields[6]) if len(fields) > 6 and fields[6].isdigit() else 10,
            ability=fields[7] if len(fields) > 7 else '',
            equip_type=fields[8] if len(fields) > 8 else '',
            flag=fields[9] if len(fields) > 9 else '',
        )
        db.session.add(equip)
        count += 1
    db.session.commit()
    print(f'  {category}匯入完成: {count} 筆')


def import_techniques():
    """匯入技法資料（data/tec.cgi）"""
    print('匯入技法...')
    lines = read_file('tec.cgi')
    for i, line in enumerate(lines):
        parts = line.split('<>')
        if len(parts) < 7:
            continue
        tec = Technique(
            id=i,
            name=parts[0],
            power=int(parts[1]) if parts[1].lstrip('-').isdigit() else 0,
            hit_rate=int(parts[2]) if parts[2].isdigit() else 0,
            mp_cost=int(parts[3]) if parts[3].isdigit() else 0,
            stat_bonus=parts[4],
            effect_type=int(parts[5]) if parts[5].isdigit() else 0,
            job_req=parts[6] if len(parts) > 6 else '',
        )
        db.session.add(tec)
    db.session.commit()
    print(f'  技法匯入完成: {Technique.query.count()} 筆')


def import_abilities():
    """匯入能力資料（data/ability.cgi）"""
    print('匯入能力...')
    lines = read_file('ability.cgi')
    for line in lines:
        parts = line.split('<>')
        if len(parts) < 8:
            continue
        ab = Ability(
            id=int(parts[0]) if parts[0].isdigit() else 0,
            name=parts[1],
            description=parts[2],
            power=int(parts[3]) if parts[3].lstrip('-').isdigit() else 0,
            tier=int(parts[4]) if parts[4].isdigit() else 0,
            cost=int(parts[5]) if parts[5].isdigit() else 0,
            class_req=int(parts[6]) if parts[6].isdigit() else 0,
            ability_type=int(parts[7]) if parts[7].strip().isdigit() else 0,
        )
        db.session.add(ab)
    db.session.commit()
    print(f'  能力匯入完成: {Ability.query.count()} 筆')


def import_monsters():
    """匯入怪物資料（data/monster.cgi）"""
    print('匯入怪物...')
    for fname in ['monster.cgi', 'monster2.cgi']:
        lines = read_file(fname)
        for line in lines:
            parts = line.split('<>')
            if len(parts) < 2:
                continue
            monster = Monster(
                name=parts[0],
                stats=parts[1] if len(parts) > 1 else '',
                weapon=parts[2] if len(parts) > 2 else '',
                armor=parts[3] if len(parts) > 3 else '',
                element=int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0,
                exp_reward=int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 0,
                gold_reward=int(parts[6]) if len(parts) > 6 and parts[6].isdigit() else 0,
                area=int(parts[7]) if len(parts) > 7 and parts[7].strip().isdigit() else 1,
            )
            db.session.add(monster)
    db.session.commit()
    print(f'  怪物匯入完成: {Monster.query.count()} 筆')


def import_classes():
    """匯入職業定義（data/class.cgi）"""
    print('匯入職業...')
    lines = read_file('class.cgi')
    for i, line in enumerate(lines):
        parts = line.split('<>')
        if len(parts) < 2:
            continue
        jc = JobClass(
            id=i,
            name=parts[0],
            requirements=parts[1] if len(parts) > 1 else '',
            stat_caps=parts[2] if len(parts) > 2 else '',
            stat_mods=parts[3] if len(parts) > 3 else '',
            tier=int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0,
            base_type=int(parts[5]) if len(parts) > 5 and parts[5].strip().isdigit() else 0,
        )
        db.session.add(jc)
    db.session.commit()
    print(f'  職業匯入完成: {JobClass.query.count()} 筆')


def main():
    app = create_app()
    with app.app_context():
        print('=== Farland History Ⅱ 資料匯入 ===')
        print(f'資料目錄: {os.path.abspath(DATA_DIR)}')
        print()

        db.drop_all()
        db.create_all()


        import_countries()
        import_towns()
        import_equipment('arm.cgi', 'weapon')
        import_equipment('pro.cgi', 'armor')
        import_equipment('acc.cgi', 'accessory')
        import_equipment('item.cgi', 'item')
        import_techniques()
        import_abilities()
        import_monsters()
        import_classes()

        print()
        print('=== 匯入完成 ===')


if __name__ == '__main__':
    main()
