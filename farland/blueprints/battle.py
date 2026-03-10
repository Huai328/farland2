"""
Farland History Ⅱ — Battle Blueprint
對應 battle.cgi 及 battle/ 目錄的 6 個戰鬥模式
"""
import time
import random
from flask import Blueprint, render_template, request, redirect, url_for, flash

from farland.models import (
    db, Character, Monster, CharacterItem, BattleState, Equipment,
)
from farland.auth import login_required
from farland.common import (
    get_town_for_character, get_country, append_game_log,
)
from farland.battle_support import (
    Fighter, make_fighter_from_char, make_fighter_from_monster,
    run_battle, load_techniques, para, lvup, maxup,
)
from farland.services.equipment import parse_equip, add_to_inventory
from config import Config
from game_data import (
    BATTLE_LOCATIONS, ELEMENTS, ELEMENT_BG, ELEMENT_FG,
    JOBS, JOB_STAT_CAP_BONUS,
)

bp = Blueprint('battle', __name__, url_prefix='/battle')


@bp.route('/', methods=['GET', 'POST'])
@login_required
def dispatch(char):
    """Battle 主分發器"""
    mode = request.form.get('mode') or request.args.get('mode', '')
    handlers = {
        'battle': pve_start,
        'battle2': arena_battle,
        'kunren': kunren_select,
        'kunren2': kunren_battle,
        'toubatsu': toubatsu_select,
        'toubatsu2': toubatsu_battle,
        'battle3': boss_battle,
    }
    # 數字 mode 也走 PvE
    if mode.isdigit():
        return pve_battle(char, int(mode))

    handler = handlers.get(mode)
    if not handler:
        flash('尚未選擇選單。')
        return redirect(url_for('main.top'))
    return handler(char)


# ===== PvE 一般戰鬥 =====

def pve_start(char):
    """選擇戰鬥場所後進入 pve_battle"""
    mode = request.form.get('battle_mode', type=int)
    if mode is None:
        flash('請選擇戰場。')
        return redirect(url_for('main.top'))
    return pve_battle(char, mode)


def pve_battle(char, battle_mode: int):
    """PvE 戰鬥 — 對應 battle/battle.pl:bat"""
    if battle_mode not in BATTLE_LOCATIONS:
        flash('無效的戰場。')
        return redirect(url_for('main.top'))

    # 戰鬥冷卻檢查
    now = int(time.time())
    btime = Config.BATTLE_TIME - (now - (char.last_action or 0))
    if btime > 0:
        flash(f'距離下次戰鬥還需等待 {btime} 秒。')
        return redirect(url_for('main.top'))

    # 隱藏迷宮存取檢查
    hidden_checks = {
        5: lambda: char.exp % 11 == 0,
        6: lambda: (char.oya or 0) % 40 == 0,
        7: lambda: (char.oya or 0) % 80 == 7,
        8: lambda: (char.oya or 0) % 300 == 8,
        9: lambda: (char.oya or 0) % 1000 == 9,
        10: lambda: char.oya == 777,
        11: lambda: (char.oya or 0) % 2500 == 17,
        12: lambda: char.oya == 55555,
        13: lambda: (char.oya or 0) % 5000 == 773,
        14: lambda: char.oya == 77777,
        15: lambda: char.oya in (775, 776),
    }
    if battle_mode in hidden_checks and not hidden_checks[battle_mode]():
        flash('偵測到非法操作。')
        return redirect(url_for('main.top'))

    # 怪物等級決定
    mode_to_level = {
        1: 1, 2: 2, 3: 3, 4: 4,
        5: 1, 6: 2, 7: 2, 8: 3, 9: 4,
        10: 1, 11: 2, 12: 3, 13: 3, 14: 1, 15: 1,
    }
    mon_level = mode_to_level.get(battle_mode, 1)

    # 稀有怪物判定 (2%)
    rare = random.randint(0, 49) == 7

    # 怪物選擇
    monsters = Monster.query.filter_by(area=mon_level).all()
    if not monsters:
        flash('找不到怪物。')
        return redirect(url_for('main.top'))
    mon = random.choice(monsters)

    # 建立 Fighter
    player = make_fighter_from_char(char)
    enemy = make_fighter_from_monster(mon, char.max_hp, rare)

    # 城鎮資訊
    town = get_town_for_character(char.position)
    town_ele = town.element if town else 0

    # 執行戰鬥
    result = run_battle(player, enemy, town_ele, max_turns=30)

    # 戰鬥後處理
    post_msg = ''
    get_ex = 0
    get_gold = 0
    get_abp = battle_mode

    epoint = int((enemy.max_hp + enemy.max_mp) / 3) + enemy.str_stat + enemy.vit + \
             enemy.int_stat + enemy.fai + enemy.dex + enemy.agi

    if result.win:
        char.win_streak = (char.win_streak or 0) + 1
        char.total_wins = (char.total_wins or 0) + 1

        get_ex = int(epoint / 15) + 10 + random.randint(0, 9)
        get_ex = max(10, min(get_ex, 50)) + random.randint(0, 9)

        # 隱藏地城獎勵
        z_gold = 0
        if battle_mode == 5 and char.exp < 9900:
            get_ex = 100
            z_gold = int(random.random() * char.exp * 20)
            post_msg += f'{char.name}發現了<b>隱藏的寶箱</b>！<br><b>{z_gold}</b>Gold。<br>'
        elif battle_mode in (7, 8):
            get_ex = 100
            z_gold = int(random.random() * (500000 if battle_mode == 7 else 2000000))
            post_msg += f'{char.name}發現了<b>隱藏的寶箱</b>！<br><b>{z_gold}</b>Gold。<br>'
        elif battle_mode == 6:
            get_ex = 100
            get_abp = random.randint(0, 49)
            if random.randint(0, 19) == 7:
                get_abp = 300
            z_gold = int(random.random() * 100000)
            post_msg += f'{char.name}發現了<b>隱藏的寶箱</b>！<br><b>{z_gold}</b>Gold。<br>'
        elif battle_mode == 9:
            get_ex = 100
            get_abp = 100 + random.randint(0, 199)
            if random.randint(0, 19) == 7:
                get_abp = 1000
            # 隨機極限+1
            stat_names = ['力量', '耐力', '智力', '精神', '靈巧', '敏捷']
            stat_attrs = ['str_stat', 'vit', 'int_stat', 'fai', 'dex', 'agi']
            idx = random.randint(0, 5)
            caps = char.parsed_stat_caps
            cap_keys = ['max_str', 'max_vit', 'max_int', 'max_fai', 'max_dex', 'max_agi']
            caps[cap_keys[idx]] = min(400, caps[cap_keys[idx]] + 1)
            char.stat_caps = ','.join(str(caps[k]) for k in cap_keys)
            post_msg += f'<span class="heal">{stat_names[idx]}的極限提升了1！！</span><br>'
        elif battle_mode == 13:
            get_abp = 1000

        # 經驗值增加被動技能
        if player.ab.get(22):
            get_ex = int(get_ex * 1.2)
            get_abp += 1

        if rare:
            get_abp = battle_mode * 20

        # 經驗值/金幣
        if char.exp < 9900:
            char.exp += get_ex
        char.total_exp = (char.total_exp or 0) + get_ex

        get_gold = (epoint + int(random.random() * epoint / 5)) * 4

        # 發現金幣
        add_gold = 0
        find_bonus = int(player.ab_dmg.get(13, 0) / 750) if player.ab.get(13) else 0
        if random.randint(0, max(1, 10 - find_bonus)) == 1:
            add_gold = int(random.random() * (get_gold * 5 + 1000))
            post_msg += f'還撿到了<b>{add_gold}</b>Gold。<br>'

        total_gold = get_gold + add_gold + z_gold
        char.gold += total_gold
        char.ability_pts += get_abp

        # JP 更新
        jp = char.parsed_job_points
        jp[char.job_type] = min(jp[char.job_type] + get_abp, Config.MAX_JOB_LEVEL)
        char.job_points = ','.join(str(p) for p in jp)

        # 升級
        post_msg += lvup(char, player)

        # 極限提升判定
        caps = char.parsed_stat_caps
        cap_keys = ['max_str', 'max_vit', 'max_int', 'max_fai', 'max_dex', 'max_agi']
        maxtotal = sum(caps[k] for k in cap_keys)
        maxrand = int((maxtotal - 1000) / 20)
        if maxrand > 0:
            maxrand2 = maxrand * maxrand
            if player.ab.get(22):
                maxrand2 = int(maxrand2 / 1.5)
            if maxrand2 > 0 and (random.randint(0, maxrand2) == 1 or battle_mode == 13):
                post_msg += maxup(char, player)

        # 寶箱掉落
        drop_msg = _try_drop_item(char, player, battle_mode, rare)
        if drop_msg:
            post_msg += drop_msg

    elif result.lose:
        char.gold = max(0, char.gold // 2)

    # 更新狀態
    char.last_action = now
    char.oya = random.randint(0, 19999)

    # 特殊 moya 處理
    if battle_mode == 11:
        char.oya = 775 + random.randint(0, 11)
    elif battle_mode == 15:
        char.oya = 777 + random.randint(0, 3) if random.randint(0, 29) != 7 else 77777
    elif battle_mode == 8 and random.randint(0, 9) == 1 and not result.lose:
        char.oya = 55555
    if random.randint(0, 149999) == 777:
        char.oya = 77777

    char.hp = max(0, player.hp)
    char.mp = max(0, player.mp)
    db.session.commit()

    location_name = BATTLE_LOCATIONS.get(battle_mode, '不明')
    return render_template('battle/result.html',
                           char=char, result=result, player=player, enemy=enemy,
                           location=location_name, battle_mode=battle_mode,
                           town=town, get_ex=get_ex, get_gold=get_gold,
                           get_abp=get_abp, post_msg=post_msg)


# ===== 練武場 (Arena) =====

def arena_battle(char):
    """練武場 — 對應 battle/battle2.pl（vs 冠軍）"""
    if char.gold < 10000:
        flash('參加費10000G不足。')
        return redirect(url_for('main.top'))

    now = int(time.time())
    btime = Config.BATTLE_TIME - (now - (char.last_action or 0))
    if btime > 0:
        flash(f'距離下次戰鬥還需等待 {btime} 秒。')
        return redirect(url_for('main.top'))

    char.gold -= 10000

    # 冠軍根據玩家的狀態數值生成
    player = make_fighter_from_char(char)
    enemy = Fighter(
        name='冠軍',
        chara_img='enemy3',
        element=random.randint(1, 7),
        hp=char.max_hp, max_hp=char.max_hp,
        mp=char.max_mp, max_mp=char.max_mp,
        str_stat=char.str_stat, vit=char.vit,
        int_stat=char.int_stat, fai=char.fai,
        dex=char.dex, agi=char.agi,
        technique='90,92,95,20,20',
    )

    town = get_town_for_character(char.position)
    town_ele = town.element if town else 0
    result = run_battle(player, enemy, town_ele, max_turns=50)

    post_msg = ''
    get_ex = 0
    get_gold = 0
    get_abp = 0

    epoint = int((enemy.max_hp + enemy.max_mp) / 3) + enemy.str_stat + enemy.vit + \
             enemy.int_stat + enemy.fai + enemy.dex + enemy.agi

    if result.win:
        char.win_streak = (char.win_streak or 0) + 1
        get_ex = epoint + random.randint(0, int(epoint / 3))
        get_ex = max(10, min(get_ex, 50)) + random.randint(0, 9)
        get_gold = 20000

        if char.exp < 9900:
            char.exp += get_ex
        char.total_exp = (char.total_exp or 0) + get_ex
        char.gold += get_gold

        post_msg += lvup(char, player)
    elif result.lose:
        char.gold = max(0, char.gold // 2)

    char.last_action = now
    char.hp = max(0, player.hp)
    char.mp = max(0, player.mp)
    db.session.commit()

    return render_template('battle/result.html',
                           char=char, result=result, player=player, enemy=enemy,
                           location='練武場', battle_mode=0,
                           town=town, get_ex=get_ex, get_gold=get_gold,
                           get_abp=get_abp, post_msg=post_msg)


# ===== 訓練 (PvP 同國) =====

def kunren_select(char):
    """訓練對手選擇 — 對應 battle/kunren.pl"""
    country = get_country(char.country_id)
    if not country or char.country_id == 0:
        flash('無國籍者無法使用。')
        return redirect(url_for('main.top'))

    players = Character.query.filter(
        Character.id != char.id,
        Character.country_id == char.country_id,
    ).all()
    return render_template('battle/kunren.html', char=char, players=players)


def kunren_battle(char):
    """訓練執行 — 對應 battle/kunren2.pl"""
    enemy_id = request.form.get('player', '')
    if not enemy_id or enemy_id == char.id:
        flash('請選擇對手。')
        return redirect(url_for('battle.dispatch', mode='kunren'))

    now = int(time.time())
    btime = Config.BATTLE_TIME - (now - (char.last_action or 0))
    if btime > 0:
        flash(f'距離下次戰鬥還需等待 {btime} 秒。')
        return redirect(url_for('main.top'))

    enemy_char = db.session.get(Character, enemy_id)
    if not enemy_char:
        flash('找不到對手。')
        return redirect(url_for('main.top'))

    player = make_fighter_from_char(char)
    enemy = make_fighter_from_char(enemy_char)

    town = get_town_for_character(char.position)
    town_ele = town.element if town else 0
    result = run_battle(player, enemy, town_ele, max_turns=30)

    post_msg = ''
    get_ex = 0
    get_gold = 0
    get_abp = 3

    if result.win:
        char.win_streak = (char.win_streak or 0) + 1
        epoint = int(enemy.max_hp + enemy.max_mp + (enemy.str_stat + enemy.vit +
                     enemy.int_stat + enemy.dex + enemy.fai + enemy.agi) / 3)
        get_ex = int(epoint / 15) + 10 + random.randint(0, 9)
        get_ex = max(10, min(get_ex, 50)) + random.randint(0, 9)
        get_gold = (epoint + int(random.random() * epoint / 5)) * 4

        if char.exp < 9900:
            char.exp += get_ex
        char.total_exp = (char.total_exp or 0) + get_ex
        char.gold += get_gold
        char.ability_pts += get_abp

        jp = char.parsed_job_points
        jp[char.job_type] = min(jp[char.job_type] + get_abp, Config.MAX_JOB_LEVEL)
        char.job_points = ','.join(str(p) for p in jp)

        post_msg += lvup(char, player)
    elif result.lose:
        char.gold = max(0, char.gold // 2)

    char.last_action = now
    char.hp = max(0, player.hp)
    char.mp = max(0, player.mp)
    db.session.commit()

    return render_template('battle/result.html',
                           char=char, result=result, player=player, enemy=enemy,
                           location='訓練', battle_mode=0,
                           town=town, get_ex=get_ex, get_gold=get_gold,
                           get_abp=get_abp, post_msg=post_msg)


# ===== 討伐 (PvP 他國) =====

def toubatsu_select(char):
    """討伐對手選擇"""
    country = get_country(char.country_id)
    if not country or char.country_id == 0:
        flash('無國籍者無法使用。')
        return redirect(url_for('main.top'))

    players = Character.query.filter(
        Character.id != char.id,
        Character.country_id == 0,
    ).all()
    return render_template('battle/toubatsu.html', char=char, players=players)


def toubatsu_battle(char):
    """討伐執行 — 對應 battle/toubatsu2.pl"""
    enemy_id = request.form.get('player', '')
    if not enemy_id or enemy_id == char.id:
        flash('請選擇對手。')
        return redirect(url_for('battle.dispatch', mode='toubatsu'))

    now = int(time.time())
    btime = Config.BATTLE_TIME - (now - (char.last_action or 0))
    if btime > 0:
        flash(f'距離下次戰鬥還需等待 {btime} 秒。')
        return redirect(url_for('main.top'))

    # 戰鬥恢復率檢查
    state = db.session.get(BattleState, char.id)
    if state and state.hp_rate < 0.2:
        flash('狀態過於疲勞。')
        return redirect(url_for('main.top'))

    enemy_char = db.session.get(Character, enemy_id)
    if not enemy_char:
        flash('找不到對手。')
        return redirect(url_for('main.top'))

    player = make_fighter_from_char(char)
    enemy = make_fighter_from_char(enemy_char)

    # 討伐時 HP/MP 根據恢復率減少
    if state:
        player.hp = int(char.max_hp * (state.hp_rate or 1.0))
        player.mp = int(char.max_mp * (state.mp_rate or 1.0))

    town = get_town_for_character(char.position)
    town_ele = town.element if town else 0
    result = run_battle(player, enemy, town_ele, max_turns=50)

    post_msg = ''
    get_ex = 50 + random.randint(0, 9)
    get_gold = 0
    get_abp = 2

    if player.ab.get(22):
        get_abp += 1

    if result.win:
        char.win_streak = (char.win_streak or 0) + 1
        if char.exp < 9900:
            char.exp += get_ex
        char.total_exp = (char.total_exp or 0) + get_ex
        char.ability_pts += get_abp

        jp = char.parsed_job_points
        jp[char.job_type] = min(jp[char.job_type] + get_abp, Config.MAX_JOB_LEVEL)
        char.job_points = ','.join(str(p) for p in jp)

        post_msg += lvup(char, player)
        append_game_log(5, f'[討伐]{char.name}戰勝了{enemy_char.name}。')

    if result.lose:
        append_game_log(5, f'[敗北]{char.name}敗給了{enemy_char.name}。')

    # 恢復率更新
    hp_rate = max(0.05, int(player.hp * 100 / char.max_hp) / 100 - 0.1) if char.max_hp > 0 else 0.05
    mp_rate = max(0.05, int(player.mp * 100 / char.max_mp) / 100 - 0.1) if char.max_mp > 0 else 0.05
    if state:
        state.hp_rate = hp_rate
        state.mp_rate = mp_rate
        state.timer = now
    else:
        db.session.add(BattleState(char_id=char.id, hp_rate=hp_rate, mp_rate=mp_rate, timer=now))

    char.last_action = now
    char.hp = max(0, player.hp)
    char.mp = max(0, player.mp)
    db.session.commit()

    return render_template('battle/result.html',
                           char=char, result=result, player=player, enemy=enemy,
                           location='討伐', battle_mode=0,
                           town=town, get_ex=get_ex, get_gold=get_gold,
                           get_abp=get_abp, post_msg=post_msg)


# ===== 魔王戰 =====

def boss_battle(char):
    """魔王戰 — 對應 battle/battle3.pl（固定魔王 + 每回合強化）"""
    now = int(time.time())
    btime = Config.BATTLE_TIME - (now - (char.last_action or 0))
    if btime > 0:
        flash(f'距離下次戰鬥還需等待 {btime} 秒。')
        return redirect(url_for('main.top'))

    if (char.oya or 0) % 50 != 0:
        flash('偵測到非法操作。')
        return redirect(url_for('main.top'))

    player = make_fighter_from_char(char)
    enemy = Fighter(
        name='魔人',
        chara_img=161,
        element=0,
        hp=10000, max_hp=10000,
        mp=3000, max_mp=3000,
        str_stat=50, vit=50,
        int_stat=50, fai=50,
        dex=50, agi=50,
        technique='90,92,95,20,20',
        comment='戰鬥開始了。',
    )

    town = get_town_for_character(char.position)
    town_ele = town.element if town else 0

    # 魔王戰特殊：每回合敵人會強化（run_battle 無法對應，直接用迴圈）
    load_techniques(player)
    load_techniques(enemy)
    para(player, enemy, town_ele)

    from farland.battle_support import matt, eatt, TurnResult, CombatResult
    result = CombatResult()
    max_dmg = 0

    for turn_num in range(1, 31):
        # 每回合敵人強化
        enemy.defense += 30
        enemy.magic_def += 30
        enemy.attack += 30
        enemy.int_stat += 30
        enemy.fai += 30
        enemy.speed += 30

        turn_msgs = ''

        if player.ab.get(15) and not enemy.ab.get(15):
            first = True
        elif enemy.ab.get(15) and not player.ab.get(15):
            first = False
        elif random.randint(0, max(1, player.dex)) > random.randint(0, max(1, enemy.dex)):
            first = True
        else:
            first = False

        win = False
        lose = False

        if first:
            if player.hp > 0:
                msg, win, t_dmg = matt(player, enemy)
                turn_msgs += msg
                max_dmg = max(max_dmg, t_dmg)
            if enemy.hp > 0:
                msg, lose = eatt(player, enemy)
                turn_msgs += msg
        else:
            if enemy.hp > 0:
                msg, lose = eatt(player, enemy)
                turn_msgs += msg
            if player.hp > 0:
                msg, win, t_dmg = matt(player, enemy)
                turn_msgs += msg
                max_dmg = max(max_dmg, t_dmg)

        turn_msgs += f'{enemy.name}更加認真了。'

        tr = TurnResult(
            turn_num=turn_num, messages=turn_msgs,
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

    # 結果計算
    post_msg = ''
    get_abp = 3 + int(max_dmg / 100) + turn_num * 2 + int((enemy.max_hp - max(0, enemy.hp)) / 500)
    if result.win:
        get_abp = 100
    get_ex = int((int((enemy.max_hp + enemy.max_mp) / 3) + 300) / 15 + 10) * 10
    get_ex = max(10, min(get_ex, 50)) + random.randint(0, 9)

    if char.exp < 9900:
        char.exp += get_ex
    char.total_exp = (char.total_exp or 0) + get_ex
    char.ability_pts += get_abp

    jp = char.parsed_job_points
    jp[char.job_type] = min(jp[char.job_type] + get_abp, Config.MAX_JOB_LEVEL)
    char.job_points = ','.join(str(p) for p in jp)

    post_msg += lvup(char, player)

    # 評定
    hval = min(5, get_abp // 20)
    ratings = ['不可', '可', '良', '良', '優', '神級']
    post_msg += f'<br>回合數：{turn_num}<br>最大傷害：{max_dmg}<br>'
    post_msg += f'評定：<b>{ratings[hval]}</b><br>'

    char.oya = random.randint(0, 9999)
    char.last_action = int(time.time())
    char.hp = max(0, player.hp)
    char.mp = max(0, player.mp)
    db.session.commit()

    return render_template('battle/result.html',
                           char=char, result=result, player=player, enemy=enemy,
                           location='魔人戰', battle_mode=0,
                           town=town, get_ex=get_ex, get_gold=0,
                           get_abp=get_abp, post_msg=post_msg)


# ===== 輔助函數 =====

def _try_drop_item(char, player: Fighter, battle_mode: int, rare: bool) -> str:
    """寶箱掉落判定 — 對應 battle.pl 的寶箱獲取部分"""
    rea_up = 0
    if player.ab.get(13):
        rea_up += player.ab_dmg.get(13, 0)
    if battle_mode == 4:
        rea_up += 2000

    roll = random.randint(0, max(1, 10000 - rea_up))
    if battle_mode >= 3 and roll == 7:
        # 隨機稀有裝備掉落
        categories = ['weapon', 'armor', 'accessory', 'item']
        cat = random.choice(categories[:3]) if battle_mode >= 3 else 'item'

        equips = Equipment.query.filter_by(category=cat).all()
        if not equips:
            return ''
        equip = random.choice(equips)

        inv_count = CharacterItem.query.filter_by(char_id=char.id).count()
        if inv_count >= Config.MAX_ITEMS:
            return ''

        item = CharacterItem(
            char_id=char.id, category=cat, name=equip.name,
            price=equip.price, power=equip.power, weight=equip.weight,
            element=equip.element, hit_rate=equip.hit_rate, critical=equip.critical,
            ability=equip.ability, equip_type=equip.equip_type, flag=equip.flag,
        )
        db.session.add(item)
        append_game_log(1, f'[發現]{char.name}在{BATTLE_LOCATIONS.get(battle_mode, "?")}發現了{equip.name}！！')
        return f'<br>發現了<b class="msg-warning">{equip.name}</b>！！<br>'

    return ''
