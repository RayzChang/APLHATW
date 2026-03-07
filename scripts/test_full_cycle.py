# 執行一次完整循環測試（不管是否開盤，強制跑）
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
from core.agents.orchestrator import TradingOrchestrator
from core.execution.simulator import TradeSimulator
from core.strategy.screener import StockScreener
from core.data.tw_data_fetcher import TWDataFetcher

fetcher = TWDataFetcher()
orchestrator = TradingOrchestrator()
simulator = TradeSimulator(initial_capital=1_000_000)
screener = StockScreener(data_fetcher=fetcher)

# 強制用10支股票測試（不跑全市場）
test_stocks = ["2330","2317","2454","2412","2303","2882","1301","2308","3711","2886"]
candidates = screener.screen_batch(test_stocks)
print(f"L1篩選結果：{candidates}")

prices = {}
for stock_id in candidates[:3]:
    result = orchestrator.run_full_analysis(stock_id)
    prices[stock_id] = result.get("current_price")
    print(f"\n{'='*50}")
    print(f"股票：{stock_id}")
    print(f"Action：{result.get('action')}")
    print(f"Confidence：{result.get('confidence')}")
    print(f"Reasoning：{result.get('reasoning')}")
    print(f"Technical Report：{result.get('technical_report')}")
    print(f"Sentiment Report：{result.get('sentiment_report')}")
    print(f"Risk Report：{result.get('risk_report')}")
    print(f"{'='*50}")
    exec_result = simulator.execute_signal(result)
    print(f"執行結果：{exec_result}")

print("\n--- 持倉概覽 ---")
print(simulator.get_portfolio_summary())

print("\n--- 風險控管檢查 ---")
risk_actions = simulator.check_risk_management(prices)
print(f"風控動作：{risk_actions}")

print("\n--- 重新載入 DB 驗證 ---")
simulator.load_state()
print(f"目前部位：{list(simulator.positions.keys())}")