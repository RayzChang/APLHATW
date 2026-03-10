from datetime import datetime
import pytz

class TradingScheduler:
    @staticmethod
    def is_market_open_static() -> bool:
        tw_tz = pytz.timezone("Asia/Taipei")
        now = datetime.now(tw_tz)
        if now.weekday() >= 5:  # 週末
            return False
        market_open = now.replace(hour=9, minute=0, second=0)
        market_close = now.replace(hour=13, minute=30, second=0)
        return market_open <= now <= market_close
