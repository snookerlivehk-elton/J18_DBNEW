import os
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

# 配置 Jinja2 模板引擎目录
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    渲染首页 UI
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/query")
async def query_data(date: str = Query(..., description="赛事日期 YYYY-MM-DD")):
    """
    根据日期请求远程 API，并返回解析后的赛果数据
    """
    url = f"https://api.j18.hk/calculate/v1/historyResult?date={date}"
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
    url = f"https://api.j18.hk/calculate/v1/historyResult?date={date}"
    try:
        # 1. 获取资料
        resp = requests.get(url, timeout=10)
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

if __name__ == "__main__":
    import uvicorn
    # 供本地直接执行使用
    uvicorn.run(app, host="0.0.0.0", port=8000)
