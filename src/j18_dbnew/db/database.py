import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# 載入 .env 環境變數
load_dotenv()

# 獲取資料庫連線字串，如果沒有設定，預設使用本地 SQLite 供開發測試用
# 在 Railway 上，我們會設定 DATABASE_URL 為 postgresql://...
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./j18_local.db")

# 如果 URL 是 postgres:// (舊版 SQLAlchemy 不支援)，替換為 postgresql://
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 針對 SQLite 需要特別設定 connect_args
connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

# 建立 SQLAlchemy 引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args=connect_args
)

# 建立 SessionLocal 類別，每次呼叫都會產生一個資料庫會話
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 建立 Base 類別，供 Models 繼承
Base = declarative_base()

def get_db():
    """
    FastAPI 依賴注入用的資料庫會話產生器
    確保每個請求結束後都會關閉連線
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
