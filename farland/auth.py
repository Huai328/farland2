"""
Farland History Ⅱ — 認證模組
替代原始 hidden field id/pass 模式，使用 Flask session
"""
import functools
import time

from flask import session, redirect, url_for, flash

from farland.models import db, Character
from config import Config


def login_user(char_id: str, password: str) -> Character | None:
    """驗證並登入使用者，成功返回 Character，失敗返回 None"""
    char = db.session.get(Character, char_id)
    if char is None or char.password != password:
        return None

    # 更新最後活動時間
    char.last_action = int(time.time())
    char.host = ''  # TODO: 取得 remote host
    db.session.commit()

    session['char_id'] = char.id
    return char


def logout_user():
    """登出"""
    session.pop('char_id', None)


def get_current_character() -> Character | None:
    """取得當前登入角色，並檢查 session 逾時"""
    char_id = session.get('char_id')
    if not char_id:
        return None

    char = db.session.get(Character, char_id)
    if char is None:
        session.pop('char_id', None)
        return None

    # 檢查逾時
    now = int(time.time())
    if now > char.last_action + Config.SESSION_TIMEOUT:
        session.pop('char_id', None)
        return None

    return char


def login_required(f):
    """裝飾器：要求登入"""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        char = get_current_character()
        if char is None:
            flash('連線已逾時，請重新登入。')
            return redirect(url_for('main.login'))
        return f(char, *args, **kwargs)
    return decorated
