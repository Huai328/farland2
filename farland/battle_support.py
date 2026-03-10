"""
Farland History Ⅱ — 戰鬥引擎
轉換自 battle_suport.cgi (664行) 的純邏輯計算

核心函數：
  PARA  — 戰鬥參數初始化（攻防速暴計算）
  MATT  — 玩家回合攻擊（7-15 層判定樹）
  EATT  — 敵方回合攻擊（鏡像結構）
  LVUP  — 升級處理
  MAXUP — 限界值上昇
  TEC_OPEN — 技法資料載入

所有函數操作 CombatState dataclass，不直接操作 DB。
"""
import random
from dataclasses import dataclass, field

from farland.models import db, Ability, Technique
from game_data import ANTI_ELEMENT, JOB_STAT_CAP_BONUS


@dataclass
class Fighter:
    """戰鬥中的角色/敵人參數"""
    name: str = ''
    chara_img: int = 0
    element: int = 0

    hp: int = 0
    max_hp: int = 0
    mp: int = 0
    max_mp: int = 0

    str_stat: int = 0
    vit: int = 0
    int_stat: int = 0
    fai: int = 0
    dex: int = 0
    agi: int = 0

    job_type: int = 0
    job_class: int = 0

    # 裝備數值
    arm_dmg: int = 0
    arm_wei: int = 0
    arm_name: str = ''
    pro_dmg: int = 0
    pro_wei: int = 0
    pro_name: str = ''
    acc_dmg: int = 0
    acc_wei: int = 0
    acc_name: str = ''
    arm_sta: int = 0  # weapon ability
    pro_sta: int = 0  # armor ability
    acc_sta: int = 0  # accessory ability

    # 技設定
    technique: str = '0,0,0,50,50'
    skills: str = ''

    # 限界值
    stat_caps: str = '200,200,200,200,200,200'

    # 計算後的戰鬥值
    attack: int = 0
    defense: int = 0
    magic_def: int = 0
    critical: int = 20
    dodge: int = 0
    dodge2: int = 0  # guard (from ability)
    speed: int = 0

    # 技法陣列
    tec_name: list = field(default_factory=lambda: ['', '', ''])
    tec_str: list = field(default_factory=lambda: [0, 0, 0])
    tec_hit: list = field(default_factory=lambda: [0, 0, 0])
    tec_mp: list = field(default_factory=lambda: [0, 0, 0])
    tec_sta: list = field(default_factory=lambda: [0, 0, 0])
    mp_rate: int = 50
    hp_rate: int = 50

    # 能力
    ab: dict = field(default_factory=dict)   # ab[type] = True/False
    ab_dmg: dict = field(default_factory=dict)  # ab_dmg[type] = power
    ab_name: dict = field(default_factory=dict)  # ab_name[id] = name
    ab_type: dict = field(default_factory=dict)  # ab_type[id] = type

    # 狀態異常
    poison: int = 0     # 毒
    paralyzed: bool = False  # 麻痺
    revived: bool = False    # 復活已使用

    # 地形加成文字
    chi: str = ''
    comment: str = ''


@dataclass
class CombatResult:
    """一場戰鬥的結果"""
    win: bool = False
    lose: bool = False
    turns: list = field(default_factory=list)  # list of TurnResult
    max_damage: int = 0


@dataclass
class TurnResult:
    """一回合的結果"""
    turn_num: int = 0
    messages: str = ''
    player_hp: int = 0
    player_max_hp: int = 0
    player_mp: int = 0
    player_max_mp: int = 0
    enemy_hp: int = 0
    enemy_max_hp: int = 0
    enemy_mp: int = 0
    enemy_max_mp: int = 0


def load_abilities(fighter: Fighter):
    """載入能力資料到 Fighter — 對應 PARA 開頭的能力讀取"""
    skill_ids = [int(s) for s in (fighter.skills or '0,0').split(',') if s]
    equip_ability_ids = [fighter.arm_sta, fighter.pro_sta, fighter.acc_sta]
    all_ids = set(skill_ids + equip_ability_ids) - {0}

    if not all_ids:
        return

    abilities = Ability.query.filter(Ability.id.in_(all_ids)).all()
    for ab in abilities:
        fighter.ab[ab.ability_type] = True
        fighter.ab_dmg[ab.ability_type] = ab.power
        fighter.ab_name[ab.id] = ab.name
        fighter.ab_type[ab.id] = ab.ability_type


def load_techniques(fighter: Fighter):
    """載入技法資料 — 對應 TEC_OPEN"""
    parts = (fighter.technique or '0,0,0,50,50').split(',')
    tec_ids = [int(parts[i]) if i < len(parts) else 0 for i in range(3)]
    fighter.mp_rate = int(parts[3]) if len(parts) > 3 else 50
    fighter.hp_rate = int(parts[4]) if len(parts) > 4 else 50

    for i, tid in enumerate(tec_ids):
        if tid == 0:
            continue
        tec = db.session.get(Technique, tid)
        if tec:
            fighter.tec_name[i] = tec.name
            fighter.tec_str[i] = tec.power
            fighter.tec_hit[i] = tec.hit_rate
            fighter.tec_mp[i] = tec.mp_cost
            fighter.tec_sta[i] = tec.effect_type


def para(player: Fighter, enemy: Fighter, town_element: int = 0):
    """
    戰鬥參數初始化 — 對應 sub PARA
    計算攻擊力/防禦力/速度/暴擊率等
    """
    load_abilities(player)
    load_abilities(enemy)

    # 地形加成
    tup = player.ab_dmg.get(19, 0) / 100 if player.ab.get(19) else 0
    etup = enemy.ab_dmg.get(19, 0) / 100 if enemy.ab.get(19) else 0

    p_add_str = 0
    p_add_def = 0
    e_add_str = 0
    e_add_def = 0

    if town_element == player.element:
        p_add_str = int(player.str_stat * (0.1 + tup))
        p_add_def = int(player.vit * (0.1 + tup))
        player.chi = '○'
    elif ANTI_ELEMENT.get(player.element) == town_element:
        p_add_str = -int(player.str_stat * 0.1)
        p_add_def = -int(player.vit * 0.1)
        player.chi = '×'

    if town_element == enemy.element:
        e_add_str = int(enemy.str_stat * (0.1 + etup))
        e_add_def = int(enemy.vit * (0.1 + etup))
        enemy.chi = '○'
    elif ANTI_ELEMENT.get(enemy.element) == town_element:
        e_add_str = -int(enemy.str_stat * 0.1)
        e_add_def = -int(enemy.vit * 0.1)
        enemy.chi = '×'

    # 魔法武器 (ability 18)
    if player.ab.get(18):
        player.arm_dmg += int(player.int_stat * player.ab_dmg[18] / 100)
    if enemy.ab.get(18):
        enemy.arm_dmg += int(enemy.int_stat * enemy.ab_dmg[18] / 100)

    # 攻擊力計算
    player.attack = player.str_stat + player.arm_dmg + int(player.arm_wei / 5) + p_add_str
    if player.ab.get(2):  # 力量提升
        player.attack += int(player.ab_dmg[2] / 100 * player.attack)
    enemy.attack = enemy.str_stat + enemy.arm_dmg + int(enemy.arm_wei / 5) + e_add_str
    if enemy.ab.get(2):
        enemy.attack += int(enemy.ab_dmg[2] / 100 * enemy.attack)

    # 傷害減輕 (ability 3)
    if player.ab.get(3):
        enemy.attack -= int(player.ab_dmg.get(2, 0) / 100 * enemy.attack)
    if enemy.ab.get(3):
        player.attack -= int(enemy.ab_dmg.get(2, 0) / 100 * player.attack)

    # 防禦力計算
    player.defense = player.vit + player.pro_dmg + player.acc_dmg + p_add_def
    enemy.defense = enemy.vit + enemy.pro_dmg + enemy.acc_dmg + e_add_def

    # 魔法防禦
    player.magic_def = int(player.fai / 2)
    enemy.magic_def = int(enemy.fai / 2)

    # 爆擊
    player.critical = 20 + int(player.dex / 3)
    enemy.critical = 20 + int(enemy.dex / 3)
    if player.ab.get(10):
        player.critical += player.ab_dmg[10] * 10
    if enemy.ab.get(10):
        enemy.critical += enemy.ab_dmg[10] * 10
    player.critical = min(player.critical, 250)
    enemy.critical = min(enemy.critical, 250)

    # 迴避率
    player.dodge = int(player.dex / 3)
    enemy.dodge = int(enemy.dex / 3)
    if player.ab.get(8):
        player.dodge2 = player.ab_dmg[8] * 10
    if enemy.ab.get(8):
        enemy.dodge2 = enemy.ab_dmg[8] * 10

    # 速度（影響攻擊次數）
    p_haste = player.ab_dmg.get(4, 0) if player.ab.get(4) else 0
    e_haste = enemy.ab_dmg.get(4, 0) if enemy.ab.get(4) else 0
    player.speed = player.agi - player.arm_wei - player.pro_wei - player.acc_wei + p_haste * 50
    enemy.speed = enemy.agi - enemy.arm_wei - enemy.pro_wei - enemy.acc_wei + e_haste * 50

    # 敵 HP/MP 設定
    enemy.hp = enemy.max_hp
    enemy.mp = enemy.max_mp


def matt(player: Fighter, enemy: Fighter) -> str:
    """
    玩家攻擊回合 — 對應 sub MATT
    回傳戰鬥訊息 HTML
    """
    bmess = ''

    if player.paralyzed:
        bmess += f'<span class="msg-warning">{player.name}無法行動。</span><br>'
        player.paralyzed = False
        return bmess

    # 再生 (ability 1)
    if player.ab.get(1):
        heal = int(player.ab_dmg[1] / 100 * player.max_hp)
        player.hp = min(player.hp + heal, player.max_hp)
        bmess += f'[再生]{player.name}的HP恢復了<b class="heal">{heal}</b>。<br>'

    # 攻擊次數
    num_attacks = int(player.speed / 100 + random.random() * player.speed / 100) + 1
    num_attacks = max(1, min(num_attacks, 8))
    bmess += f'<b class="player-name">{player.name}</b>發動<b class="atk-count">{num_attacks}</b>次攻擊！<br>'

    # 中毒傷害
    if player.poison:
        poison_dmg = int(random.random() * player.max_hp * player.poison / 10)
        player.hp -= poison_dmg
        player.hp = max(1, player.hp)
        bmess += f'<span class="msg-warning">因中毒受到{poison_dmg}點傷害。</span><br>'

    win = False
    max_dmg = 0

    for _ in range(num_attacks):
        rand_val = random.randint(0, 99)
        at = False
        sv = 0
        dmg = 0

        # 技選擇
        if player.hp / (player.max_hp + 1) * 100 <= player.hp_rate:
            magic = 2
        elif player.mp / (player.max_mp + 1) * 100 <= player.mp_rate:
            magic = 1
        else:
            magic = 0

        # MP 消費計算
        mp_cost = player.tec_mp[magic]
        if player.ab.get(6):
            mp_cost -= int(player.tec_mp[magic] * player.ab_dmg[6] / 100)

        hit_up = 1.5 if player.ab.get(25) else 1.0

        if player.tec_hit[magic] * hit_up > rand_val and mp_cost <= player.mp:
            # 技命中
            bmess += f'<b class="tech-name">{player.tec_name[magic]}</b> '
            if player.ab.get(6):
                bmess += f'<b class="heal">(消耗減少{player.ab_dmg[6]}%)</b> '
            player.mp -= mp_cost

            sta = player.tec_sta[magic]
            if sta == 1:  # HP恢復
                heal = player.tec_str[magic] + int(random.random() * player.fai / 2)
                player.hp = min(player.hp + heal, player.max_hp)
                bmess += f'HP恢復了<b class="heal">{heal}</b>。<br>'
            elif sta == 2:  # HP+MP恢復
                player.hp = min(player.hp + int(player.max_hp / 10), player.max_hp)
                player.mp = min(player.mp + int(player.max_mp / 10), player.max_mp)
                bmess += '<span class="heal">HP與MP恢復了。</span><br>'
            elif sta == 3:  # 攻擊力上升
                player.attack += int(player.fai * (player.tec_str[magic] / 100))
                bmess += '<span class="heal">攻擊力上升了。</span><br>'
            elif sta == 4:  # 防禦力上升
                player.defense += int(player.fai * (player.tec_str[magic] / 100))
                bmess += '<span class="heal">耐久力上升了。</span><br>'
            elif sta == 5:  # 魔防上升
                player.magic_def += int(player.fai * (player.tec_str[magic] / 100))
                bmess += '<span class="heal">魔法耐久力上升了。</span><br>'
            elif sta == 6:  # 吸收攻擊
                dmg = player.tec_str[magic] + int(random.random() * player.int_stat) - enemy.magic_def
                sv = 6
                at = True
            elif sta == 7:  # MP吸收
                stolen = int(random.random() * enemy.max_mp / 5)
                enemy.mp = max(0, enemy.mp - stolen)
                player.mp = min(player.mp + stolen, player.max_mp)
                bmess += f'{enemy.name}的MP被奪取了<span class="msg-warning">{stolen}</span>。<br>'
            elif sta == 8:  # 比例傷害
                enemy.hp = int(enemy.hp - enemy.hp / player.tec_str[magic])
                bmess += f'{enemy.name}的體力減少了{player.tec_str[magic]}分之1。<br>'
            else:
                # 一般魔法攻擊
                dmg = player.tec_str[magic] + int(random.random() * player.int_stat) - enemy.magic_def
                if player.ab.get(5):
                    dmg += int(dmg * player.ab_dmg[5] / 100)
                    bmess += f'<b class="heal">(傷害+{player.ab_dmg[5]}%)</b> '
                if enemy.ab.get(7):
                    dmg -= int(dmg * enemy.ab_dmg[7] / 100)
                    bmess += f'<b class="heal">(傷害-{enemy.ab_dmg[7]}%)</b> '
                at = True
                if sta == 9: sv = 1    # 即死
                elif sta == 10: sv = 2  # 防禦下降
                elif sta == 11: sv = 3  # 毒
                elif sta == 12: sv = 4  # 命中下降
                elif sta == 13: sv = 5  # 麻痺
                elif sta == 14: sv = 7  # 減速
            bmess += '<br>'
        else:
            # 一般攻擊
            max_atk = max(1, player.attack - enemy.defense // 2)
            dmg = int(random.random() * max_atk)
            at = True

        if at:
            hit_rand = random.randint(0, 1)
            # 反擊 (ability 12)
            if enemy.ab.get(12) and 100 > int(random.random() * (1200 - enemy.fai)):
                counter_dmg = int((dmg + int(random.random() * enemy.str_stat)) / 2 * enemy.ab_dmg[12])
                counter_dmg = max(1, counter_dmg)
                player.hp -= counter_dmg
                player.hp = max(1, player.hp)
                dmg = 0
                hit_rand = 0
                bmess += f'<b class="heal">{enemy.name}的反擊！</b><br>對{player.name}造成了<b class="dmg">{counter_dmg}</b>點傷害。'
            elif enemy.dodge > int(random.random() * 1000):
                bmess += f'<b class="heal">{enemy.name}敏捷地閃避了。</b><br>'
                dmg = 0
                hit_rand = 0
            elif enemy.dodge2 > int(random.random() * 1000):
                bmess += f'<b class="heal">{enemy.name}發動了防禦。</b><br>'
                dmg = 0
                hit_rand = 0
            elif player.critical > int(random.random() * 1000):
                bmess += '<b class="crit">暴擊！</b>'
                dmg = int(dmg * 1.5)
                if player.ab.get(23):
                    dmg = int(dmg * player.ab_dmg[23])

            # 傷害處理
            if dmg <= 0 and hit_rand == 0:
                dmg = 0
                bmess += f'<span class="msg-warning">{enemy.name}未受到傷害。</span><br>'
            elif dmg <= 0:
                dmg = 1

            if dmg > 0:
                bmess += f'<span class="msg-warning">{enemy.name}</span>受到了<b class="dmg">{dmg}</b>點傷害。<br>'
                # 追加效果
                bmess += _apply_attack_effects(player, enemy, dmg, sv)
                if max_dmg < dmg:
                    max_dmg = dmg

            enemy.hp -= dmg

        if enemy.hp <= 0:
            bmess += f'<span class="msg-warning">{enemy.name}被打倒了！</span><br>'
            # 復活 (ability 11)
            if enemy.ab.get(11) and random.randint(0, 99) < enemy.ab_dmg[11] and not player.revived:
                enemy.hp = int(enemy.max_hp / 2)
                player.revived = True
                bmess += f'<span class="msg-warning">{enemy.name}復活了！</span><br>'
            else:
                enemy.hp = 0
                win = True
                break

    return bmess, win, max_dmg


def eatt(player: Fighter, enemy: Fighter) -> str:
    """
    敵方攻擊回合 — 對應 sub EATT（MATT 的鏡像）
    """
    bmess = ''

    if enemy.paralyzed:
        bmess += f'<span class="msg-warning">{enemy.name}無法行動。</span><br>'
        enemy.paralyzed = False
        return bmess, False

    # 再生
    if enemy.ab.get(1):
        heal = int(enemy.ab_dmg[1] / 100 * enemy.max_hp)
        enemy.hp = min(enemy.hp + heal, enemy.max_hp)
        bmess += f'[再生]{enemy.name}的HP恢復了<b class="heal">{heal}</b>。<br>'

    num_attacks = int(enemy.speed / 100 + random.random() * enemy.speed / 100) + 1
    num_attacks = max(1, min(num_attacks, 8))
    bmess += f'<b class="enemy-name">{enemy.name}</b>發動<b class="atk-count">{num_attacks}</b>次攻擊！<br>'

    if enemy.poison:
        poison_dmg = int(random.random() * enemy.max_hp * enemy.poison / 10)
        enemy.hp -= poison_dmg
        enemy.hp = max(1, enemy.hp)
        bmess += f'<span class="msg-warning">因中毒受到{poison_dmg}點傷害。</span><br>'

    lose = False

    for _ in range(num_attacks):
        rand_val = random.randint(0, 99)
        at = False
        sv = 0
        dmg = 0

        if enemy.hp / (enemy.max_hp + 1) * 100 <= enemy.hp_rate:
            magic = 2
        elif enemy.mp / (enemy.max_mp + 1) * 100 <= enemy.mp_rate:
            magic = 1
        else:
            magic = 0

        mp_cost = enemy.tec_mp[magic]
        if enemy.ab.get(6):
            mp_cost -= int(enemy.tec_mp[magic] * enemy.ab_dmg[6] / 100)

        hit_up = 1.5 if enemy.ab.get(25) else 1.0

        if enemy.tec_hit[magic] * hit_up > rand_val and mp_cost <= enemy.mp:
            bmess += f'<b class="tech-name">{enemy.tec_name[magic]}</b> '
            if enemy.ab.get(6):
                bmess += f'<b class="heal">(消耗減少{enemy.ab_dmg[6]}%)</b> '
            enemy.mp -= mp_cost

            sta = enemy.tec_sta[magic]
            if sta == 1:
                heal = enemy.tec_str[magic] + int(random.random() * enemy.fai / 2)
                enemy.hp = min(enemy.hp + heal, enemy.max_hp)
                bmess += f'HP恢復了<b class="heal">{heal}</b>。<br>'
            elif sta == 2:
                enemy.hp = min(enemy.hp + int(enemy.max_hp / 10), enemy.max_hp)
                enemy.mp = min(enemy.mp + int(enemy.max_mp / 10), enemy.max_mp)
                bmess += '<span class="heal">HP與MP恢復了。</span><br>'
            elif sta == 3:
                enemy.attack += int(enemy.fai * (enemy.tec_str[magic] / 100))
                bmess += '<span class="heal">攻擊力上升了。</span><br>'
            elif sta == 4:
                enemy.defense += int(enemy.fai * (enemy.tec_str[magic] / 100))
                bmess += '<span class="heal">耐久力上升了。</span><br>'
            elif sta == 5:
                enemy.magic_def += int(enemy.fai * (enemy.tec_str[magic] / 100))
                bmess += '<span class="heal">魔法耐久力上升了。</span><br>'
            elif sta == 6:
                dmg = enemy.tec_str[magic] + int(random.random() * enemy.int_stat) - player.magic_def
                sv = 6
                at = True
            elif sta == 7:
                stolen = int(random.random() * player.max_mp / 5)
                player.mp = max(0, player.mp - stolen)
                enemy.mp = min(enemy.mp + stolen, enemy.max_mp)
                bmess += f'奪取了{player.name}的MP<b class="msg-warning">{stolen}</b>。<br>'
            elif sta == 8:
                player.hp = int(player.hp - player.hp / enemy.tec_str[magic])
                bmess += f'{player.name}的體力減少了{enemy.tec_str[magic]}分之1。<br>'
            else:
                dmg = enemy.tec_str[magic] + int(random.random() * enemy.int_stat) - player.magic_def
                if enemy.ab.get(5):
                    dmg += int(dmg * enemy.ab_dmg[5] / 100)
                if player.ab.get(7):
                    dmg -= int(dmg * player.ab_dmg[7] / 100)
                at = True
                if sta == 9: sv = 1
                elif sta == 10: sv = 2
                elif sta == 11: sv = 3
                elif sta == 12: sv = 4
                elif sta == 13: sv = 5
                elif sta == 14: sv = 7
            bmess += '<br>'
        else:
            max_atk = max(1, enemy.attack - player.defense // 2)
            dmg = int(random.random() * max_atk)
            at = True

        if at:
            hit_rand = random.randint(0, 1)
            if player.ab.get(12) and 100 > int(random.random() * (1200 - player.fai)):
                counter_dmg = int((dmg + int(random.random() * player.str_stat)) / 2 * player.ab_dmg[12])
                counter_dmg = max(1, counter_dmg)
                enemy.hp -= counter_dmg
                enemy.hp = max(1, enemy.hp)
                dmg = 0
                hit_rand = 0
                bmess += f'<b class="heal">{player.name}的反擊！</b><br>對{enemy.name}造成了<b class="dmg">{counter_dmg}</b>點傷害。'
            elif player.dodge > int(random.random() * 1000):
                bmess += f'<b class="heal">{player.name}敏捷地閃避了。</b><br>'
                dmg = 0
                hit_rand = 0
            elif player.dodge2 > int(random.random() * 1000):
                bmess += f'<b class="heal">{player.name}發動了防禦。</b><br>'
                dmg = 0
                hit_rand = 0
            elif enemy.critical > int(random.random() * 1000):
                bmess += '<b class="crit">暴擊！</b>'
                dmg = int(dmg * 1.5)
                if enemy.ab.get(23):
                    dmg = int(dmg * enemy.ab_dmg[23])

            if dmg <= 0 and hit_rand == 0:
                dmg = 0
                bmess += f'<span class="heal">{player.name}未受到傷害。</span><br>'
            elif dmg <= 0:
                dmg = 1

            if dmg > 0:
                bmess += f'<span class="heal">{player.name}</span>受到了<b class="dmg">{dmg}</b>點傷害。<br>'
                bmess += _apply_defense_effects(player, enemy, dmg, sv)

            player.hp -= dmg

        if player.hp <= 0:
            bmess += f'<span class="msg-warning">{player.name}力竭倒下了。</span><br>'
            if player.ab.get(11) and random.randint(0, 99) < player.ab_dmg[11] and not enemy.revived:
                player.hp = int(player.max_hp / 2)
                enemy.revived = True
                bmess += f'<span class="msg-warning">{player.name}復活了！</span><br>'
            else:
                player.hp = 0
                lose = True
                break

    return bmess, lose


def _apply_attack_effects(attacker: Fighter, defender: Fighter, dmg: int, sv: int) -> str:
    """攻擊方的追加效果"""
    msg = ''
    if sv == 2:
        defender.defense -= int(defender.defense / 10)
        defender.defense = max(0, defender.defense)
        msg += f'{defender.name}的防禦力下降了。<br>'
    elif random.randint(0, 3) == 2 and sv == 3 or (attacker.ab.get(14) and random.randint(0, 5) < 1):
        defender.poison = attacker.ab_dmg.get(14, 1) or 1
        msg += f'<span class="msg-warning">{defender.name}中毒了。</span><br>'
    elif sv == 4 and defender.dodge < 1000:
        defender.dodge += 40
        msg += f'<span class="msg-warning">{defender.name}的命中率下降了。</span><br>'
    elif (random.randint(0, 7) == 2 and sv == 5) or (attacker.ab.get(24) and random.randint(0, 14) == 1):
        defender.paralyzed = True
        msg += f'<span class="msg-warning">{defender.name}麻痺了。</span><br>'
    elif sv == 6 or (attacker.ab.get(28) and random.randint(0, 3) == 1):
        heal = int(dmg / 2)
        attacker.hp = min(attacker.hp + heal, attacker.max_hp)
        msg += f'{attacker.name}吸收了<span class="heal">{heal}</span>HP。<br>'
    elif (random.randint(0, 7) == 2 and sv == 7) or (attacker.ab.get(16) and random.randint(0, 99) < attacker.ab_dmg.get(16, 0)):
        defender.speed = max(0, defender.speed - 50)
        msg += f'<span class="msg-warning">{defender.name}的速度變慢了。</span><br>'
    elif attacker.ab.get(26) and random.randint(0, 2) == 1:
        extra = random.randint(0, 199)
        msg += f'<span class="msg-warning">追加造成了<b>{extra}</b>點傷害。</span><br>'
        defender.hp -= extra
    elif attacker.ab.get(27) and random.randint(0, 2) == 1:
        stolen = random.randint(0, 149)
        defender.mp = max(0, defender.mp - stolen)
        attacker.mp = min(attacker.mp + stolen, attacker.max_mp)
        msg += f'{defender.name}的MP被奪取了<span class="msg-warning">{stolen}</span>。<br>'

    # 即死 (sv==1)
    if (defender.name != '城塞' and random.randint(0, 29) == 7 and sv == 1) or \
       (defender.name != '城塞' and attacker.ab.get(9) and random.randint(0, 999) < attacker.ab_dmg.get(9, 0)):
        defender.hp = 0
        msg += f'<span class="msg-warning">{defender.name}即死了。</span><br>'

    return msg


def _apply_defense_effects(defender: Fighter, attacker: Fighter, dmg: int, sv: int) -> str:
    """被攻擊方的追加效果（EATT 的追加效果部分）"""
    msg = ''
    if sv == 2:
        defender.defense -= int(defender.defense / 10)
        defender.defense = max(0, defender.defense)
        msg += f'{defender.name}的防禦力下降了。<br>'
    elif (random.randint(0, 3) == 2 and sv == 3) or (attacker.ab.get(14) and random.randint(0, 5) < 1):
        defender.poison = attacker.ab_dmg.get(14, 1) or 1
        msg += f'<span class="msg-warning">{defender.name}中毒了。</span><br>'
    elif sv == 4 and defender.dodge < 1000:
        defender.dodge += 40
        msg += f'<span class="msg-warning">{defender.name}的命中率下降了。</span><br>'
    elif (random.randint(0, 7) == 2 and sv == 5) or (attacker.ab.get(24) and random.randint(0, 14) == 1):
        defender.paralyzed = True
        msg += f'<span class="msg-warning">{defender.name}麻痺了。</span><br>'
    elif sv == 6 or (attacker.ab.get(28) and random.randint(0, 3) == 1):
        heal = int(dmg / 2)
        attacker.hp = min(attacker.hp + heal, attacker.max_hp)
        msg += f'{attacker.name}吸收了<span class="heal">{heal}</span>HP。<br>'
    elif (random.randint(0, 7) == 2 and sv == 7) or (attacker.ab.get(16) and random.randint(0, 999) < attacker.ab_dmg.get(16, 0)):
        defender.speed = max(0, defender.speed - 50)
        msg += f'<span class="msg-warning">{defender.name}的速度變慢了。</span><br>'
    elif (random.randint(0, 29) == 7 and sv == 1) or (attacker.ab.get(9) and random.randint(0, 999) < attacker.ab_dmg.get(9, 0)):
        defender.hp = 0
        msg += f'<span class="msg-warning">{defender.name}即死了。</span><br>'
    elif attacker.ab.get(26) and random.randint(0, 2) == 1:
        extra = random.randint(0, 199)
        msg += f'<span class="msg-warning">追加造成了<b>{extra}</b>點傷害。</span><br>'
        defender.hp -= extra
    elif attacker.ab.get(27) and random.randint(0, 2) == 1:
        stolen = random.randint(0, 149)
        defender.mp = max(0, defender.mp - stolen)
        attacker.mp = min(attacker.mp + stolen, attacker.max_mp)
        msg += f'{defender.name}的MP被奪取了<span class="msg-warning">{stolen}</span>。<br>'

    return msg


def lvup(char, player: Fighter) -> str:
    """
    升級處理 — 對應 sub LVUP
    直接修改 Character ORM 物件
    回傳訊息
    """
    new_lv = min(char.exp // 100 + 1, 100)
    if char.exp > 9999:
        char.exp = 9999
    old_lv = char.level
    if new_lv <= old_lv:
        return ''

    msg = ''
    caps = char.parsed_stat_caps

    for _ in range(new_lv - old_lv):
        msg += f'<span class="msg-warning">{char.name}升級了！</span><br>'

        hp_up = random.randint(0, int(char.vit / 40 + char.fai / 80 + 7)) + 1
        mp_up = random.randint(0, int(char.int_stat / 40 + char.fai / 80 + 1))
        char.max_hp += hp_up
        char.max_mp += mp_up

        str_up = random.randint(0, 1)
        vit_up = random.randint(0, 1)
        int_up = random.randint(0, 1)
        fai_up = random.randint(0, 1)
        dex_up = random.randint(0, 1)
        agi_up = random.randint(0, 1)
        char.str_stat += str_up
        char.vit += vit_up
        char.int_stat += int_up
        char.fai += fai_up
        char.dex += dex_up
        char.agi += agi_up

        # 限界值檢查
        max_hp_cap = caps['max_str'] * 5 + caps['max_vit'] * 10 + caps['max_fai'] * 3 - 2000
        max_mp_cap = caps['max_int'] * 5 + caps['max_fai'] * 3 - 800

        cap_hit = ''
        if char.max_hp > max_hp_cap:
            char.max_hp = max_hp_cap
            cap_hit = '（已達到限界。）'
        if char.max_mp > max_mp_cap:
            char.max_mp = max_mp_cap

        if char.str_stat > caps['max_str']: char.str_stat = caps['max_str']
        if char.vit > caps['max_vit']: char.vit = caps['max_vit']
        if char.int_stat > caps['max_int']: char.int_stat = caps['max_int']
        if char.fai > caps['max_fai']: char.fai = caps['max_fai']
        if char.dex > caps['max_dex']: char.dex = caps['max_dex']
        if char.agi > caps['max_agi']: char.agi = caps['max_agi']

        msg += f'HP提升了<span class="heal">{hp_up}</span>{cap_hit}<br>'
        msg += f'MP提升了<span class="heal">{mp_up}</span><br>'
        if str_up: msg += f'力量提升了<span class="heal">{str_up}</span><br>'
        if vit_up: msg += f'耐力提升了<span class="heal">{vit_up}</span><br>'
        if int_up: msg += f'知力提升了<span class="heal">{int_up}</span><br>'
        if fai_up: msg += f'精神提升了<span class="heal">{fai_up}</span><br>'
        if dex_up: msg += f'靈巧提升了<span class="heal">{dex_up}</span><br>'
        if agi_up: msg += f'敏捷提升了<span class="heal">{agi_up}</span><br>'

    return msg


def maxup(char, player: Fighter) -> str:
    """
    限界值上升 — 對應 sub MAXUP
    """
    from farland.common import append_game_log

    roll = random.randint(0, 99)
    if roll < 1:  # 1%
        msg = f'<b class="msg-warning">{char.name}覺醒了！</b>'
        append_game_log(1, f'[覺醒]{char.name}覺醒了！！')
        rate = 15
    elif roll < 6:  # 5%
        msg = f'<b class="msg-warning">{char.name}急速成長了！</b>'
        append_game_log(1, f'[急速成長]{char.name}達成了急速成長！')
        rate = 5
    else:
        msg = f'<b class="heal">{char.name}的限界值上升了！</b>'
        rate = 1

    caps = char.parsed_stat_caps
    bonus = JOB_STAT_CAP_BONUS.get(char.job_type, [1, 1, 1, 1, 1, 1])
    cap_keys = ['max_str', 'max_vit', 'max_int', 'max_fai', 'max_dex', 'max_agi']

    new_caps = []
    for i, key in enumerate(cap_keys):
        val = caps[key] + bonus[i] * rate
        val = min(val, 400)
        new_caps.append(str(val))

    char.stat_caps = ','.join(new_caps)
    return msg + '<br>'


def make_fighter_from_char(char) -> Fighter:
    """Character ORM → Fighter dataclass"""
    from farland.services.equipment import parse_equip
    weapon = parse_equip(char.weapon)
    armor = parse_equip(char.armor)
    accessory = parse_equip(char.accessory)

    return Fighter(
        name=char.name,
        chara_img=char.chara_img,
        element=char.element,
        hp=char.hp, max_hp=char.max_hp,
        mp=char.mp, max_mp=char.max_mp,
        str_stat=char.str_stat, vit=char.vit,
        int_stat=char.int_stat, fai=char.fai,
        dex=char.dex, agi=char.agi,
        job_type=char.job_type, job_class=char.job_class,
        arm_dmg=weapon.damage, arm_wei=weapon.weight, arm_name=weapon.name,
        pro_dmg=armor.damage, pro_wei=armor.weight, pro_name=armor.name,
        acc_dmg=accessory.damage, acc_wei=accessory.weight, acc_name=accessory.name,
        arm_sta=weapon.ability, pro_sta=armor.ability, acc_sta=accessory.ability,
        technique=char.technique or '0,0,0,50,50',
        skills=char.skills or '',
        stat_caps=char.stat_caps or '200,200,200,200,200,200',
        comment=char.comment or '',
    )


def make_fighter_from_monster(mon, player_max_hp: int = 0, rare: bool = False) -> Fighter:
    """Monster ORM → Fighter dataclass"""
    stats = [int(x) for x in mon.stats.split(',')]
    # stats: hp, mp, str, vit, int, fai, dex, agi, element
    ehp, emp = stats[0], stats[1]
    estr, evit = stats[2], stats[3]
    eint, efai = stats[4] if len(stats) > 4 else 0, stats[5] if len(stats) > 5 else 0
    edex = stats[6] if len(stats) > 6 else 0
    eagi = stats[7] if len(stats) > 7 else 0
    eele = stats[8] if len(stats) > 8 else 0

    if rare:
        max_hp = ehp
        max_mp = emp
    else:
        max_hp = int((ehp + player_max_hp / 2) / 1.5)
        max_mp = emp + int(random.random() * emp / 2)

    f_str = int((estr + player_max_hp * 0) / 1.0) if rare else int((estr + (estr + evit) / 2) / 1.7)
    f_vit = evit if rare else int((evit + (estr + evit) / 2) / 1.7)

    area = mon.area
    if area == 1: img = 'enemy'
    elif area == 2: img = 'enemy2'
    elif area == 3: img = 'enemy3'
    else: img = 'enemy4'

    return Fighter(
        name=mon.name,
        chara_img=img,
        element=eele,
        hp=max_hp, max_hp=max_hp,
        mp=max_mp, max_mp=max_mp,
        str_stat=f_str, vit=f_vit,
        int_stat=eint, fai=efai,
        dex=edex, agi=eagi,
        technique=mon.weapon or '0,0,0,50,50',
        skills=mon.armor or '',
    )


def run_battle(player: Fighter, enemy: Fighter, town_element: int = 0,
               max_turns: int = 30) -> CombatResult:
    """
    完整戰鬥流程
    回傳 CombatResult
    """
    load_techniques(player)
    load_techniques(enemy)
    para(player, enemy, town_element)

    result = CombatResult()
    max_dmg = 0

    for turn_num in range(1, max_turns + 1):
        turn_msgs = ''

        # 先攻判定
        if player.ab.get(15) and player.ab_dmg.get(15, 0) > enemy.ab_dmg.get(15, 0) and \
           random.randint(0, max(1, 3 - player.ab_dmg.get(15, 0))) == 0:
            first = True
        elif enemy.ab.get(15) and enemy.ab_dmg.get(15, 0) > player.ab_dmg.get(15, 0) and \
             random.randint(0, max(1, 3 - enemy.ab_dmg.get(15, 0))) == 0:
            first = False
        elif random.randint(0, max(1, player.dex)) > random.randint(0, max(1, enemy.dex)):
            first = True
        else:
            first = False

        if first:
            if player.hp > 0:
                msg, win, t_dmg = matt(player, enemy)
                turn_msgs += msg
                max_dmg = max(max_dmg, t_dmg)
            if enemy.hp > 0 and not (enemy.hp <= 0):
                msg, lose = eatt(player, enemy)
                turn_msgs += msg
        else:
            if enemy.hp > 0:
                msg, lose = eatt(player, enemy)
                turn_msgs += msg
            if player.hp > 0 and not (player.hp <= 0):
                msg, win, t_dmg = matt(player, enemy)
                turn_msgs += msg
                max_dmg = max(max_dmg, t_dmg)
            else:
                win = False

        tr = TurnResult(
            turn_num=turn_num,
            messages=turn_msgs,
            player_hp=max(0, player.hp), player_max_hp=player.max_hp,
            player_mp=max(0, player.mp), player_max_mp=player.max_mp,
            enemy_hp=max(0, enemy.hp), enemy_max_hp=enemy.max_hp,
            enemy_mp=max(0, enemy.mp), enemy_max_mp=enemy.max_mp,
        )
        result.turns.append(tr)

        if enemy.hp <= 0:
            result.win = True
            break
        if player.hp <= 0:
            result.lose = True
            break

    result.max_damage = max_dmg
    return result
