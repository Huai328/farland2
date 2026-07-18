"""
Farland History Ⅱ — Flask Application Factory
"""
from flask import Flask
from flask_session import Session

from config import Config
from farland.models import db


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
def create_app():
    # ... 上面原本的其他程式碼保持不動 ...

    with app.app_context():
        db.session.execute(db.text("DROP SCHEMA public CASCADE;"))
        db.session.execute(db.text("CREATE SCHEMA public;"))
        db.session.commit()
        db.create_all()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
