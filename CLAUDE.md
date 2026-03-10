# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

Farland History Ⅱ Ver2.11 — 從 Perl 5 CGI (2006-2007) 遷移至 Python Flask 的日系線上多人策略 RPG。原始資料為 Shift_JIS 編碼 flat-file，已轉為 UTF-8 + SQLite。所有介面文字使用繁體中文。

## 開發指令

```bash
# 啟動開發伺服器
python3 app.py
# 伺服器於 http://127.0.0.1:5000

# 匯入原始 Perl 資料
python3 scripts/import_data.py

# 翻譯日文資料檔（../data/*.cgi → data/*.cgi）
python3 scripts/translate_data.py
```

無測試框架、無 linter、無 CI/CD。資料庫在首次啟動時由 `db.create_all()` 自動建立 `farland2.db`。

## 架構核心

### POST 分發器模式

所有遊戲操作統一 POST 至 `/top`，由 `main.py:top()` 根據 `request.form['mode']` 分發到對應 Blueprint。模式分類定義於 `main.py` 頂部的四組集合：`BATTLE_MODES`、`TOWN_MODES`、`STATUS_MODES`、`COUNTRY_MODES`。新增遊戲功能時必須將 mode 值加入對應集合。

### 戰鬥引擎 (`battle_support.py`)

純邏輯計算模組，所有函數操作 `CombatState` / `Fighter` dataclass，不直接操作 DB。核心流程：`PARA`（參數初始化）→ `MATT`（玩家攻擊）→ `EATT`（敵方攻擊）→ `LVUP`（升級）。Blueprint `battle.py` 負責 DB 讀寫與結果渲染。

### 冷卻時間機制

`Character.last_action`（Unix timestamp）僅在實際遊戲行動（戰鬥/移動/侵攻）時更新，不在頁面刷新時更新。三種冷卻間隔由 `config.py` 控制：`BATTLE_TIME`(60s)、`KINGDOM_TIME`(600s)、`MAP_TIME`(1200s)。

### 資料格式

原始 `.cgi` 檔案使用 `<>` 作為欄位分隔符。`data/` 目錄為 UTF-8 翻譯後的遊戲資料，`../data/` 為原始 Shift_JIS 來源。`scripts/translate_data.py` 包含 ~900+ 日中翻譯字典。

### 認證

玩家認證透過 Flask Session（`session['char_id']`），由 `auth.py:login_required` 裝飾器保護路由。管理後台獨立認證（`session['admin']`），預設帳密在 `Config.ADMIN_ID` / `Config.ADMIN_PASS`。

## 關鍵慣例

- 裝備欄位為逗號分隔字串 `no,name,val,dmg,wei,ele,hit,cl,sta,type,flg`，存於 `Character.weapon/armor/accessory`
- 能力值上限存於 `Character.stat_caps`（逗號分隔），職業點數存於 `Character.job_points`
- 城鎮座標固定於 6×6 格世界地圖（`Town.x`, `Town.y`），移動僅限相鄰格
- 國家 ID 0 表示無國籍
- 所有遊戲參數集中於 `config.py:Config`，常數定義於 `game_data.py`
- 15 個 SQLAlchemy Model 定義於單一 `models.py`
- Jinja2 模板全域變數由 `app.py:create_app()` 注入
