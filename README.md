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
| 移動/侵攻 | 6×6 世界地圖、鄰接城鎮移動、攻城戰（含滅國/天下統一判定） | `main.py` |
| 世界情勢 | 國家排名（人口/財力/領土）、世界地圖、自動解說、歷史紀錄 | `ranking.py` |
| 管理後台 | 角色管理、不活躍清除、警告、資料初始化 | `admin.py` |

## 快速開始

```bash
# 建立虛擬環境
python3 -m venv .venv
source .venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 匯入遊戲資料（首次執行）
python3 scripts/import_data.py

# 啟動開發伺服器
python3 app.py
```

伺服器預設在 `http://127.0.0.1:5000` 啟動。資料庫 `farland2.db` 由 `db.create_all()` 於首次啟動時自動建立。

## 專案結構

```
farland2/
├── app.py                      # Flask 應用工廠
├── config.py                   # 遊戲設定（冷卻時間、經濟參數、UI 配色等）
├── game_data.py                # 職業/屬性/裝備/戰場等常數定義
├── requirements.txt
├── farland/
│   ├── models.py               # SQLAlchemy 資料模型（19 個表）
│   ├── auth.py                 # 登入驗證（Flask Session）
│   ├── common.py               # 共用工具函數
│   ├── battle_support.py       # 戰鬥計算引擎（純邏輯，不操作 DB）
│   ├── blueprints/
│   │   ├── main.py             # 首頁、登入、主畫面、POST 分發器、移動、侵攻
│   │   ├── battle.py           # 戰鬥系統
│   │   ├── town.py             # 城鎮系統
│   │   ├── status.py           # 角色管理
│   │   ├── country.py          # 國家系統
│   │   ├── ranking.py          # 世界情勢/排名
│   │   └── admin.py            # 管理後台
│   └── services/
│       ├── character.py        # 角色建立/驗證
│       └── equipment.py        # 裝備計算/物品欄管理
├── templates/                  # Jinja2 模板（54 個 HTML）
│   ├── base.html
│   ├── top.html                # 主畫面
│   ├── battle/                 # 戰鬥相關頁面
│   ├── town/                   # 城鎮相關頁面
│   ├── status/                 # 角色管理頁面
│   ├── country/                # 國家系統頁面
│   ├── etc/                    # 移動/侵攻頁面
│   ├── admin/                  # 管理後台頁面
│   └── partials/               # 可復用部分模板
├── static/
│   ├── img/                    # 遊戲圖片資源
│   └── css/farland.css
├── data/                       # 遊戲資料檔（UTF-8，<> 分隔）
├── scripts/
│   ├── import_data.py          # 資料匯入腳本（data/*.cgi → SQLite）
│   └── translate_data.py       # 日文→繁體中文翻譯腳本（~900+ 詞條）
└── migrations/                 # Alembic 資料庫遷移
```

## 資料管道

遊戲資料從原始 Perl 版經兩階段處理：

```
原始 Shift_JIS .cgi ──translate_data.py──→ data/ (UTF-8) ──import_data.py──→ SQLite
```

- `scripts/translate_data.py`：讀取原始 Shift_JIS 資料，透過 ~900+ 日中翻譯字典轉為繁體中文 UTF-8，輸出至 `data/`
- `scripts/import_data.py`：讀取 `data/*.cgi`（UTF-8），解析 `<>` 分隔格式，匯入 SQLite

```bash
# 翻譯日文資料（需要原始 ../data/ 目錄）
python3 scripts/translate_data.py

# 匯入翻譯後資料至資料庫
python3 scripts/import_data.py
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

## 切換至 MariaDB

預設使用 SQLite，如需切換至 MariaDB，設定環境變數 `DATABASE_URL` 即可：

```bash
# 安裝 MariaDB 驅動
pip install mariadb mysqlclient

# 設定連線字串
export DATABASE_URL="mariadb+mariadbconnector://root:1qaz@WSX@127.0.0.1:3306/farland2"

# 建立資料庫（MariaDB CLI）
mariadb -u root -p -e "CREATE DATABASE farland2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 啟動伺服器（首次啟動自動建表）
python3 app.py

# 匯入遊戲資料
python3 scripts/import_data.py
```

也可寫入 `.env` 或直接修改 `config.py` 中的 `SQLALCHEMY_DATABASE_URI`。

## 架構設計

### POST 分發器模式

所有遊戲操作統一 POST 至 `/top`，由 `main.py:top()` 根據 `request.form['mode']` 分發到對應 Blueprint。模式分類定義於 `main.py` 頂部的四組集合：`BATTLE_MODES`、`TOWN_MODES`、`STATUS_MODES`、`COUNTRY_MODES`。

### 戰鬥引擎

`battle_support.py` 為純邏輯計算模組，操作 `Fighter` / `CombatState` dataclass，不直接操作 DB。核心流程：`PARA`（參數初始化）→ `MATT`（玩家攻擊）→ `EATT`（敵方攻擊）→ `LVUP`（升級）。

### 冷卻時間機制

`Character.last_action`（Unix timestamp）僅在實際遊戲行動（戰鬥/移動/侵攻）時更新，不在頁面刷新時更新。

## 技術棧

| 項目 | 版本 |
|------|------|
| Python | 3.12+ |
| Flask | ≥ 3.0 |
| Flask-SQLAlchemy | ≥ 3.1 |
| Flask-Session | ≥ 0.8 |
| SQLAlchemy | ≥ 2.0 |
| Alembic | ≥ 1.13 |
| SQLite | 內建 |

## 原始版本

- **Farland History Ⅱ Ver2.11**
- 原作語言：Perl 5 CGI
- 原始規模：~18,136 行 Perl、191 個檔案
- 資料儲存：Shift_JIS flat-file
- 年代：2006-2007
