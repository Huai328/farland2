"""
Farland History Ⅱ — 角色服務
處理角色建立、裝備解析等業務邏輯
"""
import time
from dataclasses import dataclass

from farland.models import db, Character
from config import Config
from game_data import INITIAL_STATS


@dataclass
class ParsedEquipment:
    """解析後的單件裝備"""
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


def parse_equipment(equip_str: str) -> ParsedEquipment:
    """解析逗號分隔的裝備字串"""
    if not equip_str:
        return ParsedEquipment()
    parts = equip_str.split(',')
    if len(parts) < 11:
        parts.extend([''] * (11 - len(parts)))
    return ParsedEquipment(
        no=int(parts[0] or 0),
        name=parts[1],
        value=int(parts[2] or 0),
        damage=int(parts[3] or 0),
        weight=int(parts[4] or 0),
        element=int(parts[5] or 0),
        hit_rate=int(parts[6] or 80),
        critical=int(parts[7] or 10),
        ability=int(parts[8] or 0),
        equip_type=parts[9],
        flag=parts[10],
    )


def create_character(
    char_id: str,
    password: str,
    name: str,
    sex: int,
    element: int,
    chara_img: int,
    country_id: int,
    email: str,
) -> Character:
    """建立新角色（對應 chara_make.cgi）"""
    now = int(time.time())
    char = Character(
        id=char_id,
        password=password,
        name=name,
        sex=sex,
        element=element,
        chara_img=chara_img,
        country_id=country_id,
        hp=INITIAL_STATS['hp'],
        max_hp=INITIAL_STATS['hp'],
        mp=INITIAL_STATS['mp'],
        max_mp=INITIAL_STATS['mp'],
        str_stat=INITIAL_STATS['str'],
        vit=INITIAL_STATS['vit'],
        int_stat=INITIAL_STATS['int'],
        fai=INITIAL_STATS['fai'],
        dex=INITIAL_STATS['dex'],
        agi=INITIAL_STATS['agi'],
        stat_caps=INITIAL_STATS['stat_caps'],
        gold=INITIAL_STATS['gold'],
        weapon=INITIAL_STATS['weapon'],
        armor=INITIAL_STATS['armor'],
        accessory=INITIAL_STATS['accessory'],
        technique=INITIAL_STATS['technique'],
        last_action=now,
        created_at=now,
        oya=1,
        flag4=email,
    )
    db.session.add(char)
    db.session.commit()
    return char


def validate_new_character(char_id: str, password: str, name: str, email: str) -> str | None:
    """驗證新角色資料，回傳錯誤訊息或 None"""
    if not char_id:
        return '請輸入 ID。'
    if not password:
        return '請輸入密碼。'
    if char_id == password:
        return 'ID 和密碼不能相同。'
    if len(char_id) < 4 or len(char_id) > 8:
        return 'ID 請輸入 4～8 個字元。'
    if len(password) < 4 or len(password) > 8:
        return '密碼請輸入 4～8 個字元。'
    if not char_id.isalnum():
        return 'ID 請使用半形輸入。'
    if not password.isalnum():
        return '密碼請使用半形輸入。'
    if not name:
        return '請輸入名稱。'
    if len(name) < 2 or len(name) > 8:
        return '名稱請輸入 2～8 個字元。'
    if not email or '@' not in email or '.' not in email.split('@')[-1]:
        return '電子郵件輸入不正確。'

    # 重複檢查
    if db.session.get(Character, char_id):
        return '該 ID 已被使用。'
    if Character.query.filter_by(name=name).first():
        return '該名稱已被使用。'
    if Character.query.filter_by(flag4=email).first():
        return '該電子郵件已被使用。'

    return None
