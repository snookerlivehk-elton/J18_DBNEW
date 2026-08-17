import os
import datetime
import requests
from fastapi import FastAPI, Request, Query, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# 导入现有的解析器逻辑与资料库模块
from src.j18_dbnew.parsers.history_result import HistoryResultParser
from src.j18_dbnew.db.database import SessionLocal, engine, Base, get_db
from src.j18_dbnew.db import models, crud

# 在应用启动时自动建立资料表 (开发用，正式环境建议用 Alembic 等 Migration 工具)
models.Base.metadata.create_all(bind=engine)

# 初始化 FastAPI 应用
app = FastAPI(title="J18 DBNEW Query")

# 配置 Jinja2 模板引擎目录，并显式指定 context 键名，避免旧式写法引发的 TypeError: unhashable type: 'dict' 问题
templates = Jinja2Templates(directory="templates", context_processors=[])

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    渲染首页 UI
    """
    return templates.TemplateResponse(request=request, name="index.html", context={})

@app.get("/api/query")
async def query_data(date: str = Query(..., description="赛事日期 YYYY-MM-DD")):
    """
    根据日期请求远程 API，并返回解析后的赛果数据
    """
    # 强制从环境变量读取基础 URL，不在程式码中留下任何预设网址
    base_url = os.getenv("J18_HISTORY_RESULT_URL")
    if not base_url:
        return {"code": -1, "msg": "系统设定错误：未配置数据来源入口 (J18_HISTORY_RESULT_URL)", "data": []}
        
    url = f"{base_url}?date={date}"
    try:
        # 发送请求获取源数据
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        
        # 使用项目内的解析器解析数据为规范化模型
        canonical_races = HistoryResultParser.parse(payload)
        
        # 返回成功响应与解析后的数据列表
        return {
            "code": 0,
            "msg": "success",
            "data": [race.model_dump() for race in canonical_races]
        }
    except Exception as e:
        # 异常情况返回错误信息
        return {"code": -1, "msg": str(e), "data": []}

@app.get("/api/sync")
async def sync_data_to_db(date: str = Query(..., description="赛事日期 YYYY-MM-DD"), db: Session = Depends(get_db)):
    """
    【手动触发入口】从远程 API 获取指定日期的赛事资料，解析后存入数据库
    """
    base_url = os.getenv("J18_HISTORY_RESULT_URL")
    if not base_url:
        return {"code": -1, "msg": "系统设定错误：未配置数据来源入口 (J18_HISTORY_RESULT_URL)", "data": None}

    url = f"{base_url}?date={date}"
    try:
        # 1. 获取资料
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        # 2. 解析资料为 Canonical Model
        canonical_races = HistoryResultParser.parse(payload)

        if not canonical_races:
            return {"code": 0, "msg": "当日无赛事资料可同步", "data": {"races_synced": 0}}

        # 3. 将解析后的资料写入数据库
        races_synced = crud.sync_races_to_db(db=db, canonical_races=canonical_races, racing_date=date)

        return {
            "code": 0,
            "msg": f"同步成功，已将 {races_synced} 场赛事写入资料库",
            "data": {"races_synced": races_synced}
        }
    except Exception as e:
        return {"code": -1, "msg": f"同步失败: {str(e)}", "data": None}


def _parse_date(s: str) -> datetime.date:
    """解析 YYYY-MM-DD 日期字符串并返回 date 对象；失败抛出 ValueError"""
    return datetime.datetime.strptime(s, "%Y-%m-%d").date()


def _date_range(start: datetime.date, end: datetime.date):
    """生成 [start, end] 区间（含首尾）的日期迭代器"""
    cur = start
    one_day = datetime.timedelta(days=1)
    while cur <= end:
        yield cur
        cur += one_day


@app.get("/api/backfill")
async def backfill_range_to_db(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD（默认为今天）"),
    db: Session = Depends(get_db)
):
    """
    【批量回填入口】将 start_date ~ end_date 区间（含两端）的历史资料逐日同步写入数据库
    用法示例：/api/backfill?start_date=2025-09-07&end_date=2026-08-17
    """
    base_url = os.getenv("J18_HISTORY_RESULT_URL")
    if not base_url:
        return {"code": -1, "msg": "系统设定错误：未配置数据来源入口 (J18_HISTORY_RESULT_URL)", "data": None}

    # 1. 校验并准备日期区间
    try:
        sd = _parse_date(start_date)
        ed = _parse_date(end_date) if end_date else datetime.date.today()
    except ValueError:
        return {"code": -1, "msg": "日期格式错误，请使用 YYYY-MM-DD", "data": None}

    if sd > ed:
        return {"code": -1, "msg": "起始日期不能大于结束日期", "data": None}

    # 2. 逐日抓取并入库，记录详细结果便于排查
    results = []
    total_races = 0
    skipped_empty = 0
    failed_dates = 0

    for d in _date_range(sd, ed):
        d_str = d.strftime("%Y-%m-%d")
        url = f"{base_url}?date={d_str}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            canonical_races = HistoryResultParser.parse(payload)

            if not canonical_races:
                # 当日没有赛事：跳过，不视为失败
                results.append({"date": d_str, "status": "skipped", "races": 0, "msg": "当日无赛事资料"})
                skipped_empty += 1
                continue

            races_synced = crud.sync_races_to_db(db=db, canonical_races=canonical_races, racing_date=d_str)
            total_races += races_synced
            results.append({"date": d_str, "status": "ok", "races": races_synced, "msg": "success"})
        except Exception as e:
            failed_dates += 1
            results.append({"date": d_str, "status": "failed", "races": 0, "msg": str(e)})

    summary = {
        "start_date": sd.isoformat(),
        "end_date": ed.isoformat(),
        "days_scanned": len(results),
        "days_ok": sum(1 for r in results if r["status"] == "ok"),
        "days_skipped": skipped_empty,
        "days_failed": failed_dates,
        "races_synced_total": total_races,
    }
    return {
        "code": 0 if failed_dates == 0 else -1,
        "msg": "批量回填完成（部分日期失败，请查看详情）" if failed_dates else "批量回填完成",
        "data": {"summary": summary, "details": results}
    }

if __name__ == "__main__":
    import uvicorn
    # 供本地直接执行使用
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.get("/api/sync_status")
async def get_sync_status(db: Session = Depends(get_db)):
    """
    查询数据库的同步状态：已同步的最早/最晚日期、赛事总数、马匹纪录总数
    """
    status = crud.get_sync_status(db)
    return {"code": 0, "msg": "success", "data": status}
