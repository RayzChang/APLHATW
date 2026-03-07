from sqlalchemy.orm import Session
from loguru import logger
from core.db.models import Portfolio, Position, TradeHistory
from core.notifications.line_notify import LineNotifier

class TradingEngine:
    """模擬交易引擎：負責執行買賣單、扣款與建立明細"""
    
    FEE_RATE = 0.001425  # 手續費 (千分之 1.425)
    TAX_RATE = 0.003     # 證交稅 (千分之 3)

    def __init__(self, db: Session):
        self.db = db
        self.notifier = LineNotifier()

    def get_portfolio(self) -> Portfolio:
        portfolio = self.db.query(Portfolio).first()
        if not portfolio:
            raise Exception("系統尚未初始化 Portfolio 紀錄！")
        return portfolio

    def execute_order(
        self, 
        symbol: str, 
        name: str, 
        action: str, 
        amount: int, 
        price: float, 
        reason: str = "",
        stop_loss_price: float = None,
        take_profit_price: float = None
    ) -> bool:
        """
        處理一筆訂單
        action: "BUY" 或 "SELL"
        amount: 這次交易的總數 (股數), 一張 = 1000 股
        """
        portfolio = self.get_portfolio()
        position = self.db.query(Position).filter(Position.symbol == symbol).first()

        try:
            if action == "BUY":
                return self._process_buy(portfolio, position, symbol, name, amount, price, reason, stop_loss_price, take_profit_price)
            elif action == "SELL":
                return self._process_sell(portfolio, position, symbol, name, amount, price, reason)
            else:
                logger.error(f"未知的交易動作: {action}")
                return False
        except Exception as e:
            self.db.rollback()
            logger.error(f"訂單執行失敗 [{symbol} {action}]: {e}")
            return False

    def _process_buy(self, portfolio: Portfolio, position: Position, symbol: str, name: str, amount: int, price: float, reason: str, sl: float, tp: float) -> bool:
        trade_value = amount * price
        fee = int(trade_value * self.FEE_RATE)
        fee = max(fee, 20)  # 最低手續費 20 元
        total_cost = trade_value + fee

        if portfolio.available_cash < total_cost:
            logger.warning(f"買進失敗 {symbol}: 餘額不足。所需 {total_cost}, 可用 {portfolio.available_cash}")
            return False

        # 扣款
        portfolio.available_cash -= total_cost

        # 寫入 Transaction
        th = TradeHistory(symbol=symbol, name=name, action="BUY", amount=amount, price=price, fee=fee, tax=0, reason=reason)
        self.db.add(th)

        # 更新或新增持倉
        if position:
            # 已經有部位了，重新計算平均成本
            total_shares = position.amount + amount
            total_invested = (position.amount * position.entry_price) + total_cost
            position.entry_price = total_invested / total_shares
            position.amount = total_shares
            position.current_price = price
            position.high_price_since_entry = max(position.high_price_since_entry, price)
        else:
            # 建立新部位
            position = Position(
                symbol=symbol, name=name, amount=amount, 
                entry_price=total_cost / amount, current_price=price,
                high_price_since_entry=price,
                stop_loss_price=sl,
                take_profit_price=tp
            )
            self.db.add(position)

        self.db.commit()
        logger.success(f"成功買進 {symbol} {amount} 股 @ {price:.2f}")
        self.notifier.alert_trade("BUY", symbol, price, reason=f"花費: {total_cost}")
        return True

    def _process_sell(self, portfolio: Portfolio, position: Position, symbol: str, name: str, amount: int, price: float, reason: str) -> bool:
        if not position or position.amount < amount:
            logger.warning(f"賣出失敗 {symbol}: 庫存不足。想賣 {amount}, 目前持有 {position.amount if position else 0}")
            return False

        trade_value = amount * price
        fee = int(trade_value * self.FEE_RATE)
        fee = max(fee, 20)
        tax = int(trade_value * self.TAX_RATE)
        net_income = trade_value - fee - tax

        # 加款
        portfolio.available_cash += net_income

        # 寫入 Transaction
        th = TradeHistory(symbol=symbol, name=name, action="SELL", amount=amount, price=price, fee=fee, tax=tax, reason=reason)
        self.db.add(th)

        # 減少持倉或刪除
        position.amount -= amount
        if position.amount <= 0:
            self.db.delete(position)
        else:
            position.current_price = price

        self.db.commit()
        logger.success(f"成功賣出 {symbol} {amount} 股 @ {price:.2f}")
        self.notifier.alert_trade("SELL", symbol, price, reason=f"獲利結算, 實拿: {net_income}")
        return True

    def evaluate_portfolio_value(self):
        """重新計算帳戶總市值 (現金 + 股票市值)"""
        portfolio = self.get_portfolio()
        positions = self.db.query(Position).all()
        stock_value = sum([p.amount * p.current_price for p in positions])
        portfolio.total_assets = portfolio.available_cash + stock_value
        self.db.commit()
