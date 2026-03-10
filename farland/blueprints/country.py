"""
Farland History Ⅱ — Country Blueprint
對應 country.cgi 的 43 個 mode（國家系統）
"""
import time
import math
import random
from flask import Blueprint, render_template, request, redirect, url_for, flash

from farland.models import (
    db, Character, Town, Country, Unit, ForumPost, CountryRule,
    CountryEquipment, DischargLog,
)
from farland.auth import login_required
from farland.common import (
    get_town_for_character, get_country, get_all_countries,
    append_game_log, append_battle_history, format_datetime,
)
from config import Config
from game_data import ELEMENTS, ELEMENT_BG, ELEMENT_FG

bp = Blueprint('country', __name__, url_prefix='/country')


def _get_officials(country):
    """國家家老 ID 列表"""
    if not country or not country.officials:
        return []
    return [s.strip() for s in country.officials.split(',') if s.strip()]


def _is_king_or_official(char, country):
    """國王或家老"""
    if not country:
        return False
    if char.id == country.king_id:
        return True
    return char.id in _get_officials(country)


@bp.route('/', methods=['GET', 'POST'])
@login_required
def dispatch(char):
    """Country 主分發器"""
    mode = request.form.get('mode') or request.args.get('mode', '')
    handlers = {
        # 建國
        'build': build_view,
        'build2': build_action,
        # 城門守衛
        'def': garrison_view,
        'def_out': garrison_leave,
        # 城升級
        'town_up': town_up_view,
        'town_up2': town_up_action,
        # 裝備開發
        'town_arm': town_arm_view,
        'town_arm2': town_arm_action,
        # 城強化
        'ram_up': ram_up_view,
        'ram_up2': ram_up_action,
        # 攻撃
        'ram_down': ram_down_view,
        'ram_down2': ram_down_action,
        # 國王交涉
        'king_conv': king_conv_view,
        'king_chat': king_chat_action,
        # 任命
        'king_com': king_com_view,
        'king_com2': king_com_action,
        # 國王交代
        'king_change': king_change_view,
        'king_change2': king_change_action,
        # 城收入
        'money_get': money_get_action,
        'town_rec': town_rec_action,
        # 命令
        'sirei': sirei_view,
        'sirei2': sirei_action,
        # 部隊
        'unit': unit_view,
        'unit_entry': unit_entry_action,
        'unit_delete': unit_delete_action,
        'unit_edit': unit_edit_view,
        'unit_edit2': unit_edit_action,
        # 所屬變更
        'con_change': con_change_view,
        'con_change2': con_change_action,
        'con_change3': con_change3_view,
        'con_change4': con_change4_action,
        # 討論板
        'con_conv': con_conv_view,
        'all_conv': all_conv_view,
        'conv_write': conv_write_action,
        # 法規
        'rule': rule_view,
        'all_rule': all_rule_view,
        'rule_write': rule_write_action,
        'rule_delete': rule_delete_action,
        # 解雇
        'discharge': discharge_view,
        'discharge2': discharge_action,
        # 國庫援助
        'suport_money': suport_money_view,
        'suport_money2': suport_money_action,
    }
    handler = handlers.get(mode)
    if not handler:
        flash('尚未選擇選單。')
        return redirect(url_for('main.top'))
    return handler(char)


# ============================================================
# 建國
# ============================================================

def build_view(char):
    """建國 表示"""
    if char.country_id != 0:
        flash('已經隸屬於某國。')
        return redirect(url_for('main.top'))
    towns = Town.query.filter_by(country_id=0).all()
    return render_template('country/build.html', char=char, towns=towns)


def build_action(char):
    """建國 実行"""
    con_name = request.form.get('con_name', '').strip()
    town_id = request.form.get('town_id', type=int)

    if not con_name or len(con_name) < 1 or len(con_name) > 10:
        flash('國名請輸入1至10個字。')
        return redirect(url_for('country.dispatch', mode='build'))
    if char.country_id != 0:
        flash('已經隸屬於某國。')
        return redirect(url_for('main.top'))

    cost = 5_000_000
    if char.gold < cost:
        flash(f'建國需要{cost}G。')
        return redirect(url_for('country.dispatch', mode='build'))

    if Country.query.filter_by(name=con_name).first():
        flash('該國名已被使用。')
        return redirect(url_for('country.dispatch', mode='build'))

    town = db.session.get(Town, town_id) if town_id is not None else None
    if not town or town.country_id != 0:
        flash('該城無法使用。')
        return redirect(url_for('country.dispatch', mode='build'))

    char.gold -= cost
    new_country = Country(
        name=con_name,
        element=char.element,
        gold=0,
        king_id=char.id,
        officials='',
        member_count=1,
        message='',
    )
    db.session.add(new_country)
    db.session.flush()

    char.country_id = new_country.id
    char.country_exp = 100
    town.country_id = new_country.id

    db.session.commit()
    append_game_log(6, f'[建國]{char.name}建立了{con_name}國。')
    flash(f'已建立{con_name}國！')
    return redirect(url_for('main.top'))


# ============================================================
# 城門守衛
# ============================================================

def garrison_view(char):
    """城門守衛 参加"""
    town = get_town_for_character(char.position)
    country = get_country(char.country_id)
    if not country or not town or town.country_id != char.country_id:
        flash('僅能在本國的城內執行。')
        return redirect(url_for('main.top'))

    # 守衛參加 → 城的防禦力提升
    bonus = char.level + char.vit // 5
    town.town_def += bonus
    if town.town_def > 999:
        town.town_def = 999
    char.country_exp += 1
    db.session.commit()

    append_game_log(6, f'[守衛]{char.name}擔任了{town.name}城的守衛。（防禦+{bonus}）')
    flash(f'已擔任{town.name}城的守衛。（防禦+{bonus}）')
    return redirect(url_for('main.top'))


def garrison_leave(char):
    """城門守衛 離脱"""
    town = get_town_for_character(char.position)
    if not town:
        flash('找不到城。')
        return redirect(url_for('main.top'))
    flash('已離開守衛崗位。')
    return redirect(url_for('main.top'))


# ============================================================
# 城升級
# ============================================================

def town_up_view(char):
    """城的發展 顯示"""
    town = get_town_for_character(char.position)
    country = get_country(char.country_id)
    if not country or not town or town.country_id != char.country_id:
        flash('僅能在本國的城內執行。')
        return redirect(url_for('main.top'))
    return render_template('country/town_up.html', char=char, town=town, country=country)


def town_up_action(char):
    """城的發展 執行"""
    town = get_town_for_character(char.position)
    country = get_country(char.country_id)
    if not country or not town or town.country_id != char.country_id:
        flash('僅能在本國的城內執行。')
        return redirect(url_for('main.top'))
    if char.country_exp < 100:
        flash('國貢獻度需要100。')
        return redirect(url_for('main.top'))

    target = request.form.get('target', '')
    amount = request.form.get('amount', type=int, default=0)
    if amount <= 0:
        flash('請輸入投資額。')
        return redirect(url_for('country.dispatch', mode='town_up'))

    gold_needed = amount * 10000
    if char.gold < gold_needed:
        flash('持有金不足。')
        return redirect(url_for('country.dispatch', mode='town_up'))

    char.gold -= gold_needed
    char.country_exp += amount

    dev_map = {
        'arm': 'weapon_dev',
        'pro': 'armor_dev',
        'acc': 'acc_dev',
        'item': 'item_dev',
        'trade': 'trade',
    }
    attr = dev_map.get(target)
    if not attr:
        flash('無效的對象。')
        return redirect(url_for('country.dispatch', mode='town_up'))

    current = getattr(town, attr)
    setattr(town, attr, current + amount)
    db.session.commit()

    label_map = {'arm': '武器店', 'pro': '防具店', 'acc': '飾品店', 'item': '產業', 'trade': '交易'}
    append_game_log(6, f'[發展]{char.name}將{town.name}城的{label_map[target]}發展了{amount}。')
    flash(f'{town.name}城的{label_map[target]}已發展{amount}。')
    return redirect(url_for('main.top'))


# ============================================================
# 裝備開發
# ============================================================

def town_arm_view(char):
    """武器、防具的開發 顯示"""
    town = get_town_for_character(char.position)
    country = get_country(char.country_id)
    if not country or not town or town.country_id != char.country_id:
        flash('僅能在本國的城內執行。')
        return redirect(url_for('main.top'))
    return render_template('country/town_arm.html', char=char, town=town, country=country)


def town_arm_action(char):
    """武器、防具的開發 執行"""
    town = get_town_for_character(char.position)
    country = get_country(char.country_id)
    if not country or not town or town.country_id != char.country_id:
        flash('僅能在本國的城內執行。')
        return redirect(url_for('main.top'))
    if char.id != country.king_id:
        flash('僅國王可執行。')
        return redirect(url_for('main.top'))
    if char.country_exp < 500:
        flash('國貢獻度需要500。')
        return redirect(url_for('main.top'))

    eqp = request.form.get('eqp', '')
    name = request.form.get('name', '').strip()
    ele = request.form.get('ele', type=int)
    dmg_input = request.form.get('dmg', type=int, default=0)
    wei_input = request.form.get('wei', type=int, default=0)
    atype = request.form.get('atype', '剣')

    if not name:
        flash('未輸入名稱。')
        return redirect(url_for('country.dispatch', mode='town_arm'))
    if dmg_input < 50:
        flash('攻擊值太小。')
        return redirect(url_for('country.dispatch', mode='town_arm'))
    if ele is None:
        flash('未選擇元素。')
        return redirect(url_for('country.dispatch', mode='town_arm'))

    # 同一城最多 3 件
    existing = CountryEquipment.query.filter_by(town_id=town.id).count()
    if existing >= 3:
        flash('同一座城最多只能開發3件。')
        return redirect(url_for('country.dispatch', mode='town_arm'))

    gold_cost = (dmg_input + wei_input) * 10000
    if country.gold < gold_cost:
        flash('國庫資金不足。')
        return redirect(url_for('country.dispatch', mode='town_arm'))

    country.gold -= gold_cost

    # 屬性和國家加成
    up = 0.0
    if ele == town.element:
        up += 0.2
    if ele == country.element:
        up += 0.2
    dmg = int(dmg_input * (1 + up))
    wei = int(wei_input * (1 + up))

    # 計算實際數值（對應原始 Perl 公式）
    if eqp in ('t_arm', 't_pro'):
        arm_dmg = int(math.sqrt(dmg)) + random.randint(0, int(math.sqrt(dmg) * 4)) - random.randint(0, max(1, int(math.sqrt(wei) / 2)))
        arm_dmg = min(arm_dmg, 250)
        arm_dmg += random.randint(0, int(up * 50 + 5))
        arm_dmg = max(arm_dmg, 10 + random.randint(0, 9))

        if arm_dmg < 200:
            arm_wei = arm_dmg - int(math.sqrt(wei) * 2) - random.randint(0, max(1, int(math.sqrt(wei) * 5)))
            arm_wei = max(arm_wei, 5)
            arm_wei -= random.randint(0, int(up * 30 + 5))
            arm_wei = max(arm_wei, max(0, 5 - random.randint(0, 9)))
        else:
            arm_wei = arm_dmg - int(math.sqrt(wei)) - random.randint(0, max(1, int(math.sqrt(wei) * 3)))
            arm_wei = max(arm_wei, 15)
            arm_wei -= random.randint(0, int(up * 30 + 5))
            arm_wei = max(arm_wei, max(0, 15 - random.randint(0, 9)))

        sa = max(1, arm_dmg - arm_wei)
        arm_val = arm_dmg * arm_dmg * 250 + sa * sa * 500
        if arm_dmg < 30:
            arm_val //= 10
        elif arm_dmg < 50:
            arm_val //= 5
        elif arm_dmg < 100:
            arm_val //= 3
        elif arm_dmg < 150:
            arm_val //= 2
        elif arm_dmg < 200:
            arm_val = int(arm_val / 1.5)
        category = 0 if eqp == 't_arm' else 1
        com = '武器' if eqp == 't_arm' else '防具'

        # 武器類型加成
        if eqp == 't_arm':
            if atype == '剣':
                arm_dmg = int(arm_dmg * 1.15)
                arm_wei += 20
            elif atype == '槍':
                arm_dmg = int(arm_dmg * 0.9)
                arm_wei -= 5
            elif atype == '杖':
                arm_dmg = int(arm_dmg * 1.1)
                arm_wei += 12
            elif atype == '弓':
                arm_dmg = int(arm_dmg * 0.8)
                arm_wei -= 10
            elif atype == '短刀':
                arm_dmg = int(arm_dmg * 0.95)
                arm_wei -= 3
    elif eqp == 't_acc':
        arm_dmg = int(math.sqrt(dmg) / 3) + random.randint(0, max(1, int(math.sqrt(dmg)))) - random.randint(0, max(1, int(math.sqrt(wei) / 5)))
        arm_dmg = min(arm_dmg, int(55 + up * 50))
        arm_dmg += random.randint(0, int(up * 20 + 3))

        if arm_dmg < 50:
            arm_wei = arm_dmg - int(math.sqrt(wei)) - random.randint(0, max(1, int(math.sqrt(wei) * 2)))
            arm_wei -= random.randint(0, int(up * 10 + 2))
            arm_wei = max(arm_wei, max(0, -random.randint(0, 9)))
        else:
            arm_wei = arm_dmg - int(math.sqrt(wei) / 2) - random.randint(0, max(1, int(math.sqrt(wei))))
            arm_wei -= random.randint(0, int(up * 10 + 2))
            arm_wei = max(arm_wei, max(0, 5 - random.randint(0, 4)))

        sa = max(1, arm_dmg - arm_wei)
        arm_val = arm_dmg * arm_dmg * 2000 + sa * sa * 4000
        if arm_dmg < 20:
            arm_val //= 10
        elif arm_dmg < 30:
            arm_val //= 5
        elif arm_dmg < 40:
            arm_val //= 3
        elif arm_dmg < 50:
            arm_val //= 2
        elif arm_dmg < 60:
            arm_val = int(arm_val / 1.5)
        category = 2
        atype = '飾品'
        com = '飾品'
    else:
        flash('非法存取。')
        return redirect(url_for('main.top'))

    arm_val = int(arm_val * 0.8) + random.randint(0, int(arm_val * 0.4))
    arm_val = max(arm_val, 1000)
    arm_hit = 75 + random.randint(0, 9)
    arm_cl = 9 + random.randint(0, 1)

    ceq = CountryEquipment(
        category=category,
        name=name,
        price=arm_val,
        power=arm_dmg,
        weight=arm_wei,
        element=ele,
        hit_rate=arm_hit,
        critical=arm_cl,
        equip_type=atype,
        town_id=town.id,
        country_id=country.id,
    )
    db.session.add(ceq)
    db.session.commit()

    append_game_log(6, f'[{com}開發]{country.name}國{char.name}開發了{town.name}城的{com}：{name}({arm_dmg}/{arm_wei})({ELEMENTS.get(ele, "?")})。')
    flash(f'已開發{com}：{name}({arm_dmg}/{arm_wei})({ELEMENTS.get(ele, "?")})。')
    return redirect(url_for('main.top'))


# ============================================================
# 城強化
# ============================================================

def ram_up_view(char):
    """城的強化 顯示"""
    town = get_town_for_character(char.position)
    country = get_country(char.country_id)
    if not country or not town or town.country_id != char.country_id:
        flash('僅能在本國的城內執行。')
        return redirect(url_for('main.top'))
    return render_template('country/ram_up.html', char=char, town=town, country=country)


def ram_up_action(char):
    """城的強化 執行"""
    town = get_town_for_character(char.position)
    country = get_country(char.country_id)
    if not country or not town or town.country_id != char.country_id:
        flash('僅能在本國的城內執行。')
        return redirect(url_for('main.top'))
    if char.country_exp < 100:
        flash('國貢獻度需要100。')
        return redirect(url_for('main.top'))

    gold_input = request.form.get('gold', type=int, default=0)
    if gold_input <= 0 or gold_input > 300:
        flash('請輸入1至300的範圍。')
        return redirect(url_for('country.dispatch', mode='ram_up'))

    # 冷卻檢查
    now = int(time.time())
    cooldown = Config.KINGDOM_TIME - (now - char.created_at)
    if cooldown > 0:
        flash(f'距城的強化還需等待{cooldown}秒。')
        return redirect(url_for('main.top'))

    gold_cost = gold_input * 10000
    if country.gold < gold_cost:
        flash('國庫資金不足。')
        return redirect(url_for('country.dispatch', mode='ram_up'))

    country.gold -= gold_cost
    up = int(gold_input * ((100 + char.int_stat) / 300))

    target = request.form.get('pow', '')
    if target == 't_maxhp':
        up_val = up * 10
        town.town_max_hp = min(town.town_max_hp + up_val, 9999)
        com = '城MAX'
    elif target == 't_hp':
        up_val = up * 100
        town.town_hp = min(town.town_hp + up_val, town.town_max_hp)
        com = '城力'
    elif target == 't_str':
        up_val = up
        town.town_str = min(town.town_str + up_val, 999)
        com = '攻撃力'
    elif target == 't_def':
        up_val = up
        town.town_def = min(town.town_def + up_val, 999)
        com = '防御力'
    else:
        flash('無效的對象。')
        return redirect(url_for('country.dispatch', mode='ram_up'))

    char.created_at = int(time.time())
    db.session.commit()

    append_game_log(6, f'[強化]{char.name}將{town.name}城的{com}強化了{up_val}。')
    flash(f'{town.name}城的{com}已強化{up_val}。')
    return redirect(url_for('main.top'))


# ============================================================
# 攻撃（敵城弱化）
# ============================================================

def ram_down_view(char):
    """攻撃 表示"""
    town = get_town_for_character(char.position)
    country = get_country(char.country_id)
    if not country or not town or town.country_id != char.country_id:
        flash('僅能在本國的城內執行。')
        return redirect(url_for('main.top'))

    # 取得鄰接的敵城
    adjacent = Town.query.filter(
        Town.country_id != char.country_id,
        Town.country_id != 0,
        Town.x.between(town.x - 1, town.x + 1),
        Town.y.between(town.y - 1, town.y + 1),
        Town.id != town.id,
    ).all()

    all_towns = Town.query.all()
    countries = {c.id: c for c in Country.query.all()}

    return render_template('country/ram_down.html', char=char, town=town,
                           country=country, adjacent=adjacent,
                           all_towns=all_towns, countries=countries)


def ram_down_action(char):
    """攻撃 実行"""
    town = get_town_for_character(char.position)
    country = get_country(char.country_id)
    if not country or not town or town.country_id != char.country_id:
        flash('僅能在本國的城內執行。')
        return redirect(url_for('main.top'))
    if char.country_exp < 500:
        flash('國貢獻度需要500。')
        return redirect(url_for('main.top'))

    gold_input = request.form.get('gold', type=int, default=0)
    if gold_input <= 0 or gold_input > 300:
        flash('請輸入1至300的範圍。')
        return redirect(url_for('country.dispatch', mode='ram_down'))

    now = int(time.time())
    cooldown = Config.KINGDOM_TIME - (now - char.created_at)
    if cooldown > 0:
        flash(f'距攻擊還需等待{cooldown}秒。')
        return redirect(url_for('main.top'))

    target_id = request.form.get('tid', type=int)
    if not target_id:
        flash('請選擇攻擊對象。')
        return redirect(url_for('country.dispatch', mode='ram_down'))

    target_town = db.session.get(Town, target_id)
    if not target_town or target_town.country_id == 0 or target_town.country_id == char.country_id:
        flash('不能攻擊同一個國家。')
        return redirect(url_for('country.dispatch', mode='ram_down'))

    gold_cost = gold_input * 10000
    if country.gold < gold_cost:
        flash('國庫資金不足。')
        return redirect(url_for('country.dispatch', mode='ram_down'))

    country.gold -= gold_cost
    up = int(gold_input * ((100 + char.int_stat) / 600))

    target = request.form.get('pow', '')
    if target == 't_str':
        target_town.town_str = max(400, target_town.town_str - up)
        com = '攻撃力'
    elif target == 't_def':
        target_town.town_def = max(400, target_town.town_def - up)
        com = '防御力'
    else:
        flash('無效的對象。')
        return redirect(url_for('country.dispatch', mode='ram_down'))

    char.created_at = int(time.time())
    db.session.commit()

    append_game_log(6, f'[攻擊]{char.name}使{target_town.name}城的{com}降低了{up}。')
    flash(f'{target_town.name}城的{com}已降低{up}。')
    return redirect(url_for('main.top'))


# ============================================================
# 國王交涉
# ============================================================

def king_conv_view(char):
    """国王交涉 表示"""
    country = get_country(char.country_id)
    if not country or char.id != country.king_id:
        flash('僅國王可執行。')
        return redirect(url_for('main.top'))

    countries = Country.query.filter(Country.id != char.country_id).all()
    kings = {}
    for c in countries:
        if c.king_id:
            king = db.session.get(Character, c.king_id)
            if king:
                kings[c.id] = king

    return render_template('country/king_conv.html', char=char,
                           country=country, countries=countries, kings=kings)


def king_chat_action(char):
    """國王訊息發送"""
    country = get_country(char.country_id)
    if not country or char.id != country.king_id:
        flash('僅國王可執行。')
        return redirect(url_for('main.top'))

    target_con = request.form.get('target_con', type=int)
    message = request.form.get('message', '').strip()[:200]
    if not target_con or not message:
        flash('請輸入收件人和訊息。')
        return redirect(url_for('country.dispatch', mode='king_conv'))

    target = db.session.get(Country, target_con)
    if not target or not target.king_id:
        flash('找不到收件人。')
        return redirect(url_for('country.dispatch', mode='king_conv'))

    from farland.models import Message
    now = int(time.time())
    msg = Message(
        scope=f'player_{target.king_id}',
        sender_id=char.id,
        recipient_id=target.king_id,
        sender_name=char.name,
        sender_img=char.chara_img,
        body=f'[國王交涉]{country.name}國王：{message}',
        created_at=now,
    )
    db.session.add(msg)
    db.session.commit()

    flash(f'已向{target.name}國王發送訊息。')
    return redirect(url_for('main.top'))


# ============================================================
# 任命
# ============================================================

def king_com_view(char):
    """家老的任命 顯示"""
    country = get_country(char.country_id)
    if not country or char.id != country.king_id:
        flash('僅國王可執行。')
        return redirect(url_for('main.top'))

    members = Character.query.filter(
        Character.country_id == char.country_id,
        Character.id != char.id,
    ).all()
    officials = _get_officials(country)

    return render_template('country/king_com.html', char=char,
                           country=country, members=members, officials=officials)


def king_com_action(char):
    """家老的任命 執行"""
    country = get_country(char.country_id)
    if not country or char.id != country.king_id:
        flash('僅國王可執行。')
        return redirect(url_for('main.top'))

    slot1 = request.form.get('slot1', '').strip()
    slot2 = request.form.get('slot2', '').strip()
    slot3 = request.form.get('slot3', '').strip()

    officials = [s for s in [slot1, slot2, slot3] if s]
    country.officials = ','.join(officials)
    db.session.commit()

    flash('已任命家老。')
    append_game_log(6, f'[任命]{char.name}任命了{country.name}國的家老。')
    return redirect(url_for('main.top'))


# ============================================================
# 國王交代
# ============================================================

def king_change_view(char):
    """国王交代 表示"""
    country = get_country(char.country_id)
    if not country or char.id != country.king_id:
        flash('僅國王可執行。')
        return redirect(url_for('main.top'))

    members = Character.query.filter(
        Character.country_id == char.country_id,
        Character.id != char.id,
    ).all()
    return render_template('country/king_change.html', char=char,
                           country=country, members=members)


def king_change_action(char):
    """国王交代 実行"""
    country = get_country(char.country_id)
    if not country or char.id != country.king_id:
        flash('僅國王可執行。')
        return redirect(url_for('main.top'))

    new_king_id = request.form.get('new_king', '').strip()
    if not new_king_id:
        flash('請選擇新國王。')
        return redirect(url_for('country.dispatch', mode='king_change'))

    new_king = db.session.get(Character, new_king_id)
    if not new_king or new_king.country_id != char.country_id:
        flash('找不到對象。')
        return redirect(url_for('country.dispatch', mode='king_change'))

    country.king_id = new_king_id
    db.session.commit()

    append_game_log(6, f'[國王交接]{country.name}國的國王從{char.name}交接給{new_king.name}。')
    flash(f'已將國王交接給{new_king.name}。')
    return redirect(url_for('main.top'))


# ============================================================
# 城收入
# ============================================================

def money_get_action(char):
    """城金受取"""
    country = get_country(char.country_id)
    town = get_town_for_character(char.position)
    if not country or not town or town.country_id != char.country_id:
        flash('僅能在本國的城內執行。')
        return redirect(url_for('main.top'))
    if char.id != country.king_id:
        flash('僅國王可執行。')
        return redirect(url_for('main.top'))

    if town.gold <= 0:
        flash('城中沒有資金。')
        return redirect(url_for('main.top'))

    amount = town.gold
    country.gold += amount
    town.gold = 0
    char.country_exp += amount // 10000
    db.session.commit()

    flash(f'已將{amount}G存入國庫。')
    return redirect(url_for('main.top'))


def town_rec_action(char):
    """城資產的領取"""
    country = get_country(char.country_id)
    town = get_town_for_character(char.position)
    if not country or not town or town.country_id != char.country_id:
        flash('僅能在本國的城內執行。')
        return redirect(url_for('main.top'))

    if town.gold <= 10000:
        flash('城資產需要10000G以上才能領取。')
        return redirect(url_for('main.top'))

    amount = town.gold
    side_income = amount // 10
    country.gold += amount
    char.gold += side_income
    char.country_exp += amount // 10000
    town.gold = 0
    db.session.commit()

    flash(f'已領取{amount}G的城資。（副收入: {side_income}G）')
    return redirect(url_for('main.top'))


# ============================================================
# 命令
# ============================================================

def sirei_view(char):
    """命令 表示"""
    country = get_country(char.country_id)
    if not country or not _is_king_or_official(char, country):
        flash('僅國王或家老可執行。')
        return redirect(url_for('main.top'))
    return render_template('country/sirei.html', char=char, country=country)


def sirei_action(char):
    """命令 実行"""
    country = get_country(char.country_id)
    if not country or not _is_king_or_official(char, country):
        flash('僅國王或家老可執行。')
        return redirect(url_for('main.top'))

    message = request.form.get('message', '').strip()[:200]
    if not message:
        flash('請輸入命令內容。')
        return redirect(url_for('country.dispatch', mode='sirei'))

    country.message = message
    db.session.commit()

    append_game_log(6, f'[命令]{country.name}國{char.name}發出了命令。')
    flash('已發出命令。')
    return redirect(url_for('main.top'))


# ============================================================
# 部隊
# ============================================================

def unit_view(char):
    """部隊一覧"""
    country = get_country(char.country_id)
    if not country:
        flash('未隸屬於任何國家。')
        return redirect(url_for('main.top'))

    units = Unit.query.filter_by(country_id=char.country_id).all()
    unit_members = {}
    for u in units:
        members = Character.query.filter_by(unit_id=str(u.id)).all()
        unit_members[u.id] = members

    return render_template('country/unit.html', char=char, country=country,
                           units=units, unit_members=unit_members)


def unit_entry_action(char):
    """部隊参加"""
    unit_id = request.form.get('unit_id', type=int)
    if not unit_id:
        flash('請選擇部隊。')
        return redirect(url_for('country.dispatch', mode='unit'))

    unit = db.session.get(Unit, unit_id)
    if not unit or unit.country_id != char.country_id:
        flash('無法加入該部隊。')
        return redirect(url_for('country.dispatch', mode='unit'))

    if char.unit_id:
        flash('已經隸屬於某部隊。請先退出。')
        return redirect(url_for('country.dispatch', mode='unit'))

    char.unit_id = str(unit_id)
    db.session.commit()

    flash(f'已加入{unit.name}。')
    return redirect(url_for('country.dispatch', mode='unit'))


def unit_delete_action(char):
    """部隊脱退/解散"""
    if not char.unit_id:
        flash('未隸屬於任何部隊。')
        return redirect(url_for('country.dispatch', mode='unit'))

    unit = db.session.get(Unit, int(char.unit_id))
    if not unit:
        char.unit_id = ''
        db.session.commit()
        flash('已退出部隊。')
        return redirect(url_for('country.dispatch', mode='unit'))

    if unit.leader_id == char.id:
        # 隊長 → 解散
        members = Character.query.filter_by(unit_id=str(unit.id)).all()
        for m in members:
            m.unit_id = ''
        db.session.delete(unit)
        db.session.commit()
        flash(f'已解散{unit.name}。')
    else:
        char.unit_id = ''
        db.session.commit()
        flash(f'已退出{unit.name}。')

    return redirect(url_for('country.dispatch', mode='unit'))


def unit_edit_view(char):
    """部隊作成 表示"""
    country = get_country(char.country_id)
    if not country:
        flash('未隸屬於任何國家。')
        return redirect(url_for('main.top'))
    if char.unit_id:
        flash('已經隸屬於某部隊。')
        return redirect(url_for('country.dispatch', mode='unit'))
    return render_template('country/unit_edit.html', char=char, country=country)


def unit_edit_action(char):
    """部隊作成 実行"""
    country = get_country(char.country_id)
    if not country:
        flash('未隸屬於任何國家。')
        return redirect(url_for('main.top'))
    if char.unit_id:
        flash('已經隸屬於某部隊。')
        return redirect(url_for('country.dispatch', mode='unit'))

    unit_name = request.form.get('unit_name', '').strip()
    message = request.form.get('message', '').strip()[:200]
    if not unit_name or len(unit_name) > 16:
        flash('部隊名請輸入1至16個字。')
        return redirect(url_for('country.dispatch', mode='unit_edit'))

    unit = Unit(
        leader_id=char.id,
        name=unit_name,
        message=message,
        country_id=char.country_id,
    )
    db.session.add(unit)
    db.session.flush()

    char.unit_id = str(unit.id)
    db.session.commit()

    flash(f'已建立部隊「{unit_name}」。')
    return redirect(url_for('country.dispatch', mode='unit'))


# ============================================================
# 所屬變更
# ============================================================

def con_change_view(char):
    """加入國家 顯示"""
    if char.country_id != 0:
        flash('已經隸屬於某國。請先退出再加入。')
        return redirect(url_for('main.top'))
    countries = Country.query.all()
    return render_template('country/con_change.html', char=char, countries=countries)


def con_change_action(char):
    """加入國家 執行"""
    if char.country_id != 0:
        flash('已經隸屬於某國。')
        return redirect(url_for('main.top'))

    con_id = request.form.get('con_id', type=int)
    if not con_id:
        flash('請選擇國家。')
        return redirect(url_for('country.dispatch', mode='con_change'))

    # 解雇檢查（100日限制 → 簡化為 24 小時）
    discharged = DischargLog.query.filter_by(
        char_id=char.id, from_country_id=con_id
    ).first()
    if discharged:
        flash('被解雇的國家在一定期間內無法加入。')
        return redirect(url_for('country.dispatch', mode='con_change'))

    country = db.session.get(Country, con_id)
    if not country:
        flash('找不到國家。')
        return redirect(url_for('country.dispatch', mode='con_change'))

    char.country_id = con_id
    char.country_exp = 0
    country.member_count += 1
    db.session.commit()

    append_game_log(6, f'[加入]{char.name}加入了{country.name}國。')
    flash(f'已加入{country.name}國。')
    return redirect(url_for('main.top'))


def con_change3_view(char):
    """脱退 確認"""
    if char.country_id == 0:
        flash('未隸屬於任何國家。')
        return redirect(url_for('main.top'))
    country = get_country(char.country_id)
    return render_template('country/con_change3.html', char=char, country=country)


def con_change4_action(char):
    """脱退 実行"""
    country = get_country(char.country_id)
    if not country:
        flash('未隸屬於任何國家。')
        return redirect(url_for('main.top'))
    if char.id == country.king_id:
        flash('國王不能退出。')
        return redirect(url_for('main.top'))
    if char.unit_id:
        flash('請先退出部隊。')
        return redirect(url_for('main.top'))

    cost = 5_000_000
    if char.gold < cost:
        flash(f'退出需要{cost}G。')
        return redirect(url_for('main.top'))

    old_name = country.name
    char.gold -= cost
    char.country_id = 0
    char.country_exp = 0
    # 狀態重置
    char.hp = 50
    char.max_hp = 50
    char.mp = 30
    char.max_mp = 30
    char.str_stat = 30
    char.vit = 30
    char.int_stat = 30
    char.fai = 30
    char.dex = 30
    char.agi = 30
    char.exp = 0

    country.member_count = max(0, country.member_count - 1)
    db.session.commit()

    append_game_log(6, f'[退出]{char.name}退出了{old_name}國。')
    append_battle_history(char.id, f'退出了{old_name}國，成為無國籍者。', '退國')
    flash(f'已退出{old_name}國。')
    return redirect(url_for('main.top'))


# ============================================================
# 討論板（國家/全體）
# ============================================================

def con_conv_view(char):
    """国内討論 表示"""
    country = get_country(char.country_id)
    if not country:
        flash('未隸屬於任何國家。')
        return redirect(url_for('main.top'))

    forum_type = f'country_{char.country_id}'
    posts = ForumPost.query.filter_by(forum_type=forum_type).order_by(
        ForumPost.thread_id.desc(), ForumPost.id.asc()
    ).limit(30).all()

    # 以討論串分組
    threads = _group_posts_into_threads(posts)

    return render_template('country/conv.html', char=char, country=country,
                           threads=threads, forum_type='con')


def all_conv_view(char):
    """全体討論 表示"""
    posts = ForumPost.query.filter_by(forum_type='all').order_by(
        ForumPost.thread_id.desc(), ForumPost.id.asc()
    ).limit(30).all()

    threads = _group_posts_into_threads(posts)
    country = get_country(char.country_id)

    return render_template('country/conv.html', char=char, country=country,
                           threads=threads, forum_type='all')


def _group_posts_into_threads(posts):
    """以討論串分組"""
    threads = []
    current_thread = None
    for p in posts:
        if p.title:
            if current_thread:
                threads.append(current_thread)
            current_thread = {'op': p, 'replies': []}
        elif current_thread:
            current_thread['replies'].append(p)
    if current_thread:
        threads.append(current_thread)
    return threads


def conv_write_action(char):
    """討論板發文"""
    bbs = request.form.get('bbs', '')
    title = request.form.get('title', '').strip()[:30]
    message = request.form.get('message', '').strip()[:200]
    is_new = request.form.get('type', '') == '1'
    resno = request.form.get('resno', type=int)

    if not message:
        flash('請輸入訊息。')
        return redirect(url_for('main.top'))
    if is_new and not title:
        flash('請輸入標題。')
        return redirect(url_for('main.top'))

    country = get_country(char.country_id)
    if bbs == 'con':
        if not country:
            flash('未隸屬於任何國家。')
            return redirect(url_for('main.top'))
        forum_type = f'country_{char.country_id}'
        redirect_mode = 'con_conv'
    elif bbs == 'all':
        forum_type = 'all'
        redirect_mode = 'all_conv'
    else:
        flash('非法存取。')
        return redirect(url_for('main.top'))

    role = ''
    if country:
        role = f'{country.name}国王' if char.id == country.king_id else f'{country.name}国民'

    now = int(time.time())

    if is_new:
        thread_id = now  # 新討論串以 timestamp 為討論串 ID
    elif resno is not None:
        # 回覆既有討論串 → 尋找 thread_id
        existing = ForumPost.query.filter_by(forum_type=forum_type).order_by(
            ForumPost.id.asc()
        ).offset(resno).first()
        thread_id = existing.thread_id if existing else now
    else:
        thread_id = now

    post = ForumPost(
        forum_type=forum_type,
        thread_id=thread_id,
        char_id=char.id,
        char_name=char.name,
        char_img=char.chara_img,
        country_element=country.element if country else 0,
        title=title if is_new else '',
        body=message,
        role=role,
        created_at=now,
    )
    db.session.add(post)

    # 上限 30 件
    count = ForumPost.query.filter_by(forum_type=forum_type).count()
    if count > 30:
        old = ForumPost.query.filter_by(forum_type=forum_type).order_by(
            ForumPost.id.asc()
        ).limit(count - 30).all()
        for o in old:
            db.session.delete(o)

    db.session.commit()
    flash('已發表文章。')
    return redirect(url_for('country.dispatch', mode=redirect_mode))


# ============================================================
# 法規
# ============================================================

def rule_view(char):
    """国法 表示"""
    country = get_country(char.country_id)
    if not country:
        flash('未隸屬於任何國家。')
        return redirect(url_for('main.top'))

    rules = CountryRule.query.filter_by(scope=str(char.country_id)).order_by(
        CountryRule.id.desc()
    ).all()

    return render_template('country/rule.html', char=char, country=country,
                           rules=rules, rule_type=1)


def all_rule_view(char):
    """全体法 表示"""
    rules = CountryRule.query.filter_by(scope='global').order_by(
        CountryRule.id.desc()
    ).all()
    country = get_country(char.country_id)

    return render_template('country/rule.html', char=char, country=country,
                           rules=rules, rule_type=2)


def rule_write_action(char):
    """法規追加"""
    country = get_country(char.country_id)
    rule_type = request.form.get('type', type=int, default=1)
    message = request.form.get('message', '').strip()[:100]

    if not message:
        flash('請輸入內容。')
        return redirect(url_for('main.top'))

    if rule_type == 1:
        if not country or not _is_king_or_official(char, country):
            flash('僅國王或家老可執行。')
            return redirect(url_for('main.top'))
        scope = str(char.country_id)
        redirect_mode = 'rule'
    elif rule_type == 2:
        if not country or char.id != country.king_id:
            flash('僅國王可執行。')
            return redirect(url_for('main.top'))
        scope = 'global'
        redirect_mode = 'all_rule'
    else:
        flash('非法存取。')
        return redirect(url_for('main.top'))

    count = CountryRule.query.filter_by(scope=scope).count()
    if count >= 20:
        flash('已達到最大數量。')
        return redirect(url_for('country.dispatch', mode=redirect_mode))

    role = f'{country.name}国王' if char.id == country.king_id else ''
    now = int(time.time())

    rule = CountryRule(
        scope=scope,
        char_id=char.id,
        char_name=char.name,
        char_img=char.chara_img,
        body=message,
        role=role,
        created_at=now,
    )
    db.session.add(rule)
    db.session.commit()

    flash('已新增規則。')
    return redirect(url_for('country.dispatch', mode=redirect_mode))


def rule_delete_action(char):
    """法規削除"""
    country = get_country(char.country_id)
    rule_type = request.form.get('type', type=int, default=1)
    rule_no = request.form.get('no', type=int)

    if rule_no is None:
        flash('請選擇刪除對象。')
        return redirect(url_for('main.top'))

    if rule_type == 1:
        if not country or not _is_king_or_official(char, country):
            flash('僅國王或家老可刪除。')
            return redirect(url_for('main.top'))
        scope = str(char.country_id)
        redirect_mode = 'rule'
    elif rule_type == 2:
        if not country or char.id != country.king_id:
            flash('僅國王可刪除。')
            return redirect(url_for('main.top'))
        scope = 'global'
        redirect_mode = 'all_rule'
    else:
        flash('非法存取。')
        return redirect(url_for('main.top'))

    rule = db.session.get(CountryRule, rule_no)
    if rule and rule.scope == scope:
        db.session.delete(rule)
        db.session.commit()
        flash('已刪除規則。')
    else:
        flash('找不到對象。')

    return redirect(url_for('country.dispatch', mode=redirect_mode))


# ============================================================
# 解雇
# ============================================================

def discharge_view(char):
    """解雇 表示"""
    country = get_country(char.country_id)
    if not country or not _is_king_or_official(char, country):
        flash('僅國王或家老可執行。')
        return redirect(url_for('main.top'))

    members = Character.query.filter(
        Character.country_id == char.country_id,
        Character.id != char.id,
        Character.id != country.king_id,
    ).all()

    # 家老不在對象範圍內
    officials = _get_officials(country)
    members = [m for m in members if m.id not in officials]

    return render_template('country/discharge.html', char=char,
                           country=country, members=members)


def discharge_action(char):
    """解雇 実行"""
    country = get_country(char.country_id)
    if not country or not _is_king_or_official(char, country):
        flash('僅國王或家老可執行。')
        return redirect(url_for('main.top'))

    target_id = request.form.get('cand', '').strip()
    if not target_id:
        flash('請選擇對象。')
        return redirect(url_for('country.dispatch', mode='discharge'))

    target = db.session.get(Character, target_id)
    if not target or target.country_id != char.country_id:
        flash('找不到對象。')
        return redirect(url_for('country.dispatch', mode='discharge'))

    officials = _get_officials(country)
    if target_id in officials:
        flash('家老不能解雇。請先解任。')
        return redirect(url_for('country.dispatch', mode='discharge'))

    if char.country_exp < 100:
        flash('國貢獻度需要100。')
        return redirect(url_for('main.top'))

    char.country_exp -= 100
    target.country_exp = 0
    target.country_id = 0

    # 部隊脱退
    if target.unit_id:
        unit = db.session.get(Unit, int(target.unit_id)) if target.unit_id.isdigit() else None
        if unit and unit.leader_id == target.id:
            members = Character.query.filter_by(unit_id=target.unit_id).all()
            for m in members:
                m.unit_id = ''
            db.session.delete(unit)
        target.unit_id = ''

    # 解雇記録
    discharg = DischargLog(
        char_id=target_id,
        from_country_id=char.country_id,
        created_at=format_datetime(),
    )
    db.session.add(discharg)

    country.member_count = max(0, country.member_count - 1)
    db.session.commit()

    append_game_log(6, f'[解雇]{char.name}將{target.name}從{country.name}國解雇。')
    append_battle_history(target_id, f'被{country.name}國解雇。', country.name)
    flash(f'已解雇{target.name}。')
    return redirect(url_for('main.top'))


# ============================================================
# 國庫援助
# ============================================================

def suport_money_view(char):
    """国庫援助 表示"""
    country = get_country(char.country_id)
    if not country:
        flash('未隸屬於任何國家。')
        return redirect(url_for('main.top'))
    return render_template('country/suport_money.html', char=char, country=country)


def suport_money_action(char):
    """国庫援助 実行"""
    country = get_country(char.country_id)
    if not country:
        flash('未隸屬於任何國家。')
        return redirect(url_for('main.top'))

    gold_input = request.form.get('gold', type=int, default=0)
    if gold_input <= 0:
        flash('請輸入援助金額。')
        return redirect(url_for('country.dispatch', mode='suport_money'))

    gold = gold_input * 10000
    if char.gold < gold:
        flash('持有金不足。')
        return redirect(url_for('country.dispatch', mode='suport_money'))

    char.gold -= gold
    country.gold += gold
    char.country_exp += gold_input
    db.session.commit()

    append_game_log(6, f'[援助]{char.name}向{country.name}國援助了{gold}G。')
    flash(f'已向{country.name}國援助{gold}G。')
    return redirect(url_for('main.top'))
