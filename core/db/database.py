from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.settings import DB_PATH

# 確保資料庫目錄存在
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# 建立 SQLite 連線 Engine
# check_same_thread=False 讓 FastAPI 多執行緒不報錯
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# 建立 Session 的工廠函式
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 宣告 Base，給 models 繼承用
Base = declarative_base()

def get_db():
    """
    提供 FastAPI 取得 Database Session 用的 Dependency
    確保每次 request 後自動 close session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
