from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from core.db.database import Base

class Portfolio(Base):
    """資產總表：紀錄當前可用餘額與歷史最高資產等"""
    __tablename__ = "portfolio"

    id = Column(Integer, primary_key=True, index=True)
    total_assets = Column(Float, default=1000000.0)    # 總資產 (現金 + 股票市值)
    available_cash = Column(Float, default=1000000.0)  # 可用現金
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Position(Base):
    """持倉表：記錄目前手上持有的股票"""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), unique=True, index=True, nullable=False) # 股票代碼
    name = Column(String(50), nullable=False)
    
    amount = Column(Integer, nullable=False, default=0)       # 股數 (1張 = 1000股)
    entry_price = Column(Float, nullable=False)               # 平均買入成本
    current_price = Column(Float, nullable=False)             # 最新報價
    
    # 風控相關欄位
    high_price_since_entry = Column(Float, nullable=False)    # 買入後創下的最高價
    stop_loss_price = Column(Float, nullable=True)            # 當下設定的停損價
    take_profit_price = Column(Float, nullable=True)          # 當下設定的停利價
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TradeHistory(Base):
    """交易明細表：記錄每一筆買賣的歷史"""
    __tablename__ = "trade_history"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), index=True, nullable=False)
    name = Column(String(50), nullable=False)
    
    action = Column(String(10), nullable=False)         # "BUY" 或 "SELL"
    amount = Column(Integer, nullable=False)            # 交易股數
    price = Column(Float, nullable=False)               # 成交價
    fee = Column(Float, default=0.0)                    # 手續費
    tax = Column(Float, default=0.0)                    # 證交稅
    
    # AI 決策相關
    reason = Column(Text, nullable=True)                # AI 決定買賣的原因
    
    created_at = Column(DateTime, default=datetime.utcnow)
