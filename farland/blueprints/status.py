"""
Farland History Ⅱ — Status Blueprint
對應 status.cgi 的 32+ 個 mode（角色管理）
"""
import time
import random
from flask import Blueprint, render_template, request, redirect, url_for, flash

from farland.models import db, Character, CharacterItem, Technique, Ability, Message
from farland.auth import login_required
from farland.common import (
    get_town_for_character, get_country, get_all_countries,
    append_game_log, append_battle_history, format_datetime,
)
from farland.services.equipment import (
    parse_equip, get_inventory, add_to_inventory,
    remove_from_inventory, equip_item, use_consumable,
)
from config import Config
from game_data import JOBS, JOB_TYPES, JOB_STAT_CAP_BONUS, ELEMENTS

bp = Blueprint('status', __name__, url_prefix='/status')


# ===== 狀態查看 =====

@bp.route('/', methods=['GET', 'POST'])
@login_required
def dispatch(char):
    """Status 主分發器"""
    mode = request.form.get('mode') or request.args.get('mode', 'status')
    handlers = {
        'status': status_view,
        'equip': equip_view,
        'equip2': equip_action,
        'change': change_view,
        'change2': change_action,
        'skill': skill_view,
        'skill2': skill_action,
        'skill3': skill_upgrade,
        'tec_set': tec_set_view,
        'tec_set2': tec_set_action,
        'sk_set': sk_set_view,
        'sk_set2': sk_set_action,
        'chat': chat_action,
        'money_send': money_send_view,
        'money_send2': money_send_action,
        'item_send': item_send_view,
        'item_send2': item_send_action,
        'getabp': getabp_view,
        'getabp2': getabp_action,
        'renkin': renkin_view,
        'renkin2': renkin_action,
        'data_change': data_change_view,
        'data_change2': data_change_action,
        'prof_edit': prof_edit_view,
        'prof_write': prof_write_action,
        'name_change': name_change_view,
        'name_change2': name_change_action,
        'type_change': type_change_view,
        'type_change2': type_change_action,
        'hero': hero_view,
        'backup': backup_view,
        'con_renew': con_renew_action,
    }
    handler = handlers.get(mode)
    if not handler:
        flash('尚未選擇選單。')
        return redirect(url_for('main.top'))
    return handler(char)


def status_view(char):
    """狀態查看（status.pl）"""
    weapon = parse_equip(char.weapon)
    armor = parse_equip(char.armor)
    accessory = parse_equip(char.accessory)
    country = get_country(char.country_id)

    # 技能
    tec_parts = (char.technique or '0,0,0,50,50').split(',')
    tec_ids = [int(tec_parts[i]) if i < len(tec_parts) else 0 for i in range(3)]
    techniques = []
    for tid in tec_ids:
        tec = db.session.get(Technique, tid)
        techniques.append(tec)

    # 被動技能
    skill_ids = [int(s) for s in (char.skills or '0,0').split(',') if s]
    abilities = []
    for sid in skill_ids[:2]:
        ab = db.session.get(Ability, sid)
        abilities.append(ab)

    return render_template('status/status.html',
                           char=char, weapon=weapon, armor=armor,
                           accessory=accessory, country=country,
                           techniques=techniques, abilities=abilities)


# ===== 裝備管理 =====

def equip_view(char):
    """道具的使用/裝備 顯示（equip.pl）"""
    items = get_inventory(char.id)
    return render_template('status/equip.html', char=char, items=items)


def equip_action(char):
    """道具的使用/裝備 執行（equip2.pl）"""
    item_id = request.form.get('item_id', type=int)
    if not item_id:
        flash('請選擇道具。')
        return redirect(url_for('status.dispatch', mode='equip'))

    item = db.session.get(CharacterItem, item_id)
    if not item or item.char_id != char.id:
        flash('找不到道具。')
        return redirect(url_for('status.dispatch', mode='equip'))

    if item.category in ('weapon', 'armor', 'accessory'):
        error = equip_item(char, item)
        if error:
            flash(error)
        else:
            flash(f'已裝備{item.name}。')
    elif item.category == 'item':
        msg = use_consumable(char, item)
        flash(msg)
    else:
        flash('無法使用的道具。')

    return redirect(url_for('status.dispatch', mode='equip'))


# ===== 轉職 =====

def change_view(char):
    """轉職 顯示（change.pl）"""
    from farland.models import JobClass
    if char.level < 50:
        flash('需要等級50以上。')
        return redirect(url_for('main.top'))

    jobs = JobClass.query.all()
    jp = char.parsed_job_points

    job_type_names = ['武系', '魔系', '神系', '弓系', '體系', '盜系']
    stat_names = ['力', '體', '智', '信', '敏', '速']

    available_jobs = []
    for job in jobs:
        if job.id == char.job_class:
            continue
        
        req_texts = []
        can_change = True

        # JP Requirements (6 values)
        if job.requirements:
            reqs = job.requirements.split(',')
            for i, val in enumerate(reqs):
                if i < len(job_type_names) and val and int(val) > 0:
                    req_texts.append(f"{job_type_names[i]}: {val}")
                    if i >= len(jp) or jp[i] < int(val):
                        can_change = False
        
        # Stat Requirements (mapped to stat_caps in models, 6 values)
        if job.stat_caps:
            caps = job.stat_caps.split(',')
            char_caps = char.parsed_stat_caps
            stat_keys = ['max_str', 'max_vit', 'max_int', 'max_fai', 'max_dex', 'max_agi']
            for i, val in enumerate(caps):
                if i < len(stat_names) and val and int(val) > 0:
                    req_texts.append(f"{stat_names[i]}: {val}")
                    if i >= len(stat_keys) or char_caps.get(stat_keys[i], 0) < int(val):
                        can_change = False
                    
        req_str = ' / '.join(req_texts) if req_texts else '無條件'

        available_jobs.append({
            'id': job.id,
            'name': job.name,
            'type': job.base_type,
            'requirements': req_str,
            'can_change': can_change,
        })

    return render_template('status/change.html', char=char,
                           available_jobs=available_jobs)


def change_action(char):
    """轉職 執行（change2.pl）"""
    from farland.models import JobClass
    new_class = request.form.get('job_id', type=int)
    if new_class is None:
        flash('請選擇職業。')
        return redirect(url_for('status.dispatch', mode='change'))

    if char.level < 50:
        flash('需要等級50以上。')
        return redirect(url_for('main.top'))

    job = db.session.get(JobClass, new_class)
    if not job:
        flash('無效的職業。')
        return redirect(url_for('status.dispatch', mode='change'))

    # 確認轉職條件
    can_change = True
    jp = char.parsed_job_points
    if job.requirements:
        reqs = job.requirements.split(',')
        for i, val in enumerate(reqs):
            if val and int(val) > 0 and (i >= len(jp) or jp[i] < int(val)):
                can_change = False
    
    if job.stat_caps:
        caps = job.stat_caps.split(',')
        char_caps = char.parsed_stat_caps
        stat_keys = ['max_str', 'max_vit', 'max_int', 'max_fai', 'max_dex', 'max_agi']
        for i, val in enumerate(caps):
            if val and int(val) > 0 and i < len(stat_keys) and char_caps.get(stat_keys[i], 0) < int(val):
                can_change = False

    if not can_change:
        flash('轉職條件不足。')
        return redirect(url_for('status.dispatch', mode='change'))

    old_name = JOBS.get(char.job_class, '?')
    char.job_class = new_class
    char.job_type = job.base_type

    # 被動技能值重新計算（加入職業補正）
    from game_data import JOB_LEVEL_BONUS
    bonus = JOB_LEVEL_BONUS.get(job.base_type, [1, 1, 1, 1, 1, 1])
    caps = char.parsed_stat_caps
    
    char.str_stat = min(caps.get('max_str', 200), max(30, int(random.random() * char.str_stat / 1.5) + 10 + char.level * bonus[0]))
    char.vit = min(caps.get('max_vit', 200), max(30, int(random.random() * char.vit / 1.5) + 10 + char.level * bonus[1]))
    char.int_stat = min(caps.get('max_int', 200), max(30, int(random.random() * char.int_stat / 1.5) + 10 + char.level * bonus[2]))
    char.fai = min(caps.get('max_fai', 200), max(30, int(random.random() * char.fai / 1.5) + 10 + char.level * bonus[3]))
    char.dex = min(caps.get('max_dex', 200), max(30, int(random.random() * char.dex / 1.5) + 10 + char.level * bonus[4]))
    char.agi = min(caps.get('max_agi', 200), max(30, int(random.random() * char.agi / 1.5) + 10 + char.level * bonus[5]))

    # 重新計算 HP/MP
    char.max_hp = max(50, char.max_hp - random.randint(0, 50))
    char.max_mp = max(10, char.max_mp - random.randint(0, 20))
    char.hp = min(char.hp, char.max_hp)
    char.mp = min(char.mp, char.max_mp)

    db.session.commit()
    new_name = JOBS.get(new_class, '?')
    flash(f'已從{old_name}轉職為{new_name}。')
    append_game_log(1, f'[轉職]{char.name}轉職為{new_name}。')
    return redirect(url_for('main.top'))


# ===== 技能/被動技能 =====

def skill_view(char):
    """被動技能的取得 顯示（skill.pl）"""
    all_abilities = Ability.query.all()
    # 已擁有的能力
    owned_ids = set(char.learned_abilities)
    return render_template('status/skill.html', char=char,
                           abilities=all_abilities, owned_ids=owned_ids)


def skill_action(char):
    """被動技能的取得 執行（skill2.pl）"""
    ab_id = request.form.get('ability_id', type=int)
    if ab_id is None:
        flash('請選擇被動技能。')
        return redirect(url_for('status.dispatch', mode='skill'))

    ability = db.session.get(Ability, ab_id)
    if not ability:
        flash('無效的被動技能。')
        return redirect(url_for('status.dispatch', mode='skill'))

    if char.level < ability.class_req:
        flash(f'等級不足，需要等級 {ability.class_req}。')
        return redirect(url_for('status.dispatch', mode='skill'))

    if ab_id in char.learned_abilities:
        flash('已經學過這個被動技能了。')
        return redirect(url_for('status.dispatch', mode='skill'))

    if char.ability_pts < ability.cost:
        flash('熟練度不足。')
        return redirect(url_for('status.dispatch', mode='skill'))

    char.ability_pts -= ability.cost
    char.add_learned_ability(ab_id)
    db.session.commit()
    flash(f'已習得{ability.name}！')
    return redirect(url_for('status.dispatch', mode='skill'))


def skill_upgrade(char):
    """被動技能的修行（skill3.pl）— 極限值提升"""
    caps = char.parsed_stat_caps
    rate = 1

    roll = random.randint(0, 99)
    if roll < 1:
        # 1% 覺醒
        rate = 15
        msg = f'{char.name}覺醒了！'
        append_game_log(1, f'[覺醒]{char.name}覺醒了！！')
    elif roll < 6:
        # 5% 急速成長
        rate = 5
        msg = f'{char.name}急速成長了！'
        append_game_log(1, f'[急速成長]{char.name}達成了急速成長！')
    else:
        msg = f'{char.name}的極限值提升了！'
        rate = 1

    # 極限值提升（根據職業系統）
    bonus = JOB_STAT_CAP_BONUS.get(char.job_type, [1, 1, 1, 1, 1, 1])
    cap_keys = ['max_str', 'max_vit', 'max_int', 'max_fai', 'max_dex', 'max_agi']
    new_caps = []
    for i, key in enumerate(cap_keys):
        val = caps[key] + bonus[i] * rate
        val = min(val, Config.STAT_CAP)
        new_caps.append(str(val))

    char.stat_caps = ','.join(new_caps)
    db.session.commit()
    flash(msg)
    return redirect(url_for('main.top'))


# ===== 技設定 =====

def tec_set_view(char):
    """技能變更 顯示（tec_set.pl）"""
    job_str = str(char.job_class)
    all_tecs = Technique.query.filter(db.or_(
        Technique.job_req == 'all',
        Technique.job_req == job_str
    )).all()
    tec_parts = (char.technique or '0,0,0,50,50').split(',')
    current = [int(tec_parts[i]) if i < len(tec_parts) else 0 for i in range(5)]
    return render_template('status/tec_set.html', char=char,
                           techniques=all_tecs, current=current)


def tec_set_action(char):
    """技能變更 執行（tec_set2.pl）"""
    tec1 = request.form.get('tec1', type=int, default=0)
    tec2 = request.form.get('tec2', type=int, default=0)
    tec3 = request.form.get('tec3', type=int, default=0)
    mp_rate = request.form.get('mprate', type=int, default=50)
    hp_rate = request.form.get('hprate', type=int, default=50)

    mp_rate = max(0, min(100, mp_rate))
    hp_rate = max(0, min(100, hp_rate))

    char.technique = f'{tec1},{tec2},{tec3},{mp_rate},{hp_rate}'
    db.session.commit()
    flash('已變更技能。')
    return redirect(url_for('main.top'))


# ===== 被動技能欄位 =====

def sk_set_view(char):
    """被動技能的變更 顯示（sk_set.pl）"""
    learned = char.learned_abilities
    if learned:
        all_abilities = Ability.query.filter(Ability.id.in_(learned)).all()
    else:
        all_abilities = []
    skill_ids = [int(s) for s in (char.skills or '0,0').split(',') if s]
    return render_template('status/sk_set.html', char=char,
                           abilities=all_abilities, current=skill_ids)


def sk_set_action(char):
    """被動技能的變更 執行（sk_set2.pl）"""
    sk1 = request.form.get('sk1', type=int, default=0)
    sk2 = request.form.get('sk2', type=int, default=0)
    char.skills = f'{sk1},{sk2}'
    db.session.commit()
    flash('已變更被動技能。')
    return redirect(url_for('main.top'))


# ===== 聊天 =====

def chat_action(char):
    """聊天發送（chat.pl）"""
    mes = request.form.get('mes', '').strip()
    mes_sel = request.form.get('mes_sel', '1')
    aite = request.form.get('aite', '').strip()

    if not mes:
        flash('請輸入訊息。')
        return redirect(url_for('main.top'))

    if mes == 'clear':
        # 清除指令
        flash('已清除訊息。')
        return redirect(url_for('main.top'))

    now = int(time.time())
    country = get_country(char.country_id)

    if mes_sel == '1':
        scope = 'all'
    elif mes_sel == '2':
        scope = f'country_{char.country_id}'
    elif mes_sel == '4':
        scope = f'unit_{char.unit_id}' if char.unit_id else 'all'
    elif mes_sel == '3':
        # 個人訊息
        if not aite:
            flash('請輸入收件人名稱。')
            return redirect(url_for('main.top'))
        target = Character.query.filter_by(name=aite).first()
        if not target:
            flash('找不到對方。')
            return redirect(url_for('main.top'))
        scope = f'player_{target.id}'
    else:
        scope = 'all'

    msg = Message(
        scope=scope,
        sender_id=char.id,
        recipient_id=aite,
        sender_name=char.name,
        sender_img=char.chara_img,
        body=mes[:150],
        created_at=now,
    )
    db.session.add(msg)

    # 也存一份到送信者的記錄
    if mes_sel == '3' and aite:
        msg2 = Message(
            scope=f'player_{char.id}',
            sender_id=char.id,
            recipient_id=aite,
            sender_name=char.name,
            sender_img=char.chara_img,
            body=mes[:150],
            created_at=now,
        )
        db.session.add(msg2)

    db.session.commit()
    flash('訊息已發送。')
    return redirect(url_for('main.top'))


# ===== 匯款 =====

def money_send_view(char):
    """匯款 顯示（money_send.pl）"""
    players = Character.query.filter(Character.id != char.id).all()
    return render_template('status/money_send.html', char=char, players=players)


def money_send_action(char):
    """匯款 執行（money_send2.pl）"""
    target_id = request.form.get('target_id', '').strip()
    amount = request.form.get('amount', type=int, default=0)

    if not target_id or amount <= 0:
        flash('請指定匯款對象和金額。')
        return redirect(url_for('status.dispatch', mode='money_send'))

    if amount % 10000 != 0:
        flash('金額請以10000為單位指定。')
        return redirect(url_for('status.dispatch', mode='money_send'))

    if char.bank < amount:
        flash('銀行餘額不足。')
        return redirect(url_for('status.dispatch', mode='money_send'))

    target = db.session.get(Character, target_id)
    if not target:
        flash('找不到匯款對象。')
        return redirect(url_for('status.dispatch', mode='money_send'))

    char.bank -= amount
    target.bank += amount

    now = int(time.time())
    for scope, sender, body in [
        (f'player_{target.id}', char, f'收到{char.name}的{amount}G匯款。'),
        (f'player_{char.id}', char, f'已匯款{amount}G給{target.name}。'),
    ]:
        db.session.add(Message(
            scope=scope, sender_id=sender.id, sender_name=sender.name,
            sender_img=sender.chara_img, body=body, created_at=now,
        ))

    db.session.commit()
    flash(f'已匯款{amount}G給{target.name}。')
    return redirect(url_for('main.top'))


# ===== 道具寄送 =====

def item_send_view(char):
    """道具寄送 顯示（item_send.pl）"""
    items = get_inventory(char.id)
    players = Character.query.filter(Character.id != char.id).all()
    return render_template('status/item_send.html', char=char,
                           items=items, players=players)


def item_send_action(char):
    """道具寄送 執行（item_send2.pl）"""
    target_id = request.form.get('target_id', '').strip()
    item_id = request.form.get('item_id', type=int)

    if not target_id or not item_id:
        flash('請選擇收件人和道具。')
        return redirect(url_for('status.dispatch', mode='item_send'))

    cost = 100000
    if char.bank < cost:
        flash(f'銀行中沒有{cost}G的寄送手續費。')
        return redirect(url_for('status.dispatch', mode='item_send'))

    item = db.session.get(CharacterItem, item_id)
    if not item or item.char_id != char.id:
        flash('找不到道具。')
        return redirect(url_for('status.dispatch', mode='item_send'))

    target = db.session.get(Character, target_id)
    if not target:
        flash('找不到收件人。')
        return redirect(url_for('status.dispatch', mode='item_send'))

    char.bank -= cost
    item.char_id = target.id
    db.session.commit()

    flash(f'已將{item.name}寄送給{target.name}。（手續費: {cost}G）')
    return redirect(url_for('main.top'))


# ===== 熟練度獲取 =====

def getabp_view(char):
    """熟練度的獲取 顯示（getabp.pl）"""
    from farland.models import JobClass
    jobs = JobClass.query.all()
    return render_template('status/getabp.html', char=char, jobs=jobs)


def getabp_action(char):
    """熟練度的獲取 執行（getabp2.pl）— 將 JP 的 70% 轉換為 ABP"""
    jp_type = request.form.get('jp_type', type=int)
    if jp_type is None or jp_type < 0 or jp_type > 5:
        flash('無效的選擇。')
        return redirect(url_for('status.dispatch', mode='getabp'))

    jp = char.parsed_job_points
    points = jp[jp_type]
    if points <= 0:
        flash('沒有可轉換的點數。')
        return redirect(url_for('status.dispatch', mode='getabp'))

    gain = int(points * 0.7)
    char.ability_pts += gain

    # 重置 JP
    jp[jp_type] = 0
    char.job_points = ','.join(str(p) for p in jp)
    db.session.commit()

    flash(f'已獲得{gain}點熟練度。')
    return redirect(url_for('main.top'))


# ===== 煉金 =====

def renkin_view(char):
    """道具的製作 顯示（renkin.pl）"""
    items = get_inventory(char.id)
    # TODO: 讀取 data/renkin.cgi 的配方
    return render_template('status/renkin.html', char=char, items=items, recipes=[])


def renkin_action(char):
    """道具的製作 執行（renkin2.pl）"""
    flash('煉金功能準備中。')
    return redirect(url_for('main.top'))


# ===== 圖示變更 =====

def data_change_view(char):
    """圖示的變更 顯示（data_change.pl）"""
    return render_template('status/data_change.html', char=char,
                           max_img=Config.CHARA_IMG_COUNT)


def data_change_action(char):
    """圖示的變更 執行（data_change2.pl）"""
    new_img = request.form.get('img', type=int)
    if new_img is None or new_img < 0 or new_img > Config.CHARA_IMG_COUNT:
        flash('無效的圖片編號。')
        return redirect(url_for('status.dispatch', mode='data_change'))

    cost = 100000
    if char.gold < cost:
        flash(f'變更需要{cost}G。')
        return redirect(url_for('status.dispatch', mode='data_change'))

    char.gold -= cost
    char.chara_img = new_img
    db.session.commit()
    flash('已變更圖示。')
    return redirect(url_for('main.top'))


# ===== 個人檔案 =====

def prof_edit_view(char):
    """個人檔案變更 顯示（prof_edit.pl）"""
    return render_template('status/prof_edit.html', char=char)


def prof_write_action(char):
    """個人檔案變更 執行（prof_write.pl）"""
    profile = request.form.get('profile', '')[:1000]
    char.comment = profile
    db.session.commit()
    flash('已更新個人檔案。')
    return redirect(url_for('main.top'))


# ===== 改名（隱藏事件） =====

def name_change_view(char):
    """聖殿 顯示（name_change.pl）"""
    return render_template('status/name_change.html', char=char)


def name_change_action(char):
    """聖殿 改名 執行（name_change2.pl）"""
    new_name = request.form.get('name', '').strip()
    if not new_name or len(new_name) < 2 or len(new_name) > 8:
        flash('名稱請輸入2至8個字。')
        return redirect(url_for('status.dispatch', mode='name_change'))

    if Character.query.filter_by(name=new_name).first():
        flash('此名稱已被使用。')
        return redirect(url_for('status.dispatch', mode='name_change'))

    old_name = char.name
    char.name = new_name
    db.session.commit()
    append_game_log(1, f'[改名]{old_name}改名為{new_name}。')
    flash(f'已從{old_name}改名為{new_name}。')
    return redirect(url_for('main.top'))


# ===== 職業類型變更 =====

def type_change_view(char):
    """類型變更 顯示"""
    return render_template('status/type_change.html', char=char)


def type_change_action(char):
    """類型變更 執行"""
    new_type = request.form.get('job_type', type=int)
    if new_type is None or new_type not in JOB_TYPES:
        flash('無效的類型。')
        return redirect(url_for('status.dispatch', mode='type_change'))
    char.job_type = new_type
    db.session.commit()
    flash(f'已將類型變更為{JOB_TYPES[new_type]}。')
    return redirect(url_for('main.top'))


# ===== 英雄註冊 =====

def hero_view(char):
    """傳說英雄註冊（hero.pl）"""
    flash('英雄註冊準備中。')
    return redirect(url_for('main.top'))


# ===== 備份 =====

def backup_view(char):
    """備份（backup.pl）"""
    flash(f'角色資料: ID={char.id}, LV={char.level}, '
          f'EXP={char.exp}, Gold={char.gold}')
    return redirect(url_for('main.top'))


# ===== 所屬國籍更新 =====

def con_renew_action(char):
    """所屬國籍的更新（con_renew.pl）"""
    country = get_country(char.country_id)
    if country:
        flash(f'已更新{country.name}國的國籍。')
    else:
        flash('無所屬。')
    return redirect(url_for('main.top'))
