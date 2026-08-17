import os
import requests
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# 导入现有的解析器逻辑
from src.j18_dbnew.parsers.history_result import HistoryResultParser

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

if __name__ == "__main__":
    import uvicorn
    # 供本地直接执行使用
    uvicorn.run(app, host="0.0.0.0", port=8000)
