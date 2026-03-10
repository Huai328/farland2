"""
Farland History Ⅱ — Flask 設定
轉換自原始 conf.cgi
"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'farland2-dev-secret-key-change-in-prod')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(BASE_DIR, "farland2.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = os.path.join(BASE_DIR, '.flask_session')

    # === 遊戲設定（原 conf.cgi） ===
    GAME_VERSION = 'Farland History Ⅱ Ver2.11'
    GAME_TITLE = 'Farland History Ⅱ'

    # 最大登入人數
    MAX_LOGIN = 50

    # 更新間隔（秒）
    BATTLE_TIME = 60       # 戰鬥
    KINGDOM_TIME = 600     # 國政
    MAP_TIME = 1200        # 地圖
    CONV_TIME = 600        # 轉換

    # 經濟
    INVEST_GOLD = 50000    # 投資所需金額
    BU_GOLD = 10_000_000   # 銀行上限

    # 角色限制
    DOUBLE_ENTRY = True    # 允許雙重登錄檢查
    CHARA_ENTRY_CLOSED = False  # 是否關閉新角色註冊
    MAX_JOB_LEVEL = 99999
    MAX_ITEMS = 15
    CHARA_IMG_COUNT = 202  # 角色圖片數量
    LEVEL_CAP = 100
    STAT_CAP = 400         # 各屬性上限

    # 訊息顯示數量
    MSG_ALL = 5       # 全體
    MSG_COUNTRY = 5   # 國家
    MSG_PERSONAL = 3  # 個人
    MSG_UNIT = 3      # 部隊

    # Session 逾時
    SESSION_TIMEOUT = 1200  # 秒

    # 認證
    ATTESTATION_ENABLED = False
    SENDMAIL_PATH = '/usr/bin/sendmail'

    # UI 配色
    BG_COLOR = '#ffddcc'
    FONT_COLOR = '#883300'
    FONT_COLOR2 = '#ffffee'
