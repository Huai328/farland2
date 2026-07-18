"""
Farland History Ⅱ — Flask Application Factory
"""
from flask import Flask
from flask_session import Session
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from config import Config
from farland.models import db
# 引入您的角色資料模型 (Character)
from farland.models import Character


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static',
    )
    app.config.from_object(config_class)

    # 初始化擴展
    db.init_app(app)
    Session(app)

    # 初始化 Flask-Admin 自動後台系統
    # 注意：這裡把 url 設定為 /sys-admin，避免與您原本就有的 admin 藍圖網址衝突
    admin = Admin(app, name='Farland 自動後台管理', url='/sys-admin')
    
    # 將「角色資料表」註冊進自動後台
    admin.add_view(ModelView(Character, db.session, name='角色數值修改'))

    # 註冊 Blueprints
    from farland.blueprints.main import bp as main_bp
    from farland.blueprints.status import bp as status_bp
    from farland.blueprints.town import bp as town_bp
    from farland.blueprints.battle import bp as battle_bp
    from farland.blueprints.country import bp as country_bp
    from farland.blueprints.ranking import bp as ranking_bp
    from farland.blueprints.admin import bp as admin_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(town_bp)
    app.register_blueprint(battle_bp)
    app.register_blueprint(country_bp)
    app.register_blueprint(ranking_bp)
    app.register_blueprint(admin_bp)

    # 注入模板全域變數
    from game_data import ELEMENTS, ELEMENT_BG, ELEMENT_FG, JOBS, JOB_TYPES, EQUIP_TYPES
    app.jinja_env.globals.update(
        GAME_TITLE=Config.GAME_TITLE,
        GAME_VERSION=Config.GAME_VERSION,
        ELEMENTS=ELEMENTS,
        ELEMENT_BG=ELEMENT_BG,
        ELEMENT_FG=ELEMENT_FG,
        JOBS=JOBS,
        JOB_TYPES=JOB_TYPES,
        EQUIP_TYPES=EQUIP_TYPES,
        BG_COLOR=Config.BG_COLOR,
        FONT_COLOR=Config.FONT_COLOR,
        FONT_COLOR2=Config.FONT_COLOR2,
    )

    # 建立資料庫表
    with app.app_context():
        db.create_all()

    return app



if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
