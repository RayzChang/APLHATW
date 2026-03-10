"""
LINE Bot 推播通知模組
====================

使用 LINE Messaging API 推送交易通知給使用者。
LINE Notify 已於 2025/3/31 停止服務，改用 LINE Messaging API (Push Message)。

所需環境變數：
  LINE_CHANNEL_ACCESS_TOKEN — LINE Developers 頻道存取權杖
  LINE_USER_ID              — 接收通知的 LINE 使用者 ID
"""

import requests
from loguru import logger
from config.settings import LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID

PUSH_API = "https://api.line.me/v2/bot/message/push"

_enabled = True


def is_configured() -> bool:
    return bool(LINE_CHANNEL_ACCESS_TOKEN) and bool(LINE_USER_ID)


def set_enabled(on: bool):
    global _enabled
    _enabled = on
    logger.info(f"LINE notification {'enabled' if on else 'disabled'}")


def get_enabled() -> bool:
    return _enabled


def send_message(text: str) -> bool:
    if not _enabled or not is_configured():
        return False

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    body = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}],
    }

    try:
        import requests
        resp = requests.post(PUSH_API, json=body, headers=headers, timeout=10)
        if resp.status_code == 200:
            logger.debug("LINE push OK")
            return True
        logger.warning(f"LINE push failed {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        logger.warning(f"LINE push error: {e}")
        return False


# ── 預組訊息 ──────────────────────────────────────────────────────

def notify_buy(stock_id: str, name: str, price: float, shares: int,
               confidence: float, stop_loss: float, take_profit: float):
    text = (
        f"📈 AI 買入通知\n"
        f"──────────\n"
        f"股票：{name}（{stock_id}）\n"
        f"成交價：${price:,.2f}\n"
        f"數量：{shares:,} 股\n"
        f"AI 信心度：{confidence:.0%}\n"
        f"停損價：${stop_loss:,.2f}\n"
        f"停利價：${take_profit:,.2f}\n"
        f"──────────\n"
        f"💡 如欲跟單，請自行於券商下單"
    )
    send_message(text)


def notify_sell(stock_id: str, name: str, price: float, shares: int,
                reason: str, pnl: float, pnl_pct: float):
    emoji = "🟢" if pnl >= 0 else "🔴"
    text = (
        f"📉 AI 賣出通知\n"
        f"──────────\n"
        f"股票：{name}（{stock_id}）\n"
        f"成交價：${price:,.2f}\n"
        f"數量：{shares:,} 股\n"
        f"賣出原因：{reason}\n"
        f"{emoji} 損益：${pnl:+,.0f}（{pnl_pct:+.2f}%）\n"
        f"──────────\n"
        f"💡 如有跟單，請同步操作"
    )
    send_message(text)


def notify_scan_complete(stocks_screened: int, candidates: int, orders: int):
    text = (
        f"🤖 AI 全市場掃描完成\n"
        f"──────────\n"
        f"掃描股票：{stocks_screened:,} 支\n"
        f"技術篩選：{candidates} 個候選\n"
        f"AI 下單：{orders} 筆\n"
        f"──────────\n"
        f"請打開 AlphaTW 查看詳情"
    )
    send_message(text)
