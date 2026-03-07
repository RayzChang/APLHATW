from dataclasses import dataclass
from typing import Optional
from loguru import logger

@dataclass
class Position:
    """模擬持倉資料結構"""
    symbol: str
    amount: int  # 股數
    entry_price: float
    current_price: float
    high_price_since_entry: float  # 買入後創下的最高價 (計算追蹤止損用)
    stop_loss_price: Optional[float]
    take_profit_price: Optional[float]

@dataclass
class RiskCheckResult:
    """風控檢查結果"""
    action_required: bool
    action_type: str  # 'STOP_LOSS', 'TAKE_PROFIT', 'UPDATE_STOP', 'NONE'
    reason: str
    new_stop_price: Optional[float] = None

class DynamicStopsEngine:
    """
    動態停損/停利引擊
    包含: 固定停損停利、保本止損、追蹤止損
    """

    def __init__(self, break_even_pct: float = 3.0, trailing_stop_pct: float = 5.0):
        # 預設參數
        self.break_even_pct = break_even_pct / 100.0  # 當獲利達 3% 時啟動保本
        self.trailing_stop_pct = trailing_stop_pct / 100.0  # 從最高點回落 5% 停損

    def evaluate_position(self, pos: Position) -> RiskCheckResult:
        """綜合評估一筆持倉，判斷是否需要平倉或更新停損點"""
        current_profit_pct = (pos.current_price - pos.entry_price) / pos.entry_price

        # 1. 檢查固定停損 (Fixed Stop Loss)
        if pos.stop_loss_price and pos.current_price <= pos.stop_loss_price:
            return RiskCheckResult(
                action_required=True, 
                action_type="STOP_LOSS", 
                reason=f"觸及停損價 {pos.stop_loss_price}"
            )

        # 2. 檢查固定停利 (Fixed Take Profit)
        if pos.take_profit_price and pos.current_price >= pos.take_profit_price:
             return RiskCheckResult(
                action_required=True, 
                action_type="TAKE_PROFIT", 
                reason=f"觸及停利價 {pos.take_profit_price}"
            )

        # 3. 追蹤止損 (Trailing Stop)
        # 計算從買入以來的最高價能容忍的下跌底線
        trailing_stop_level = pos.high_price_since_entry * (1 - self.trailing_stop_pct)
        # 如果目前設定的停損點低於追蹤止損底線，且目前的獲利大於 0，我們就該把停損點往上拉
        if current_profit_pct > 0:
            best_stop = trailing_stop_level
            
            # 4. 保本止損 (Break-even Stop) - 作為追蹤止損的最低保障
            if current_profit_pct >= self.break_even_pct:
                break_even_price = pos.entry_price * 1.005 # 加一點點手續費緩衝
                best_stop = max(trailing_stop_level, break_even_price)

            # 如果算出來的最好停損點(best_stop)，比目前設定的停損價(stop_loss_price)還要高，那就發出更新通知
            if pos.stop_loss_price is None or best_stop > pos.stop_loss_price:
                # 只有當它離現價還有一點距離 (大於現價)，或者是它大於原本的停損價才更新
                if best_stop < pos.current_price:
                    return RiskCheckResult(
                        action_required=True,
                        action_type="UPDATE_STOP",
                        reason=f"啟動動態防護，停損價由 {pos.stop_loss_price or '無'} 上調至 {best_stop:.2f} (最高價 {pos.high_price_since_entry:.2f})",
                        new_stop_price=round(best_stop, 2)
                    )

        # 沒事發生，持續抱著    
        return RiskCheckResult(action_required=False, action_type="NONE", reason="持倉安全區間內")
