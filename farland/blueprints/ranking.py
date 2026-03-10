"""
Farland History Ⅱ — Ranking Blueprint
對應 sit.cgi（世界情勢 + 國家排名）
"""
from flask import Blueprint, render_template

from farland.models import db, Character, Town, Country, GameLog
from farland.common import get_all_countries
from game_data import ELEMENTS, ELEMENT_BG, ELEMENT_FG

bp = Blueprint('ranking', __name__, url_prefix='/ranking')


@bp.route('/')
def situation():
    """世界情勢（對應 sit.cgi）"""
    countries = get_all_countries()
    all_towns = Town.query.all()

    # 各國人口數
    pop_counts = {}
    for c in countries:
        pop_counts[c.id] = Character.query.filter_by(country_id=c.id).count()

    # 各國領土數
    town_counts = {}
    for c in countries:
        town_counts[c.id] = sum(1 for t in all_towns if t.country_id == c.id)

    # 國家資料列表
    country_data = []
    for c in countries:
        king = db.session.get(Character, c.king_id) if c.king_id else None
        country_data.append({
            'country': c,
            'king_name': king.name if king else '（無）',
            'population': pop_counts.get(c.id, 0),
            'gold': c.gold,
            'territory': town_counts.get(c.id, 0),
        })

    n = len(countries)

    # 人口排名
    by_pop = sorted(country_data, key=lambda x: x['population'], reverse=True)
    for rank, d in enumerate(by_pop, 1):
        d['pop_rank'] = rank
        d['point'] = (n - rank) * 2

    # 財力排名
    by_gold = sorted(country_data, key=lambda x: x['gold'], reverse=True)
    for rank, d in enumerate(by_gold, 1):
        d['gold_rank'] = rank
        d['point'] += (n - rank)

    # 領土排名
    by_territory = sorted(country_data, key=lambda x: x['territory'], reverse=True)
    for rank, d in enumerate(by_territory, 1):
        d['territory_rank'] = rank
        d['point'] += (n - rank)

    # 綜合排名
    ranked = sorted(country_data, key=lambda x: x['point'], reverse=True)

    # 各排名第一
    pop_leader = by_pop[0]['country'].name if by_pop else ''
    gold_leader = by_gold[0]['country'].name if by_gold else ''
    territory_leader = by_territory[0]['country'].name if by_territory else ''

    # 自動生成解說
    commentary = _generate_commentary(ranked, n, pop_leader, gold_leader, territory_leader)

    # 世界地圖
    country_map = {c.id: c for c in countries}
    grid = [[None for _ in range(6)] for _ in range(6)]
    for t in all_towns:
        if 0 <= t.x < 6 and 0 <= t.y < 6:
            con = country_map.get(t.country_id)
            grid[t.y][t.x] = {
                'town': t,
                'country': con,
                'bg_color': ELEMENT_BG.get(con.element, '#555555') if con else '#555555',
                'country_name': con.name if con else '無所屬',
            }

    # 歷史日誌
    history_logs = (GameLog.query
                    .filter_by(log_type=2)
                    .order_by(GameLog.created_at.desc())
                    .limit(50).all())

    return render_template(
        'ranking.html',
        ranked=ranked,
        world_map=grid,
        commentary=commentary,
        history_logs=history_logs,
    )


def _generate_commentary(ranked, n, pop_leader, gold_leader, territory_leader):
    """自動生成情勢解說（對應 sit.cgi 的 $com）"""
    if n == 0:
        return '目前尚無國家建立。未來將會是怎樣的展開呢。'

    if n == 1:
        name = ranked[0]['country'].name
        return f'目前是「{name}國」獨霸天下的局面。「{name}國」能就此統一世界嗎？'

    top = ranked[0]['country'].name
    lines = [f'目前共有 {n} 個國家的情勢。其中「{top}國」最為優勢。']

    if n > 4:
        second = ranked[1]['country'].name
        third = ranked[2]['country'].name
        lines.append(f'第二位是「{second}國」，緊接其後的是「{third}國」，局勢相當緊張。')

    lines.append(
        f'人口方面「{pop_leader}國」、財力方面「{gold_leader}國」'
        f'、領土方面「{territory_leader}國」分別領先。'
    )

    if ranked[0].get('pop_rank') == 1:
        lines.append(f'「{top}國」在人口上也佔優勢，看來世界將以「{top}國」為中心運轉。')
    else:
        lines.append(
            f'然而「{pop_leader}國」在人口上佔據優勢，'
            f'與「{top}國」之間的攻防值得關注。'
        )

    if n > 2:
        last = ranked[-1]['country'].name
        lines.append(
            f'「{last}國」雖然處境不利，但優秀的人才隨時可能扭轉局勢。'
        )

    if n == 2:
        lines.append('這兩個國家之間，究竟誰能笑到最後呢...')

    return '\n'.join(lines)
