"""
Farland History Ⅱ — Town Blueprint
對應 town.cgi 的 22 個 mode（城鎮系統）
"""
import time
import random
from flask import Blueprint, render_template, request, redirect, url_for, flash

from farland.models import db, Character, CharacterItem, Equipment, Town, BattleState
from farland.auth import login_required
from farland.common import (
    get_town_for_character, get_country, append_game_log,
)
from farland.services.equipment import get_inventory, parse_equip
from config import Config
from game_data import ELEMENTS, ELEMENT_BG, ELEMENT_FG

bp = Blueprint('town', __name__, url_prefix='/town')


@bp.route('/', methods=['GET', 'POST'])
@login_required
def dispatch(char):
    """Town 主分發器"""
    mode = request.form.get('mode') or request.args.get('mode', 'inn')
    handlers = {
        'inn': inn_action,
        'arm': shop_view,
        'pro': shop_view,
        'acc': shop_view,
        'item': shop_view,
        'buy': buy_action,
        'sell': sell_action,
        'bank': bank_view,
        'banka': bank_action,
        'bankh': bank_action,
        'bankall': bank_action,
        'arena': arena_view,
        'hinn': hinn_view,
        'hinn2': hinn_action,
        'fshop': fshop_view,
        'fex': fex_action,
        'fbid': fbid_action,
        'fget': fget_action,
        'rshop': rshop_view,
        'rbuy': rbuy_action,
        'event': event_view,
        'event2': event_action,
        'battle_entry': battle_entry_view,
        'battle_entry2': battle_entry_action,
        'entry_can': entry_can_action,
        's_shop': sshop_view,
        's_buy': sbuy_action,
    }
    handler = handlers.get(mode)
    if not handler:
        flash('尚未選擇選單。')
        return redirect(url_for('main.top'))
    return handler(char)


# ===== 旅館 =====

def inn_action(char):
    """旅館（inn.pl）— HP/MP 全恢復"""
    town = get_town_for_character(char.position)
    total_stats = char.str_stat + char.vit + char.int_stat + char.dex + char.fai + char.agi

    # 住宿費計算
    cost = char.max_hp + char.max_mp + total_stats // 3
    if char.gold + char.bank > 300000:
        cost = max(cost, 100000)

    if char.gold < cost:
        flash(f'住宿費{cost}G不足。（持有金: {char.gold}G）')
        return redirect(url_for('main.top'))

    char.gold -= cost
    char.hp = char.max_hp
    char.mp = char.max_mp

    # 戰鬥恢復率重置
    state = db.session.get(BattleState, char.id)
    if state:
        state.hp_rate = 1.0
        state.mp_rate = 1.0
    else:
        db.session.add(BattleState(
            char_id=char.id, hp_rate=1.0, mp_rate=1.0, timer=0
        ))

    # 城鎮收入
    if town:
        town.gold += cost // 10
    db.session.commit()

    flash(f'在旅館休息了。HP/MP已全恢復。（住宿費: {cost}G）')
    return redirect(url_for('main.top'))


# ===== 商店 =====

def shop_view(char):
    """武器店/防具店/飾品店/道具店 顯示（shop.pl）"""
    mode = request.form.get('mode') or request.args.get('mode', 'arm')
    town = get_town_for_character(char.position)
    country = get_country(char.country_id)

    # 商品分類
    category_map = {'arm': 'weapon', 'pro': 'armor', 'acc': 'accessory', 'item': 'item'}
    category = category_map.get(mode, 'weapon')

    # 商品一覽（篩選：城鎮發展度）
    shop_items = Equipment.query.filter_by(category=category).all()

    # 折扣計算
    discount = 0
    if town and country and town.country_id == country.id:
        discount = min(15, char.level + 1)

    # 庫存（出售用）
    inventory = get_inventory(char.id)

    shop_name = {'arm': '武器店', 'pro': '防具店', 'acc': '飾品店', 'item': '道具店'}

    return render_template('town/shop.html',
                           char=char, town=town,
                           shop_items=shop_items,
                           inventory=inventory,
                           category=category,
                           shop_name=shop_name.get(mode, '店'),
                           discount=discount,
                           mode=mode)


def buy_action(char):
    """購買（buy.pl）"""
    equip_id = request.form.get('equip_id', type=int)
    if not equip_id:
        flash('請選擇商品。')
        return redirect(url_for('main.top'))

    equip = db.session.get(Equipment, equip_id)
    if not equip:
        flash('找不到商品。')
        return redirect(url_for('main.top'))

    # 物品欄上限檢查
    inv_count = CharacterItem.query.filter_by(char_id=char.id).count()
    if inv_count >= Config.MAX_ITEMS:
        flash(f'道具欄已滿。（最多{Config.MAX_ITEMS}個）')
        return redirect(url_for('main.top'))

    # 價格（含折扣）
    town = get_town_for_character(char.position)
    country = get_country(char.country_id)
    discount = 0
    if town and country and town.country_id == country.id:
        discount = min(15, char.level + 1)
    price = equip.price - (equip.price * discount // 100)

    if char.gold < price:
        flash(f'持有金不足。（需要: {price}G）')
        return redirect(url_for('main.top'))

    char.gold -= price

    # 10% 機率隨機強化
    power_bonus = 0
    bonus_msg = ''
    if random.randint(0, 9) == 0:
        power_bonus = equip.power // 10
        bonus_msg = '（隨機強化！）'

    # 加入物品欄
    item = CharacterItem(
        char_id=char.id,
        category=equip.category,
        name=equip.name,
        price=equip.price,
        power=equip.power + power_bonus,
        weight=equip.weight,
        element=equip.element,
        hit_rate=equip.hit_rate,
        critical=equip.critical,
        ability=equip.ability,
        equip_type=equip.equip_type,
        flag=equip.flag,
    )
    db.session.add(item)

    # 城鎮收入
    if town:
        dev = max(1, town.weapon_dev or 1)
        town.gold += price // max(1, (1500 - dev) // 250)

    db.session.commit()
    flash(f'以{price}G購買了{equip.name}。{bonus_msg}')
    return redirect(url_for('main.top'))


def sell_action(char):
    """出售（sell.pl）"""
    item_id = request.form.get('item_id', type=int)
    if not item_id:
        flash('請選擇道具。')
        return redirect(url_for('main.top'))

    item = db.session.get(CharacterItem, item_id)
    if not item or item.char_id != char.id:
        flash('找不到道具。')
        return redirect(url_for('main.top'))

    sell_price = item.price // 2
    char.gold += sell_price
    name = item.name
    db.session.delete(item)
    db.session.commit()

    flash(f'以{sell_price}G出售了{name}。')
    return redirect(url_for('main.top'))


# ===== 銀行 =====

def bank_view(char):
    """銀行 顯示（bank.pl）"""
    return render_template('town/bank.html', char=char)


def bank_action(char):
    """銀行 存提款（bank2.pl）"""
    mode = request.form.get('mode', 'banka')
    amount = request.form.get('amount', type=int, default=0)

    if mode == 'bankall':
        # 全額存入
        char.bank += char.gold
        deposited = char.gold
        char.gold = 0
        db.session.commit()
        flash(f'{deposited}G已存入。（餘額: {char.bank}G）')
    elif mode == 'banka':
        # 存入
        amount = amount * 10000
        if amount <= 0 or char.gold < amount:
            flash('金額不正確。')
            return redirect(url_for('town.dispatch', mode='bank'))
        char.gold -= amount
        char.bank += amount
        db.session.commit()
        flash(f'{amount}G已存入。（餘額: {char.bank}G）')
    elif mode == 'bankh':
        # 提款
        amount = amount * 10000
        if amount <= 0 or char.bank < amount:
            flash('餘額不足。')
            return redirect(url_for('town.dispatch', mode='bank'))
        char.bank -= amount
        char.gold += amount
        db.session.commit()
        flash(f'已提取{amount}G。（餘額: {char.bank}G）')

    return redirect(url_for('main.top'))


# ===== 練武場 =====

def arena_view(char):
    """練武場 顯示（arena.pl）"""
    # TODO: 冠軍資料讀取
    flash('練武場準備中。')
    return redirect(url_for('main.top'))


# ===== 高級旅店 =====

def hinn_view(char):
    """高級旅店 顯示（hinn.pl）"""
    total = (char.max_hp + char.max_mp + char.str_stat + char.vit +
             char.int_stat + char.fai + char.dex + char.agi)
    cost = max(1000000, total * 5000)
    return render_template('town/hinn.html', char=char, cost=cost)


def hinn_action(char):
    """高級旅店 執行（hinn2.pl）— 屬性提升"""
    total = (char.max_hp + char.max_mp + char.str_stat + char.vit +
             char.int_stat + char.fai + char.dex + char.agi)
    cost = max(1000000, total * 5000)

    if char.gold < cost:
        flash(f'費用不足。（需要: {cost}G）')
        return redirect(url_for('main.top'))

    char.gold -= cost
    char.hp = char.max_hp
    char.mp = char.max_mp

    # 屬性提升
    hp_up = random.randint(150, 300)
    mp_up = random.randint(80, 160)
    caps = char.parsed_stat_caps

    max_possible_hp = caps['max_str'] * 5 + caps['max_vit'] * 10 + caps['max_fai'] * 3 - 2000
    max_possible_mp = caps['max_int'] * 5 + caps['max_fai'] * 3 - 800

    char.max_hp = min(char.max_hp + hp_up, max_possible_hp)
    char.max_mp = min(char.max_mp + mp_up, max_possible_mp)
    char.hp = char.max_hp
    char.mp = char.max_mp

    # 城鎮收入
    town = get_town_for_character(char.position)
    if town:
        town.gold += cost // 10
    db.session.commit()

    flash(f'在高級旅店休憩了。maxHP+{hp_up}, maxMP+{mp_up}（費用: {cost}G）')
    return redirect(url_for('main.top'))


# ===== 拍賣 =====

def fshop_view(char):
    """拍賣 顯示（fshop.pl）"""
    # TODO: 拍賣系統
    flash('拍賣準備中。')
    return redirect(url_for('main.top'))


def fex_action(char):
    flash('拍賣出品準備中。')
    return redirect(url_for('main.top'))


def fbid_action(char):
    flash('拍賣出價準備中。')
    return redirect(url_for('main.top'))


def fget_action(char):
    flash('拍賣領取準備中。')
    return redirect(url_for('main.top'))


# ===== 稀有商店 =====

def rshop_view(char):
    """闇市商店 顯示（rshop.pl）"""
    # 隱藏商店（moya%1000 == 1 時出現）
    flash('闇市商店準備中。')
    return redirect(url_for('main.top'))


def rbuy_action(char):
    flash('闇市購買準備中。')
    return redirect(url_for('main.top'))


# ===== 事件 =====

def event_view(char):
    """事件 顯示（event.pl）"""
    oya = char.oya or 0
    event_type = oya % 3

    events = {
        0: '有尋寶的委託。要挑戰嗎？',
        1: '有魔物討伐的委託。要挑戰嗎？',
        2: '有護衛的委託。要接受嗎？',
    }
    return render_template('town/event.html', char=char,
                           event_text=events.get(event_type, ''),
                           event_type=event_type)


def event_action(char):
    """事件 執行（event2.pl）"""
    oya = char.oya or 0
    event_type = oya % 3

    if event_type == 0:
        # 尋寶
        reward = random.randint(1, 100000)
        char.gold += reward
        char.exp += random.randint(5, 30)
        msg = f'發現了寶箱！獲得了{reward}G！'
    elif event_type == 1:
        # 魔物討伐
        if random.randint(0, 1) == 0:
            reward = random.randint(5000, 50000)
            exp = random.randint(10, 50)
            char.gold += reward
            char.exp += exp
            msg = f'討伐了魔物！獲得{reward}G和{exp}EXP！'
        else:
            loss = random.randint(1000, 10000)
            char.gold = max(0, char.gold - loss)
            msg = f'敗給了魔物…失去了{loss}G。'
    else:
        # 護衛
        reward = random.randint(10000, 80000)
        char.gold += reward
        msg = f'護衛任務完成！獲得{reward}G！'

    char.oya = random.randint(0, 99999)
    db.session.commit()
    flash(msg)
    return redirect(url_for('main.top'))


# ===== 武鬥會 =====

def battle_entry_view(char):
    """武鬥會 顯示"""
    flash('武鬥會準備中。')
    return redirect(url_for('main.top'))


def battle_entry_action(char):
    flash('武鬥會準備中。')
    return redirect(url_for('main.top'))


def entry_can_action(char):
    flash('取消報名準備中。')
    return redirect(url_for('main.top'))


# ===== 特殊商店 =====

def sshop_view(char):
    flash('特殊商店準備中。')
    return redirect(url_for('main.top'))


def sbuy_action(char):
    flash('特殊商店準備中。')
    return redirect(url_for('main.top'))
