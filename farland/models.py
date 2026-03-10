"""
Farland History Ⅱ — SQLAlchemy Models
轉換自 flat-file 資料結構（logfile/chara/*.cgi, data/*.cgi）
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Character(db.Model):
    """玩家角色（對應 logfile/chara/{id}.cgi 的 48 欄位）"""
    __tablename__ = 'characters'

    id = db.Column(db.String(8), primary_key=True)  # $mid
    password = db.Column(db.String(8), nullable=False)  # $mpass
    name = db.Column(db.String(16), nullable=False, unique=True)  # $mname
    url = db.Column(db.String(255), default='')  # $murl（認證狀態）
    chara_img = db.Column(db.Integer, default=0)  # $mchara
    sex = db.Column(db.Integer, default=0)  # $msex（0=男, 1=女）

    hp = db.Column(db.Integer, default=50)
    max_hp = db.Column(db.Integer, default=50)
    mp = db.Column(db.Integer, default=10)
    max_mp = db.Column(db.Integer, default=10)
    element = db.Column(db.Integer, default=0)  # 0-7

    str_stat = db.Column(db.Integer, default=20)  # $mstr
    vit = db.Column(db.Integer, default=20)
    int_stat = db.Column(db.Integer, default=20)  # $mint（避免保留字）
    fai = db.Column(db.Integer, default=20)  # 精神
    dex = db.Column(db.Integer, default=20)
    agi = db.Column(db.Integer, default=20)
    stat_caps = db.Column(db.String(64), default='200,200,200,200,200,200')  # $mmax

    comment = db.Column(db.Text, default='')  # $mcom
    gold = db.Column(db.Integer, default=50)
    bank = db.Column(db.Integer, default=0)
    exp = db.Column(db.Integer, default=0)  # $mex
    total_exp = db.Column(db.Integer, default=0)
    job_points = db.Column(db.String(64), default='0,0,0,0,0,0')  # $mjp
    ability_pts = db.Column(db.Integer, default=0)  # $mabp
    country_exp = db.Column(db.Integer, default=0)  # $mcex

    unit_id = db.Column(db.String(32), default='')  # $munit
    country_id = db.Column(db.Integer, default=0)  # $mcon

    # 裝備（逗號分隔字串：no,name,val,dmg,wei,ele,hit,cl,sta,type,flg）
    weapon = db.Column(db.String(255), default='')  # $marm
    armor = db.Column(db.String(255), default='')  # $mpro
    accessory = db.Column(db.String(255), default='')  # $macc

    technique = db.Column(db.String(64), default='0,0,0,50,50')  # $mtec
    status_eff = db.Column(db.String(32), default='')  # $msta
    position = db.Column(db.Integer, default=0)  # $mpos（所在城鎮 ID）
    message = db.Column(db.Text, default='')  # $mmes
    host = db.Column(db.String(255), default='')

    last_action = db.Column(db.Integer, default=0)  # $mdate（Unix timestamp）
    created_at = db.Column(db.Integer, default=0)  # $mdate2
    job_class = db.Column(db.Integer, default=0)  # 0-28
    total_wins = db.Column(db.Integer, default=0)  # $mtotal
    win_streak = db.Column(db.Integer, default=0)  # $mkati
    job_type = db.Column(db.Integer, default=0)  # 0-5
    oya = db.Column(db.Integer, default=0)  # $moya（隱藏值/亂數種子）
    skills = db.Column(db.String(32), default='')  # $msk

    flag1 = db.Column(db.String(255), default='')
    flag2 = db.Column(db.String(255), default='')
    flag3 = db.Column(db.String(255), default='')
    flag4 = db.Column(db.String(255), default='')  # email
    flag5 = db.Column(db.String(255), default='')

    @property
    def level(self):
        lv = self.exp // 100 + 1
        return min(lv, 100)

    @property
    def parsed_stat_caps(self):
        parts = (self.stat_caps or '200,200,200,200,200,200').split(',')
        keys = ['max_str', 'max_vit', 'max_int', 'max_fai', 'max_dex', 'max_agi']
        return {k: int(v) for k, v in zip(keys, parts)}

    @property
    def parsed_job_points(self):
        parts = (self.job_points or '0,0,0,0,0,0').split(',')
        return [int(p) for p in parts]


class Town(db.Model):
    """城鎮（對應 data/towndata.cgi）"""
    __tablename__ = 'towns'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    country_id = db.Column(db.Integer, default=0)
    element = db.Column(db.Integer, default=0)
    gold = db.Column(db.Integer, default=0)
    weapon_dev = db.Column(db.Integer, default=0)  # 武器店發展度
    armor_dev = db.Column(db.Integer, default=0)
    acc_dev = db.Column(db.Integer, default=0)
    item_dev = db.Column(db.Integer, default=0)  # 產業
    trade = db.Column(db.Integer, default=0)
    special = db.Column(db.Integer, default=0)
    x = db.Column(db.Integer, default=0)
    y = db.Column(db.Integer, default=0)
    # town_etc 展開
    town_hp = db.Column(db.Integer, default=0)
    town_max_hp = db.Column(db.Integer, default=0)
    town_str = db.Column(db.Integer, default=0)
    town_def = db.Column(db.Integer, default=0)
    town_dex = db.Column(db.Integer, default=0)
    town_flag = db.Column(db.String(32), default='')


class Country(db.Model):
    """國家（對應 data/country.cgi）"""
    __tablename__ = 'countries'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    element = db.Column(db.Integer, default=0)
    gold = db.Column(db.Integer, default=0)
    king_id = db.Column(db.String(8), default='')
    officials = db.Column(db.String(255), default='')  # 逗號分隔
    member_count = db.Column(db.Integer, default=0)
    message = db.Column(db.Text, default='')
    etc = db.Column(db.String(255), default='')


class Equipment(db.Model):
    """裝備定義（統一 arm.cgi + pro.cgi + acc.cgi + item.cgi）"""
    __tablename__ = 'equipment'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(16), nullable=False)  # weapon/armor/accessory/item
    name = db.Column(db.String(32), nullable=False)
    price = db.Column(db.Integer, default=0)
    power = db.Column(db.Integer, default=0)
    weight = db.Column(db.Integer, default=0)
    element = db.Column(db.Integer, default=0)
    hit_rate = db.Column(db.Integer, default=80)
    critical = db.Column(db.Integer, default=10)
    ability = db.Column(db.String(32), default='')
    equip_type = db.Column(db.String(16), default='')
    flag = db.Column(db.String(32), default='')


class Technique(db.Model):
    """技法（對應 data/tec.cgi）"""
    __tablename__ = 'techniques'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    power = db.Column(db.Integer, default=0)
    hit_rate = db.Column(db.Integer, default=0)
    mp_cost = db.Column(db.Integer, default=0)
    stat_bonus = db.Column(db.String(64), default='')
    effect_type = db.Column(db.Integer, default=0)
    job_req = db.Column(db.String(32), default='')


class Ability(db.Model):
    """能力（對應 data/ability.cgi）"""
    __tablename__ = 'abilities'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    description = db.Column(db.Text, default='')
    power = db.Column(db.Integer, default=0)  # $abdmg
    tier = db.Column(db.Integer, default=0)  # $abrate
    cost = db.Column(db.Integer, default=0)  # $abpoint
    class_req = db.Column(db.Integer, default=0)  # $abclass
    ability_type = db.Column(db.Integer, default=0)  # $abtype


class Monster(db.Model):
    """怪物（對應 data/monster.cgi）"""
    __tablename__ = 'monsters'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(32), nullable=False)
    stats = db.Column(db.String(128), nullable=False)  # 逗號分隔的多項數值
    weapon = db.Column(db.String(255), default='')
    armor = db.Column(db.String(255), default='')
    element = db.Column(db.Integer, default=0)
    exp_reward = db.Column(db.Integer, default=0)
    gold_reward = db.Column(db.Integer, default=0)
    area = db.Column(db.Integer, default=1)


class JobClass(db.Model):
    """職業定義（對應 data/class.cgi）"""
    __tablename__ = 'job_classes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False)
    requirements = db.Column(db.String(128), default='')
    stat_caps = db.Column(db.String(128), default='')
    stat_mods = db.Column(db.String(128), default='')
    tier = db.Column(db.Integer, default=0)
    base_type = db.Column(db.Integer, default=0)


class BattleState(db.Model):
    """戰鬥狀態（對應 logfile/battle/{id}.cgi）"""
    __tablename__ = 'battle_state'

    char_id = db.Column(db.String(8), db.ForeignKey('characters.id'), primary_key=True)
    hp_rate = db.Column(db.Float, default=1.0)
    mp_rate = db.Column(db.Float, default=1.0)
    timer = db.Column(db.Integer, default=0)


class CharacterItem(db.Model):
    """角色物品欄（對應 logfile/item/{id}.cgi）"""
    __tablename__ = 'character_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    char_id = db.Column(db.String(8), db.ForeignKey('characters.id'), nullable=False)
    category = db.Column(db.String(16), default='')
    name = db.Column(db.String(32), nullable=False)
    price = db.Column(db.Integer, default=0)
    power = db.Column(db.Integer, default=0)
    weight = db.Column(db.Integer, default=0)
    element = db.Column(db.Integer, default=0)
    hit_rate = db.Column(db.Integer, default=80)
    critical = db.Column(db.Integer, default=10)
    ability = db.Column(db.String(32), default='')
    equip_type = db.Column(db.String(16), default='')
    flag = db.Column(db.String(32), default='')


class GameLog(db.Model):
    """遊戲日誌（對應 data/maplog*.cgi）"""
    __tablename__ = 'game_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    log_type = db.Column(db.Integer, nullable=False)  # 1-7 對應 maplog1-7
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.Integer, nullable=False)  # Unix timestamp


class BattleHistory(db.Model):
    """戰鬥歷史（對應 logfile/history/{id}.cgi）"""
    __tablename__ = 'battle_history'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    char_id = db.Column(db.String(8), db.ForeignKey('characters.id'), nullable=False)
    result = db.Column(db.Text, nullable=False)
    opponent = db.Column(db.String(32), default='')
    created_at = db.Column(db.String(32), default='')


class Message(db.Model):
    """訊息系統（對應 meslog/*.cgi）"""
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    scope = db.Column(db.String(32), nullable=False)  # 'all' / 'country_N' / 'unit_N' / 'player_ID'
    sender_id = db.Column(db.String(8), nullable=False)
    recipient_id = db.Column(db.String(8), default='')
    sender_name = db.Column(db.String(16), nullable=False)
    sender_img = db.Column(db.Integer, default=0)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.Integer, nullable=False)


class ForumPost(db.Model):
    """討論板（對應 blog/conv/*.cgi）"""
    __tablename__ = 'forum_posts'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    forum_type = db.Column(db.String(16), nullable=False)  # 'all' / 'country_N'
    thread_id = db.Column(db.Integer, default=0)
    char_id = db.Column(db.String(8), nullable=False)
    char_name = db.Column(db.String(16), nullable=False)
    char_img = db.Column(db.Integer, default=0)
    country_element = db.Column(db.Integer, default=0)
    title = db.Column(db.String(64), default='')
    body = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(32), default='')
    created_at = db.Column(db.Integer, nullable=False)


class CountryRule(db.Model):
    """國家法規（對應 blog/rule/*.cgi）"""
    __tablename__ = 'country_rules'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    scope = db.Column(db.String(16), nullable=False)  # 'global' / country_id
    char_id = db.Column(db.String(8), nullable=False)
    char_name = db.Column(db.String(16), nullable=False)
    char_img = db.Column(db.Integer, default=0)
    body = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(32), default='')
    created_at = db.Column(db.Integer, nullable=False)


class Unit(db.Model):
    """部隊（對應 data/unit.cgi）"""
    __tablename__ = 'units'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    leader_id = db.Column(db.String(8), nullable=False)
    name = db.Column(db.String(32), nullable=False)
    message = db.Column(db.Text, default='')
    country_id = db.Column(db.Integer, default=0)


class CountryEquipment(db.Model):
    """國家開發裝備（對應 data/carm.cgi）"""
    __tablename__ = 'country_equipment'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.Integer, default=0)  # 0=武器, 1=防具, 2=飾品
    name = db.Column(db.String(32), nullable=False)
    price = db.Column(db.Integer, default=0)
    power = db.Column(db.Integer, default=0)
    weight = db.Column(db.Integer, default=0)
    element = db.Column(db.Integer, default=0)
    hit_rate = db.Column(db.Integer, default=75)
    critical = db.Column(db.Integer, default=9)
    equip_type = db.Column(db.String(16), default='')
    town_id = db.Column(db.Integer, default=0)
    country_id = db.Column(db.Integer, default=0)


class DischargLog(db.Model):
    """解雇記錄（對應 logfile/out/*.cgi）"""
    __tablename__ = 'discharg_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    char_id = db.Column(db.String(8), nullable=False)
    from_country_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.String(32), nullable=False)


class GuestList(db.Model):
    """在線玩家（對應 data/guest_list.cgi）"""
    __tablename__ = 'guest_list'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(16), nullable=False)
    timestamp = db.Column(db.Integer, nullable=False)
    country_element = db.Column(db.Integer, default=0)
    host = db.Column(db.String(255), default='')
