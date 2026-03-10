"""
Farland History Ⅱ — Admin Blueprint
對應 admin.cgi（管理後台）
"""
import time
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from farland.models import (
    db, Character, CharacterItem, BattleHistory, BattleState,
    Town, Country, GameLog, Message, Unit, ForumPost, CountryRule,
)
from farland.common import append_game_log
from config import Config

bp = Blueprint('admin', __name__, url_prefix='/admin')

# 管理員認證（使用環境變數或設定檔，此處簡化為 session 檢查）
ADMIN_SESSION_KEY = 'admin_authenticated'


def _require_admin():
    """驗證管理員身份"""
    if not session.get(ADMIN_SESSION_KEY):
        return False
    return True


@bp.route('/', methods=['GET', 'POST'])
def index():
    """管理員主頁"""
    if request.method == 'POST' and not session.get(ADMIN_SESSION_KEY):
        admin_id = request.form.get('admin_id', '').strip()
        admin_pass = request.form.get('admin_pass', '').strip()
        # 從設定讀取或使用預設
        expected_id = Config.__dict__.get('ADMIN_ID', 'admin')
        expected_pass = Config.__dict__.get('ADMIN_PASS', 'admin')
        if admin_id == expected_id and admin_pass == expected_pass:
            session[ADMIN_SESSION_KEY] = True
        else:
            flash('管理員 ID 或密碼錯誤。')
            return render_template('admin/login.html')

    if not _require_admin():
        return render_template('admin/login.html')

    return render_template('admin/index.html')


@bp.route('/logout')
def logout():
    """管理員登出"""
    session.pop(ADMIN_SESSION_KEY, None)
    return redirect(url_for('admin.index'))


@bp.route('/characters')
def characters():
    """角色管理（對應 MENTE）"""
    if not _require_admin():
        return redirect(url_for('admin.index'))

    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'name')

    query = Character.query
    if search:
        query = query.filter(Character.name.contains(search))

    if sort_by == 'id':
        query = query.order_by(Character.id)
    elif sort_by == 'host':
        query = query.order_by(Character.host)
    else:
        query = query.order_by(Character.name)

    chars = query.all()
    return render_template('admin/characters.html', chars=chars, search=search, sort_by=sort_by)


@bp.route('/delete_char', methods=['POST'])
def delete_char():
    """刪除角色（對應 DEL）"""
    if not _require_admin():
        return redirect(url_for('admin.index'))

    char_id = request.form.get('char_id', '').strip()
    if not char_id:
        flash('未指定角色。')
        return redirect(url_for('admin.characters'))

    char = db.session.get(Character, char_id)
    if not char:
        flash('角色不存在。')
        return redirect(url_for('admin.characters'))

    name = char.name

    # 清除相關資料
    CharacterItem.query.filter_by(char_id=char_id).delete()
    BattleHistory.query.filter_by(char_id=char_id).delete()
    BattleState.query.filter_by(char_id=char_id).delete()
    Message.query.filter(
        (Message.sender_id == char_id) |
        (Message.scope == f'player_{char_id}')
    ).delete(synchronize_session='fetch')

    db.session.delete(char)
    db.session.commit()

    append_game_log(1, f'<span style="color:red"><b>[刪除]</b></span> {name}已被刪除。')

    flash(f'{name} 已刪除。')
    return redirect(url_for('admin.characters'))


@bp.route('/warn', methods=['POST'])
def warn():
    """發出警告（對應 WARN）"""
    if not _require_admin():
        return redirect(url_for('admin.index'))

    player = request.form.get('player', '').strip()
    if not player:
        flash('請輸入玩家名稱。')
        return redirect(url_for('admin.index'))

    append_game_log(1, f'<span style="color:red">[警告]</span>管理員向 {player} 發出警告。')
    flash(f'已向 {player} 發出警告。')
    return redirect(url_for('admin.index'))


@bp.route('/cleanup_inactive')
def cleanup_inactive():
    """顯示不活躍玩家列表（對應 MINDEL）"""
    if not _require_admin():
        return redirect(url_for('admin.index'))

    now = int(time.time())
    threshold = now - 604800  # 7 天

    inactive = Character.query.filter(
        Character.total_wins < 10,
        Character.last_action < threshold,
    ).all()

    return render_template('admin/cleanup.html', inactive=inactive)


@bp.route('/cleanup_inactive_exec', methods=['POST'])
def cleanup_inactive_exec():
    """執行不活躍玩家清除（對應 MINDEL2）"""
    if not _require_admin():
        return redirect(url_for('admin.index'))

    now = int(time.time())
    threshold = now - 604800

    inactive = Character.query.filter(
        Character.total_wins < 10,
        Character.last_action < threshold,
    ).all()

    count = 0
    for char in inactive:
        CharacterItem.query.filter_by(char_id=char.id).delete()
        BattleHistory.query.filter_by(char_id=char.id).delete()
        BattleState.query.filter_by(char_id=char.id).delete()
        Message.query.filter(
            (Message.sender_id == char.id) |
            (Message.scope == f'player_{char.id}')
        ).delete(synchronize_session='fetch')
        db.session.delete(char)
        count += 1

    db.session.commit()
    append_game_log(
        1,
        f'<span style="color:red"><b>[刪除]</b></span>'
        f' 一週未登入且未滿10戰的玩家（{count}人）已被清除。',
    )

    flash(f'已清除 {count} 位不活躍玩家。')
    return redirect(url_for('admin.index'))


@bp.route('/init_data', methods=['POST'])
def init_data():
    """全部初始化（對應 INIT_DATA）— 危險操作"""
    if not _require_admin():
        return redirect(url_for('admin.index'))

    confirm = request.form.get('confirm', '')
    if confirm != 'YES':
        flash('請輸入 YES 確認全部初始化。')
        return redirect(url_for('admin.index'))

    # 清除所有遊戲資料
    GameLog.query.delete()
    Message.query.delete()
    ForumPost.query.delete()
    CountryRule.query.delete()
    BattleState.query.delete()
    BattleHistory.query.delete()
    CharacterItem.query.delete()
    Unit.query.delete()
    Character.query.delete()
    Country.query.delete()

    # 重置城鎮
    for t in Town.query.all():
        t.country_id = 0
        t.gold = 0
        t.weapon_dev = 0
        t.armor_dev = 0
        t.acc_dev = 0
        t.item_dev = 0
        t.trade = 0
        t.town_hp = 1000
        t.town_max_hp = 1000
        t.town_str = 300
        t.town_def = 300
        t.town_dex = 300

    db.session.commit()
    flash('全部資料已初始化。')
    return redirect(url_for('admin.index'))


@bp.route('/admin_login', methods=['POST'])
def admin_login():
    """管理員以指定角色身份登入（對應 LOGIN）"""
    if not _require_admin():
        return redirect(url_for('admin.index'))

    char_id = request.form.get('char_id', '').strip()
    char = db.session.get(Character, char_id)
    if not char:
        flash('角色不存在。')
        return redirect(url_for('admin.index'))

    # 直接設定 session
    session['char_id'] = char.id
    flash(f'已以 {char.name} 的身份登入。')
    return redirect(url_for('main.top'))
