# Farland History Ⅱ — Python Flask 版

將 2006-2007 年代的日文線上多人策略 RPG「Farland History Ⅱ Ver2.11」從 Perl 5 CGI 完整遷移至 Python Flask。

## 概要

原始版本以 Perl CGI + flat-file 文字檔構成，本專案將其現代化為：

- **後端**：Python 3.12+ / Flask 3.x
- **資料庫**：SQLite（可切換 MariaDB）
- **ORM**：SQLAlchemy 2.x
- **模板**：Jinja2（取代 Perl heredoc inline HTML）
- **認證**：Flask-Session（取代 hidden field 傳遞 id/pass）
- **編碼**：全面 UTF-8（原始為 Shift_JIS）
- **介面語言**：繁體中文

## 遊戲系統

| 系統 | 說明 | Blueprint |
|------|------|-----------|
| 戰鬥 | PvE（4 地形 + 隱藏迷宮）、訓練、討伐 | `battle.py` |
| 城鎮 | 商店（武器/防具/飾品/道具）、銀行、旅館、競技場、拍賣場 | `town.py` |
| 角色 | 裝備、轉職、技能、煉金、匯款、寄送道具 | `status.py` |
| 國家 | 建國、城鎮開發、裝備開發、城牆強化、攻城、軍事編制、論壇、法規 | `country.py` |
| 移動/侵攻 | 6x6 世界地圖、鄰接城鎮移動、攻城戰（含滅國/天下統一判定） | `main.py` |
| 世界情勢 | 國家排名（人口/財力/領土）、世界地圖、自動解說、歷史紀錄 | `ranking.py` |
| 管理後台 | 角色管理、不活躍清除、警告、資料初始化 | `admin.py` |

## 快速開始

```bash
# 建立虛擬環境
python3 -m venv .venv
source .venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 啟動開發伺服器
python app.py
```

伺服器預設在 `http://127.0.0.1:5000` 啟動。

```bash
# 關閉開發伺服器（於終端按 Ctrl+C，或使用以下指令）
kill $(pgrep -f 'python.*app\.py')
```

## 專案結構

```
farland2-py/
├── app.py                      # Flask app factory
├── config.py                   # 遊戲設定（時間間距、經濟參數等）
├── game_data.py                # 職業/屬性/裝備/戰場等常數定義
├── requirements.txt
├── farland/
│   ├── models.py               # SQLAlchemy 資料模型（15 個表）
│   ├── auth.py                 # 登入驗證
│   ├── common.py               # 共用工具函數
│   ├── battle_support.py       # 戰鬥計算引擎
│   ├── blueprints/
│   │   ├── main.py             # 首頁、登入、主畫面、移動、侵攻、聊天
│   │   ├── battle.py           # 戰鬥系統
│   │   ├── town.py             # 城鎮系統
│   │   ├── status.py           # 角色管理
│   │   ├── country.py          # 國家系統
│   │   ├── ranking.py          # 世界情勢/排名
│   │   └── admin.py            # 管理後台
│   └── services/
│       ├── character.py        # 角色建立/驗證
│       └── equipment.py        # 裝備計算/物品欄管理
├── templates/                  # Jinja2 模板
│   ├── base.html
│   ├── top.html                # 主畫面
│   ├── ranking.html            # 世界情勢
│   ├── battle/                 # 戰鬥相關頁面
│   ├── town/                   # 城鎮相關頁面
│   ├── status/                 # 角色管理頁面
│   ├── country/                # 國家系統頁面
│   ├── etc/                    # 移動/侵攻頁面
│   └── admin/                  # 管理後台頁面
├── static/
│   ├── img/                    # 遊戲圖片資源
│   └── css/farland.css
└── scripts/
    └── import_data.py          # 原始資料匯入腳本
```

## 設定

所有遊戲參數集中在 `config.py`：

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `BATTLE_TIME` | 60 | 一般行動冷卻時間（秒） |
| `KINGDOM_TIME` | 600 | 國政行動冷卻時間（秒） |
| `MAP_TIME` | 1200 | 侵攻冷卻時間（秒） |
| `INVEST_GOLD` | 50000 | 城鎮開發所需金額 |
| `MAX_ITEMS` | 15 | 角色最大持有道具數 |
| `LEVEL_CAP` | 100 | 等級上限 |
| `STAT_CAP` | 400 | 各能力值上限 |
| `ADMIN_ID` | admin | 管理員帳號 |
| `ADMIN_PASS` | admin | 管理員密碼 |

## 資料匯入

若需從原始 Perl 版匯入資料：

```bash
python scripts/import_data.py
```

腳本會讀取原始 `data/*.cgi`（Shift_JIS 編碼）並匯入 SQLite。

## 技術棧

| 項目 | 版本 |
|------|------|
| Python | 3.12+ |
| Flask | 3.x |
| SQLAlchemy | 2.x |
| SQLite | 內建（可切換 MariaDB） |
| Jinja2 | 內建於 Flask |

## 原始版本

- **Farland History Ⅱ Ver2.11**
- 原作語言：Perl 5 CGI
- 原始規模：~18,136 行 Perl、191 個檔案
- 資料儲存：Shift_JIS flat-file
- 年代：2006-2007
