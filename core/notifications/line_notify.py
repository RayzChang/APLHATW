import requests
from loguru import logger
from config.settings import LINE_NOTIFY_TOKEN

class LineNotifier:
    """
    透過 LINE Notify 傳送文字或貼圖訊息
    (需在 .env 中設定 LINE_NOTIFY_TOKEN)
    """

    API_URL = "https://notify-api.line.me/api/notify"

    def __init__(self, token: str = None):
        self.token = token or LINE_NOTIFY_TOKEN

    def send_message(self, message: str) -> bool:
        """
        發送純文字訊息
        """
        if not self.token:
            logger.warning("LINE_NOTIFY_TOKEN is not set. Skipping LINE notification.")
            return False

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        payload = {"message": message}
        
        try:
            response = requests.post(self.API_URL, headers=headers, data=payload, timeout=10)
            if response.status_code == 200:
                logger.debug("LINE notification sent successfully.")
                return True
            else:
                logger.error(f"Failed to send LINE message: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Exception while sending LINE message: {e}")
            return False
            
    def alert_trade(self, action: str, symbol: str, price: float, reason: str = ""):
        """專門發送交易通知"""
        emoji = "📈" if action in ["BUY", "TAKE_PROFIT"] else "📉"
        if action == "STOP_LOSS":
            emoji = "🛑"
        elif action == "UPDATE_STOP":
            emoji = "🛡️"
            
        msg = f"\n{emoji} 【台股推手提示】 \n動作: {action}\n標的: {symbol}\n觸發價格: {price}"
        if reason:
            msg += f"\n原因: {reason}"
            
        self.send_message(msg)
