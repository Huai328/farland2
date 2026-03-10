"""
Farland History Ⅱ — 裝備服務
轉換自 sub.cgi:equip_open 及 status/equip2.pl 的裝備計算邏輯
"""
import random
from dataclasses import dataclass

from farland.models import db, Character, CharacterItem, Equipment
from game_data import WEAPON_TYPES, JOBS


@dataclass
class ParsedEquip:
    """解析後的單件裝備（逗號分隔字串 → 結構體）"""
    no: int = 0
    name: str = ''
    value: int = 0
    damage: int = 0
    weight: int = 0
    element: int = 0
    hit_rate: int = 80
    critical: int = 10
    ability: int = 0
    equip_type: str = ''
    flag: str = ''

    def to_str(self) -> str:
        return ','.join(str(x) for x in [
            self.no, self.name, self.value, self.damage, self.weight,
            self.element, self.hit_rate, self.critical, self.ability,
            self.equip_type, self.flag
        ])


def parse_equip(s: str) -> ParsedEquip:
    """解析逗號分隔的裝備字串"""
    if not s:
        return ParsedEquip()
    parts = s.split(',')
    parts.extend([''] * max(0, 11 - len(parts)))
    return ParsedEquip(
        no=int(parts[0] or 0),
        name=parts[1] or '',
        value=int(parts[2] or 0),
        damage=int(parts[3] or 0),
        weight=int(parts[4] or 0),
        element=int(parts[5] or 0),
        hit_rate=int(parts[6] or 80),
        critical=int(parts[7] or 10),
        ability=int(parts[8] or 0),
        equip_type=parts[9] or '',
        flag=parts[10] or '',
    )


def calc_equip_damage(char: Character):
    """計算裝備實際傷害值（含屬性加成）— 對應 equip_open"""
    weapon = parse_equip(char.weapon)
    armor = parse_equip(char.armor)
    accessory = parse_equip(char.accessory)

    # 技能62: 屬性加成+15%
    skills = (char.skills or '').split(',')
    eleplus = 0.15 if '62' in skills else 0.0

    # 屬性一致加成
    if char.element == weapon.element and weapon.element != 0:
        weapon.damage = int(weapon.damage * (1.2 + eleplus))
    if char.element == armor.element and armor.element != 0:
        armor.damage = int(armor.damage * (1.2 + eleplus))
    if char.element == accessory.element and accessory.element != 0:
        accessory.damage = int(accessory.damage * (1.5 + eleplus))

    # 職業適性武器加成
    job_weapon = WEAPON_TYPES.get(char.job_class, '')
    if job_weapon == weapon.equip_type:
        weapon.hit_rate += 10

    return weapon, armor, accessory


def get_inventory(char_id: str) -> list[CharacterItem]:
    """取得角色物品欄"""
    return CharacterItem.query.filter_by(char_id=char_id).all()


def add_to_inventory(char_id: str, item: CharacterItem) -> bool:
    """將物品加入物品欄（檢查上限）"""
    from config import Config
    count = CharacterItem.query.filter_by(char_id=char_id).count()
    if count >= Config.MAX_ITEMS:
        return False
    item.char_id = char_id
    db.session.add(item)
    db.session.commit()
    return True


def remove_from_inventory(item_id: int) -> CharacterItem | None:
    """從物品欄移除物品"""
    item = db.session.get(CharacterItem, item_id)
    if item:
        db.session.delete(item)
        db.session.commit()
    return item


def equip_item(char: Character, item: CharacterItem) -> str | None:
    """裝備物品（武器/防具/飾品），舊裝備回到物品欄。回傳錯誤或 None"""
    from config import Config
    category = item.category

    # 取得目前裝備字串
    if category == 'weapon':
        old_str = char.weapon
    elif category == 'armor':
        old_str = char.armor
    elif category == 'accessory':
        old_str = char.accessory
    else:
        return '無法裝備的道具。'

    # 解析舊裝備
    old = parse_equip(old_str)

    # 將新裝備設為當前
    new_str = f'{item.id},{item.name},{item.price},{item.power},{item.weight},' \
              f'{item.element},{item.hit_rate},{item.critical},{item.ability},' \
              f'{item.equip_type},{item.flag}'

    if category == 'weapon':
        char.weapon = new_str
    elif category == 'armor':
        char.armor = new_str
    elif category == 'accessory':
        char.accessory = new_str

    # 移除新裝備從物品欄
    db.session.delete(item)

    # 舊裝備放回物品欄（如果不是初始裝備）
    if old.name and old.no != 0:
        old_item = CharacterItem(
            char_id=char.id,
            category=category,
            name=old.name,
            price=old.value,
            power=old.damage,
            weight=old.weight,
            element=old.element,
            hit_rate=old.hit_rate,
            critical=old.critical,
            ability=str(old.ability),
            equip_type=old.equip_type,
            flag=old.flag,
        )
        db.session.add(old_item)

    db.session.commit()
    return None


def use_consumable(char: Character, item: CharacterItem) -> str:
    """使用消耗品。回傳結果訊息"""
    effect = item.power
    msg = f'使用了{item.name}。'

    # 消耗品效果根據 equip_type 判定
    etype = item.equip_type or '0'

    if etype == '1':
        # HP 回復
        char.hp = min(char.hp + effect, char.max_hp)
        msg += f' HP恢復了{effect}。'
    elif etype == '2':
        # MP 回復
        char.mp = min(char.mp + effect, char.max_mp)
        msg += f' MP恢復了{effect}。'
    elif etype == '3':
        # HP + MP 全回復
        char.hp = char.max_hp
        char.mp = char.max_mp
        msg += ' HP・MP已全部恢復。'
    elif etype == '4':
        # 能力值提升
        stat_up = random.randint(1, max(1, effect))
        stats = ['str_stat', 'vit', 'int_stat', 'fai', 'dex', 'agi']
        chosen = random.choice(stats)
        current = getattr(char, chosen)
        setattr(char, chosen, current + stat_up)
        msg += f' 能力提升了{stat_up}。'
    elif etype == '5':
        # 經驗值
        char.exp += effect
        char.total_exp += effect
        msg += f' 獲得了{effect}經驗值。'
    elif etype == '6':
        # 能力點
        char.ability_pts += effect
        msg += f' 獲得了{effect}熟練度。'
    elif etype == '7':
        # 金幣
        char.gold += effect
        msg += f' 獲得了{effect}G。'
    else:
        msg += ' 但是什麼都沒有發生。'

    # 消耗品用完移除
    db.session.delete(item)
    db.session.commit()
    return msg
