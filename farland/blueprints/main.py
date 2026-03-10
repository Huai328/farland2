"""
Farland History Ⅱ — 主要 Blueprint
對應 index.cgi, login.cgi, login2.cgi, top.cgi, menu.cgi, ranking.cgi 等
包含：移動系統、侵攻系統、聊天分發、主畫面 POST 分發
"""
import time
import random
from flask import Blueprint, render_template, request, redirect, url_for, flash

from farland.models import (
    db, Character, GameLog, Message, Country, Town, BattleState,
)
from farland.auth import login_user, logout_user, login_required, get_current_character
from farland.common import (
    get_town_for_character, get_country, get_all_countries,
    update_guest_list, format_datetime, append_game_log,
)
from farland.services.character import (
    create_character, validate_new_character,
)
from config import Config
from game_data import (
    ELEMENTS, ELEMENT_BG, ELEMENT_FG, JOBS, JOB_TYPES,
    BATTLE_LOCATIONS, HINT_MESSAGES, SEX,
)

bp = Blueprint('main', __name__)


# ============================================================
# 模式分類（top POST 分發用）
# ============================================================
BATTLE_MODES = {
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
    '11', '12', '13', '14', '15',
    'kunren', 'toubatsu', 'battle', 'battle2', 'battle3',
}

TOWN_MODES = {
    'inn', 'arm', 'pro', 'acc', 'item', 'buy', 'sell',
    'bank', 'banka', 'bankh', 'bankall',
    'arena', 'hinn', 'hinn2',
    'fshop', 'fex', 'fbid', 'fget',
    'rshop', 'rbuy',
    'event', 'event2',
    'battle_entry', 'battle_entry2', 'entry_can',
    's_shop', 's_buy',
}

STATUS_MODES = {
    'status', 'equip', 'equip2',
    'change', 'change2',
    'skill', 'skill2', 'skill3',
    'tec_set', 'tec_set2',
    'sk_set', 'sk_set2',
    'money_send', 'money_send2',
    'item_send', 'item_send2',
    'getabp', 'getabp2',
    'renkin', 'renkin2',
    'data_change', 'data_change2',
    'prof_edit', 'prof_edit2',
    'hero', 'hero2',
    'backup', 'con_renew',
}

COUNTRY_MODES = {
    'build', 'build2',
    'def', 'def_out',
    'town_up', 'town_up2',
    'town_arm', 'town_arm2',
    'ram_up', 'ram_up2',
    'ram_down', 'ram_down2',
    'king_conv', 'king_chat',
    'king_com', 'king_com2',
    'king_change', 'king_change2',
    'money_get', 'town_rec',
    'sirei', 'sirei2',
    'unit', 'unit_entry', 'unit_delete', 'unit_edit', 'unit_edit2',
    'con_change', 'con_change2',
    'con_change3', 'con_change4',
    'con_conv', 'all_conv', 'conv_write',
    'rule', 'all_rule', 'rule_write', 'rule_delete',
    'discharge', 'discharge2',
    'suport_money', 'suport_money2',
}


@bp.route('/')
def index():
    """首頁（對應 index.cgi）"""
    return render_template('index.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """登入頁面（對應 login.cgi + login2.cgi）"""
    if request.method == 'POST':
        char_id = request.form.get('id', '').strip()
        password = request.form.get('pass', '').strip()

        if not char_id or not password:
            flash('請輸入 ID 和密碼。')
            return render_template('login.html')

        char = login_user(char_id, password)
        if char is None:
            flash('密碼錯誤。')
            return render_template('login.html')

        if char.url:
            flash('尚未完成認證。')
            return render_template('login.html')

        return redirect(url_for('main.top'))

    return render_template('login.html')


@bp.route('/logout')
def logout():
    """登出"""
    logout_user()
    return redirect(url_for('main.login'))


@bp.route('/top', methods=['GET', 'POST'])
@login_required
def top(char):
    """主畫面（對應 top.cgi）— GET 顯示主畫面，POST 分發至各子系統"""

    if request.method == 'POST':
        mode = request.form.get('mode', '')

        # 聊天訊息
        if mode == 'chat':
            return _handle_chat(char)

        # 移動 / 侵攻（本 blueprint 內處理）
        if mode == 'move':
            return _move_view(char)
        if mode == 'move2':
            return _move_action(char)
        if mode == 'inv':
            return _inv_view(char)
        if mode == 'inv2':
            return _inv_action(char)

        # 分發到其他 Blueprint
        if mode in BATTLE_MODES or mode.isdigit():
            return redirect(url_for('battle.dispatch', mode=mode), code=307)
        if mode in TOWN_MODES:
            return redirect(url_for('town.dispatch', mode=mode), code=307)
        if mode in STATUS_MODES:
            return redirect(url_for('status.dispatch', mode=mode), code=307)
        if mode in COUNTRY_MODES:
            return redirect(url_for('country.dispatch', mode=mode), code=307)

        # 未知 mode
        if mode:
            flash(f'未知的操作：{mode}')
        return redirect(url_for('main.top'))

    # === GET：顯示主畫面 ===
    town = get_town_for_character(char.position)
    country = get_country(char.country_id)
    countries = get_all_countries()

    # 在線玩家
    con_ele = country.element if country else 0
    guests = update_guest_list(char.name, con_ele, request.remote_addr or '')

    # 剩餘行動時間（不更新 last_action，僅在實際行動時更新）
    now = int(time.time())
    remaining = Config.BATTLE_TIME - (now - char.last_action)
    if remaining < 0:
        remaining = 0

    # 遊戲日誌
    general_logs = (GameLog.query
                    .filter_by(log_type=1)
                    .order_by(GameLog.created_at.desc())
                    .limit(10).all())
    battle_logs = (GameLog.query
                   .filter_by(log_type=5)
                   .order_by(GameLog.created_at.desc())
                   .limit(10).all())

    # 訊息
    all_messages = (Message.query
                    .filter_by(scope='all')
                    .order_by(Message.created_at.desc())
                    .limit(Config.MSG_ALL).all())
    country_messages = []
    if country:
        country_messages = (Message.query
                            .filter_by(scope=f'country_{country.id}')
                            .order_by(Message.created_at.desc())
                            .limit(Config.MSG_COUNTRY).all())
    personal_messages = (Message.query
                         .filter(
                             (Message.scope == f'player_{char.id}') |
                             (Message.sender_id == char.id)
                         )
                         .order_by(Message.created_at.desc())
                         .limit(Config.MSG_PERSONAL).all())
    unit_messages = []
    if char.unit_id:
        unit_messages = (Message.query
                         .filter_by(scope=f'unit_{char.unit_id}')
                         .order_by(Message.created_at.desc())
                         .limit(Config.MSG_UNIT).all())

    # 隨機提示
    hint = random.choice(HINT_MESSAGES)

    # 隱藏迷宮判定（$moya 值決定可用的特殊戰場）
    hidden_dungeons = []
    oya = char.oya or 0
    if oya == 77777:
        hidden_dungeons.append((14, BATTLE_LOCATIONS[14]))
    if oya == 777:
        hidden_dungeons.append((10, BATTLE_LOCATIONS[10]))
    if oya in (775, 776):
        hidden_dungeons.append((15, BATTLE_LOCATIONS[15]))
    if oya % 5000 == 773:
        hidden_dungeons.append((13, BATTLE_LOCATIONS[13]))
    if oya == 55555:
        hidden_dungeons.append((12, BATTLE_LOCATIONS[12]))
    if oya % 2500 == 17:
        hidden_dungeons.append((11, BATTLE_LOCATIONS[11]))
    if oya % 1000 == 9:
        hidden_dungeons.append((9, BATTLE_LOCATIONS[9]))
    if oya % 300 == 8:
        hidden_dungeons.append((8, BATTLE_LOCATIONS[8]))
    if oya % 80 == 7:
        hidden_dungeons.append((7, BATTLE_LOCATIONS[7]))
    if oya % 40 == 0:
        hidden_dungeons.append((6, BATTLE_LOCATIONS[6]))
    if char.exp % 11 == 0 and char.exp < 9900:
        hidden_dungeons.append((5, BATTLE_LOCATIONS[5]))

    # 國家名稱映射
    country_map = {c.id: c for c in countries}

    # 城鎮所屬國家
    town_country = None
    if town and town.country_id:
        town_country = country_map.get(town.country_id)

    return render_template(
        'top.html',
        char=char,
        town=town,
        country=country,
        town_country=town_country,
        countries=countries,
        country_map=country_map,
        guests=guests,
        remaining_time=remaining,
        general_logs=general_logs,
        battle_logs=battle_logs,
        all_messages=all_messages,
        country_messages=country_messages,
        personal_messages=personal_messages,
        unit_messages=unit_messages,
        hint=hint,
        hidden_dungeons=hidden_dungeons,
        BATTLE_LOCATIONS=BATTLE_LOCATIONS,
        SEX=SEX,
    )


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """角色註冊（對應 entry.cgi + chara_make.cgi）"""
    if Config.CHARA_ENTRY_CLOSED:
        flash('目前無法註冊新角色。')
        return redirect(url_for('main.index'))

    countries = get_all_countries()

    if request.method == 'POST':
        char_id = request.form.get('id', '').strip()
        password = request.form.get('pass', '').strip()
        name = request.form.get('name', '').strip()
        sex = int(request.form.get('sex', 0))
        element = int(request.form.get('ele', 0))
        chara_img = int(request.form.get('img', 0))
        country_id = int(request.form.get('con_id', 0))
        email = request.form.get('mail', '').strip()
        email_confirm = request.form.get('mailconfirm', '').strip()

        if email != email_confirm:
            flash('電子郵件輸入不正確。')
            return render_template('register.html', countries=countries)

        error = validate_new_character(char_id, password, name, email)
        if error:
            flash(error)
            return render_template('register.html', countries=countries)

        char = create_character(
            char_id=char_id,
            password=password,
            name=name,
            sex=sex,
            element=element,
            chara_img=chara_img,
            country_id=country_id,
            email=email,
        )

        # 記錄日誌
        country = get_country(country_id)
        con_name = country.name if country else '無所屬'
        from farland.common import append_battle_history
        append_game_log(1, f'[註冊]{name}已註冊至{con_name}國。')
        append_battle_history(char.id, f'成為{con_name}國的國民。', con_name)

        login_user(char_id, password)
        flash(f'角色註冊完成。ID: {char_id}')
        return redirect(url_for('main.top'))

    return render_template('register.html', countries=countries)


# ============================================================
# 聊天訊息處理
# ============================================================

def _handle_chat(char):
    """處理聊天訊息（top 頁面 chat 表單）"""
    mes = request.form.get('mes', '').strip()
    mes_sel = request.form.get('mes_sel', '1')
    aite = request.form.get('aite', '').strip()

    if not mes:
        return redirect(url_for('main.top'))

    # clear 指令：清除個人訊息
    if mes.lower() == 'clear':
        Message.query.filter(
            (Message.scope == f'player_{char.id}') |
            (Message.sender_id == char.id)
        ).delete()
        db.session.commit()
        flash('訊息已清除。')
        return redirect(url_for('main.top'))

    now = int(time.time())

    if mes_sel == '1':
        # 致全體
        scope = 'all'
    elif mes_sel == '2':
        # 致國民
        country = get_country(char.country_id)
        if not country:
            flash('無所屬國家。')
            return redirect(url_for('main.top'))
        scope = f'country_{country.id}'
    elif mes_sel == '4':
        # 致部隊
        if not char.unit_id:
            flash('未加入部隊。')
            return redirect(url_for('main.top'))
        scope = f'unit_{char.unit_id}'
    elif mes_sel == '3':
        # 私訊
        if not aite:
            flash('請輸入收件人名稱。')
            return redirect(url_for('main.top'))
        target = Character.query.filter_by(name=aite).first()
        if not target:
            flash('找不到該玩家。')
            return redirect(url_for('main.top'))
        scope = f'player_{target.id}'
    else:
        return redirect(url_for('main.top'))

    msg = Message(
        scope=scope,
        sender_id=char.id,
        sender_name=char.name,
        sender_img=char.chara_img,
        body=mes,
        created_at=now,
    )
    db.session.add(msg)
    db.session.commit()
    return redirect(url_for('main.top'))


# ============================================================
# 移動系統（對應 etc/move.pl, etc/move2.pl）
# ============================================================

def _get_adjacent_towns(town, all_towns, has_teleport=False):
    """取得可移動的城鎮列表（鄰接或傳送）"""
    result = []
    for t in all_towns:
        if t.id == town.id:
            continue
        if has_teleport:
            result.append(t)
        elif abs(t.x - town.x) <= 1 and abs(t.y - town.y) <= 1:
            result.append(t)
    return result


def _build_world_map(all_towns, countries, current_pos):
    """建構 6x6 世界地圖資料"""
    country_map = {c.id: c for c in countries}
    grid = [[None for _ in range(6)] for _ in range(6)]
    for t in all_towns:
        if 0 <= t.x < 6 and 0 <= t.y < 6:
            con = country_map.get(t.country_id)
            grid[t.y][t.x] = {
                'town': t,
                'country': con,
                'is_current': (t.id == current_pos),
                'bg_color': ELEMENT_BG.get(con.element, '#555555') if con else '#555555',
                'fg_color': ELEMENT_FG.get(con.element, '#f1f1f1') if con else '#f1f1f1',
                'country_name': con.name if con else '無所屬',
            }
    return grid


def _move_view(char):
    """移動畫面（對應 etc/move.pl）"""
    town = get_town_for_character(char.position)
    if not town:
        flash('找不到當前城鎮。')
        return redirect(url_for('main.top'))

    # 檢查傳送技能（技能 ID 55）
    skills = (char.skills or '').split(',')
    has_teleport = '55' in skills

    all_towns = Town.query.all()
    countries = get_all_countries()

    adjacent = _get_adjacent_towns(town, all_towns, has_teleport)
    world_map = _build_world_map(all_towns, countries, char.position)

    return render_template(
        'etc/move.html',
        char=char,
        town=town,
        adjacent_towns=adjacent,
        world_map=world_map,
    )


def _move_action(char):
    """移動執行（對應 etc/move2.pl）"""
    tid = request.form.get('tid', '')
    if not tid:
        flash('未選擇移動目的地。')
        return redirect(url_for('main.top'))

    try:
        tid = int(tid)
    except ValueError:
        flash('無效的目的地。')
        return redirect(url_for('main.top'))

    # 冷卻時間檢查
    now = int(time.time())
    btime = Config.BATTLE_TIME - (now - char.last_action)
    if btime > 0:
        flash(f'距下次行動還需等待 {btime} 秒。')
        return redirect(url_for('main.top'))

    town = get_town_for_character(char.position)
    target = db.session.get(Town, tid)
    if not target:
        flash('目的地不存在。')
        return redirect(url_for('main.top'))

    # 鄰接檢查（除非有傳送技能）
    skills = (char.skills or '').split(',')
    has_teleport = '55' in skills
    if not has_teleport:
        if abs(target.x - town.x) > 1 or abs(target.y - town.y) > 1:
            flash('無法到達該地點。')
            return redirect(url_for('main.top'))

    # 執行移動
    char.position = tid
    char.last_action = now
    db.session.commit()

    flash(f'已移動至{target.name}。')
    return render_template('etc/move_result.html', char=char, target=target)


# ============================================================
# 侵攻系統（對應 etc/inv.pl, etc/inv2.pl）
# ============================================================

def _inv_view(char):
    """侵攻畫面（對應 etc/inv.pl）"""
    town = get_town_for_character(char.position)
    if not town:
        flash('找不到當前城鎮。')
        return redirect(url_for('main.top'))

    all_towns = Town.query.all()
    countries = get_all_countries()

    # 只能攻擊鄰接的敵方城鎮
    adjacent_enemies = []
    for t in all_towns:
        if t.id == town.id:
            continue
        if abs(t.x - town.x) > 1 or abs(t.y - town.y) > 1:
            continue
        # 不能攻擊自己國家或 town id 0
        if t.country_id == char.country_id and char.country_id != 0:
            continue
        if t.id == 0:
            continue
        adjacent_enemies.append(t)

    world_map = _build_world_map(all_towns, countries, char.position)

    return render_template(
        'etc/inv.html',
        char=char,
        town=town,
        adjacent_enemies=adjacent_enemies,
        world_map=world_map,
    )


def _inv_action(char):
    """侵攻執行（對應 etc/inv2.pl — 攻城戰）"""
    tid = request.form.get('tid', '')
    if not tid:
        flash('未選擇攻擊目標。')
        return redirect(url_for('main.top'))

    try:
        tid = int(tid)
    except ValueError:
        flash('無效的目標。')
        return redirect(url_for('main.top'))

    now = int(time.time())
    country = get_country(char.country_id)

    # 冷卻檢查
    btime = Config.BATTLE_TIME - (now - char.last_action)
    if btime > 0:
        flash(f'距下次戰鬥還需等待 {btime} 秒。')
        return redirect(url_for('main.top'))

    # HP 率檢查
    battle_state = db.session.get(BattleState, char.id)
    hp_rate = battle_state.hp_rate if battle_state else 1.0
    if hp_rate < 0.25:
        flash('體力不足，無法進行侵攻。')
        return redirect(url_for('main.top'))

    # 國政冷卻（有國籍 → KINGDOM_TIME，無國籍 → MAP_TIME）
    if char.country_id != 0:
        ktime = Config.KINGDOM_TIME - (now - char.created_at)
        if ktime > 0:
            flash(f'距下次侵攻還需等待 {ktime} 秒。')
            return redirect(url_for('main.top'))
    else:
        mtime = Config.MAP_TIME - (now - char.created_at)
        if mtime > 0:
            flash(f'距下次侵攻還需等待 {mtime} 秒。')
            return redirect(url_for('main.top'))
        # 無國籍侵攻需要 50000 Gold 預金
        if char.bank < 50000:
            flash(f'無所屬的侵攻需要銀行存款 50000 Gold。')
            return redirect(url_for('main.top'))
        char.bank -= 50000

    town = get_town_for_character(char.position)
    target = db.session.get(Town, tid)
    if not target:
        flash('目標城鎮不存在。')
        return redirect(url_for('main.top'))

    # 鄰接檢查
    if abs(target.x - town.x) > 1 or abs(target.y - town.y) > 1:
        flash('無法到達該地點。')
        return redirect(url_for('main.top'))

    # 不能攻擊自己國家
    if target.country_id == char.country_id and char.country_id != 0:
        flash('不能攻擊自己的城鎮。')
        return redirect(url_for('main.top'))

    # 不能攻擊 town 0
    if target.id == 0 or target.country_id == char.country_id:
        flash('無法攻擊此城鎮。')
        return redirect(url_for('main.top'))

    # 國家人數限制檢查（5 人以下不能侵攻）
    if char.country_id != 0 and target.country_id != 0:
        attacker_count = Character.query.filter_by(country_id=char.country_id).count()
        defender_count = Character.query.filter_by(country_id=target.country_id).count()
        if attacker_count < 5 or defender_count < 5:
            flash('5 人以下的國家無法進行侵攻。')
            return redirect(url_for('main.top'))

    # 無所屬城鎮限制
    all_towns = Town.query.all()
    unowned_count = sum(1 for t in all_towns if t.country_id == 0)
    target_country_towns = sum(1 for t in all_towns if t.country_id == target.country_id)

    if char.country_id == 0 and target_country_towns <= 1:
        flash('無所屬國民無法攻擊只剩一座城的國家。')
        return redirect(url_for('main.top'))
    if char.country_id == 0 and unowned_count >= 2:
        flash('已有其他無所屬城鎮存在，無法再攻擊。')
        return redirect(url_for('main.top'))

    # 執行攻城戰（簡化版 — 對城塞戰鬥）
    target_country = get_country(target.country_id)
    target_con_name = target_country.name if target_country else '無所屬'
    con_name = country.name if country else '無所屬'

    append_game_log(
        5,
        f'<span style="color:red">[侵攻]</span>'
        f'<span style="color:red">{con_name}國</span>的{char.name}'
        f'向<span style="color:blue">{target_con_name}國：{target.name}</span>發動攻擊！'
    )

    # 戰鬥計算 — 玩家 vs 城塞
    fortress_hp = target.town_hp or 1000
    fortress_str = target.town_str or 300
    fortress_def = target.town_def or 300
    fortress_dex = target.town_dex or 300

    player_hp = int(char.max_hp * hp_rate)
    player_mp = int(char.max_mp * (battle_state.mp_rate if battle_state else 1.0))

    battle_log = []
    win = False
    lose = False

    for turn in range(1, 51):
        if player_hp <= 0 or fortress_hp <= 0:
            break

        # 先攻判定
        player_first = random.randint(0, char.dex) > random.randint(0, fortress_dex)

        if player_first:
            # 玩家攻擊城塞
            dmg = max(1, char.str_stat - fortress_def // 3 + random.randint(0, 30))
            fortress_hp -= dmg
            msg = f'{char.name}對城塞造成 {dmg} 傷害！'
            battle_log.append({'turn': turn, 'msg': msg, 'p_hp': player_hp, 'f_hp': max(0, fortress_hp)})

            if fortress_hp <= 0:
                win = True
                break

            # 城塞反擊
            dmg2 = max(1, fortress_str // 3 - char.vit // 4 + random.randint(0, 20))
            player_hp -= dmg2
            msg2 = f'城塞反擊！{char.name}受到 {dmg2} 傷害！'
            battle_log.append({'turn': turn, 'msg': msg2, 'p_hp': max(0, player_hp), 'f_hp': max(0, fortress_hp)})
        else:
            # 城塞先攻
            dmg2 = max(1, fortress_str // 3 - char.vit // 4 + random.randint(0, 20))
            player_hp -= dmg2
            msg2 = f'城塞攻擊！{char.name}受到 {dmg2} 傷害！'
            battle_log.append({'turn': turn, 'msg': msg2, 'p_hp': max(0, player_hp), 'f_hp': fortress_hp})

            if player_hp <= 0:
                lose = True
                break

            # 玩家反擊
            dmg = max(1, char.str_stat - fortress_def // 3 + random.randint(0, 30))
            fortress_hp -= dmg
            msg = f'{char.name}對城塞造成 {dmg} 傷害！'
            battle_log.append({'turn': turn, 'msg': msg, 'p_hp': player_hp, 'f_hp': max(0, fortress_hp)})

        if fortress_hp <= 0:
            win = True
        if player_hp <= 0:
            lose = True

    # 戰鬥結果處理
    result_text = '平手'
    get_exp = 0
    get_gold = 0
    get_abp = 0

    if win:
        result_text = '勝利'
        char.win_streak += 1
        get_exp = 50 + random.randint(0, 10)
        if char.exp < 9900:
            char.exp += get_exp
        char.total_exp += get_exp
        get_gold = 500 + random.randint(0, 200)
        char.gold += get_gold
        get_abp = 2
        char.ability_pts += get_abp

        # 城鎮歸屬變更
        append_game_log(
            5,
            f'<span style="color:red">[勝利]</span>'
            f'{char.name}制壓了{target.name}！'
        )
        from farland.common import append_battle_history
        append_battle_history(char.id, f'制壓了{target.name}。', target_con_name)

        char.country_exp += 5

        # 檢查是否滅國
        old_country_id = target.country_id
        target.country_id = char.country_id

        if old_country_id != 0 and target_country:
            remaining = sum(1 for t in all_towns if t.country_id == old_country_id and t.id != target.id)
            if remaining == 0:
                # 滅國！
                append_game_log(1, f'<b>[滅亡]{target_con_name}國已滅亡。</b>')
                append_game_log(2, f'{con_name}國的{char.name}使{target_con_name}國滅亡。')
                char.country_exp += 500

                # 刪除國家
                db.session.delete(target_country)

                # 檢查天下統一
                other_countries = sum(
                    1 for t in all_towns
                    if t.country_id != char.country_id and t.country_id != 0 and t.id != target.id
                )
                if other_countries == 0 and char.country_id != 0:
                    append_game_log(1, f'<b style="color:red">[統一]{con_name}國統一了天下！！</b>')
                    append_game_log(2, f'{con_name}國統一天下。')
                    char.country_exp += 1000

        # 城塞弱化
        target.town_hp = max(0, fortress_hp)
        target.town_str = max(300, (target.town_str or 300) - 15)
        target.town_def = max(300, (target.town_def or 300) - 15)

    elif lose:
        result_text = '敗北'
        append_game_log(5, f'<span style="color:blue">[敗北]</span>{char.name}在侵攻中敗北。')

    # 更新戰鬥狀態
    new_hp_rate = max(0.05, player_hp / char.max_hp - 0.1) if char.max_hp > 0 else 0.05
    new_mp_rate = max(0.05, player_mp / char.max_mp - 0.1) if char.max_mp > 0 else 0.05

    if battle_state:
        battle_state.hp_rate = new_hp_rate
        battle_state.mp_rate = new_mp_rate
        battle_state.timer = now
    else:
        db.session.add(BattleState(
            char_id=char.id, hp_rate=new_hp_rate, mp_rate=new_mp_rate, timer=now,
        ))

    char.last_action = now
    char.created_at = now  # 國政冷卻基準
    char.total_wins += 1
    db.session.commit()

    return render_template(
        'etc/inv_result.html',
        char=char,
        target=target,
        target_con_name=target_con_name,
        battle_log=battle_log,
        result=result_text,
        win=win,
        lose=lose,
        get_exp=get_exp,
        get_gold=get_gold,
        get_abp=get_abp,
    )
