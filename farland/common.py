"""
Farland History Ⅱ — 共用函數
轉換自 sub.cgi（chara_open/input 已移至 models，此處為其他工具函數）
"""
import time
from datetime import datetime

from farland.models import db, Town, Country, GameLog, GuestList, BattleHistory
from config import Config
from game_data import ELEMENTS, ELEMENT_BG, ELEMENT_FG


def get_town_for_character(position: int) -> Town | None:
    """載入角色所在城鎮（對應 town_open）"""
    return db.session.get(Town, position)


def get_country(country_id: int) -> Country | None:
    """載入國家資料（對應 con_open）"""
    if country_id == 0:
        return None
    return db.session.get(Country, country_id)


def get_all_countries() -> list[Country]:
    """取得所有國家"""
    return Country.query.all()


def append_game_log(log_type: int, message: str):
    """追加遊戲日誌（對應 maplog 系列）

    log_type:
        1 = 一般（maplog.cgi, 保留 10 筆）
        2 = 歷史（maplog2.cgi, 保留 50 筆）
        3 = 警告（maplog3.cgi, 保留 30 筆）
        4 = 道具使用（maplog4.cgi, 保留 50 筆）
        5 = 戰鬥（maplog5.cgi, 保留 10 筆）
        6 = 國家（maplog6.cgi, 保留 30 筆）
        7 = 管理（maplog7.cgi, 保留 30 筆）
    """
    limits = {1: 10, 2: 50, 3: 30, 4: 50, 5: 10, 6: 30, 7: 30}
    limit = limits.get(log_type, 30)

    log = GameLog(
        log_type=log_type,
        message=message,
        created_at=int(time.time()),
    )
    db.session.add(log)

    # 清理超過上限的舊日誌
    count = GameLog.query.filter_by(log_type=log_type).count()
    if count > limit:
        old = (GameLog.query
               .filter_by(log_type=log_type)
               .order_by(GameLog.created_at.asc())
               .limit(count - limit)
               .all())
        for o in old:
            db.session.delete(o)

    db.session.commit()


def append_battle_history(char_id: str, result: str, opponent: str):
    """追加戰鬥歷史（對應 kh_log/eh_log, 每人保留 6 筆）"""
    now = datetime.now()
    date_str = f'{now.month}月{now.day}日'

    entry = BattleHistory(
        char_id=char_id,
        result=result,
        opponent=opponent,
        created_at=date_str,
    )
    db.session.add(entry)

    count = BattleHistory.query.filter_by(char_id=char_id).count()
    if count > 6:
        old = (BattleHistory.query
               .filter_by(char_id=char_id)
               .order_by(BattleHistory.id.asc())
               .limit(count - 6)
               .all())
        for o in old:
            db.session.delete(o)

    db.session.commit()


def update_guest_list(name: str, country_element: int, host: str) -> list[dict]:
    """更新在線玩家列表（對應 guest_list，5 分鐘逾時）"""
    now = int(time.time())

    # 清理逾期玩家
    GuestList.query.filter(GuestList.timestamp < now - 300).delete()

    # 更新或新增
    existing = GuestList.query.filter_by(name=name).first()
    if existing:
        existing.timestamp = now
        existing.country_element = country_element
        existing.host = host
    else:
        db.session.add(GuestList(
            name=name,
            timestamp=now,
            country_element=country_element,
            host=host,
        ))

    db.session.commit()

    # 返回目前在線列表
    guests = GuestList.query.filter(GuestList.timestamp >= now - 300).all()
    return [{'name': g.name, 'element': g.country_element} for g in guests]


def format_datetime() -> str:
    """格式化當前時間（對應 time_data）"""
    now = datetime.now()
    weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    wd = weekdays[now.weekday()]
    return f'{now.year}/{now.month:02d}/{now.day:02d}/({wd})　{now.hour:02d}時{now.minute:02d}分'
