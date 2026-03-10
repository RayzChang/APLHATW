import { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, RefreshCcw } from 'lucide-react';

import api from '../api/axiosConfig';
import { fetchScanStatus, fetchTradingPortfolio, fetchTradingPositions, fetchTradingTrades, fetchWatchlistQuotes, resetSimulation, runScanCycle, toggleAutoScan } from '../api/trading';
import { BacktestSection } from '../components/BacktestSection';
import { PerformanceChart } from '../components/charts/PerformanceChart';
import { WatchlistPanel } from '../features/auto-trading/WatchlistPanel';
import { PortfolioHero } from '../features/portfolio/PortfolioHero';
import { PositionsTable } from '../features/portfolio/PositionsTable';
import { TradeHistoryPanel } from '../features/portfolio/TradeHistoryPanel';
import type { PortfolioResponse, PositionItem, ScanState, TradeRecord, WatchlistQuote } from '../types/trading';

const DEFAULT_SCAN_STATE: ScanState = {
  is_scanning: false,
  current: 0,
  total: 0,
  message: '待機中',
  auto_scan_enabled: false,
  market_status: 'WAITING',
  daily_api_cost_twd: 0,
  last_scan_time: null,
  last_scan_summary: '',
  stocks_screened: 0,
  candidates_found: 0,
  orders_placed: 0,
};

export function Dashboard() {
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [positions, setPositions] = useState<PositionItem[]>([]);
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistQuote[]>([]);
  const [watchlistSymbols, setWatchlistSymbols] = useState<string[]>(['2330', '2317', '2454', '2412', '0050', '6415']);
  const [scanState, setScanState] = useState<ScanState>(DEFAULT_SCAN_STATE);
  const [isLoadingPortfolio, setIsLoadingPortfolio] = useState(true);
  const [isWatchlistLoading, setIsWatchlistLoading] = useState(true);

  const formatMoney = useCallback(
    (val: number) => new Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD', minimumFractionDigits: 0 }).format(val),
    [],
  );

  const fetchSettings = useCallback(async () => {
    try {
      const res = await api.get('/api/settings');
      if (Array.isArray(res.data?.watchlist) && res.data.watchlist.length > 0) {
        setWatchlistSymbols(res.data.watchlist);
      }
    } catch (error) {
      console.error('Settings fetch failed:', error);
    }
  }, []);

  const refreshScanStatus = useCallback(async () => {
    try {
      const data = await fetchScanStatus();
      setScanState((prev) => ({ ...prev, ...data }));
      return data.is_scanning;
    } catch {
      return false;
    }
  }, []);

  const refreshPortfolioData = useCallback(async () => {
    setIsLoadingPortfolio(true);
    try {
      const [portfolioData, positionsData, tradesData] = await Promise.all([
        fetchTradingPortfolio(),
        fetchTradingPositions(),
        fetchTradingTrades(),
      ]);
      setPortfolio(portfolioData);
      setPositions(positionsData || []);
      setTrades(tradesData || []);
      if (portfolioData.scan_state) {
        setScanState((prev) => ({ ...prev, ...portfolioData.scan_state! }));
      }
    } catch (error) {
      console.error('Failed to refresh dashboard:', error);
    } finally {
      setIsLoadingPortfolio(false);
    }
  }, []);

  const refreshWatchlist = useCallback(async () => {
    if (watchlistSymbols.length === 0) {
      setWatchlist([]);
      setIsWatchlistLoading(false);
      return;
    }

    setIsWatchlistLoading(true);
    try {
      const items = await fetchWatchlistQuotes(watchlistSymbols);
      setWatchlist(items);
    } catch (error) {
      console.error('Watchlist fetch failed:', error);
    } finally {
      setIsWatchlistLoading(false);
    }
  }, [watchlistSymbols]);

  useEffect(() => {
    fetchSettings();
    refreshPortfolioData();
    refreshScanStatus();
  }, [fetchSettings, refreshPortfolioData, refreshScanStatus]);

  useEffect(() => {
    refreshWatchlist();
    const interval = setInterval(refreshWatchlist, 60000);
    return () => clearInterval(interval);
  }, [refreshWatchlist]);

  useEffect(() => {
    const interval = setInterval(refreshPortfolioData, 30000);
    return () => clearInterval(interval);
  }, [refreshPortfolioData]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;

    if (scanState.is_scanning) {
      interval = setInterval(async () => {
        const stillScanning = await refreshScanStatus();
        if (!stillScanning) {
          refreshPortfolioData();
        }
      }, 1000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [scanState.is_scanning, refreshPortfolioData, refreshScanStatus]);

  useEffect(() => {
    const interval = setInterval(() => {
      if (!scanState.is_scanning) {
        refreshScanStatus();
      }
    }, 60000);
    return () => clearInterval(interval);
  }, [scanState.is_scanning, refreshScanStatus]);

  const handleRunScan = useCallback(async () => {
    try {
      await runScanCycle();
      setScanState((prev) => ({ ...prev, is_scanning: true, message: '準備啟動全市場掃描...' }));
    } catch {
      alert('啟動失敗，請確認後端是否正在運行中！');
    }
  }, []);

  const handleToggleAutoScan = useCallback(async () => {
    try {
      const data = await toggleAutoScan();
      setScanState((prev) => ({ ...prev, auto_scan_enabled: data.auto_scan_enabled }));
      refreshScanStatus();
    } catch {
      alert('切換失敗，請確認後端是否正在運行中！');
    }
  }, [refreshScanStatus]);

  const handleReset = useCallback(async () => {
    if (!confirm('確定要重置所有模擬交易紀錄嗎？此動作無法復原！')) return;
    try {
      await resetSimulation();
      alert('模擬交易庫存與資金已重置！');
      refreshPortfolioData();
    } catch {
      alert('重置失敗！');
    }
  }, [refreshPortfolioData]);

  const handleExportCSV = useCallback(() => {
    const link = document.createElement('a');
    link.href = '/api/trading/trades/export';
    link.download = 'AlphaTW_trades.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, []);

  const latestTrades = useMemo(() => trades.slice().reverse().slice(0, 20), [trades]);

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-6 md:py-8 space-y-6 animate-in fade-in duration-700 pb-12">
      <PortfolioHero
        portfolio={portfolio}
        scanState={scanState}
        isLoading={isLoadingPortfolio}
        onRefresh={refreshPortfolioData}
        onToggleAutoScan={handleToggleAutoScan}
        onRunScan={handleRunScan}
        onReset={handleReset}
      />

      <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_0.95fr] gap-6 items-stretch">
        <div className="panel p-4 md:p-5 space-y-4 min-h-[420px]">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-black uppercase tracking-widest">資產曲線與交易節奏</h3>
            <button onClick={refreshPortfolioData} className="p-1 hover:bg-white/10 rounded-lg transition-colors">
              <RefreshCcw className={`w-3.5 h-3.5 text-text-muted ${isLoadingPortfolio ? 'animate-spin' : ''}`} />
            </button>
          </div>

          <div className="bg-black/20 rounded-xl p-4 border border-white/5 h-[260px]">
            <PerformanceChart
              data={portfolio?.equity_curve || []}
              totalProfitPct={portfolio?.total_profit_pct || 0}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-black/20 rounded-xl p-4 border border-white/5">
              <div className="text-[10px] uppercase tracking-widest text-text-muted font-bold mb-1">掃描摘要</div>
              <div className="text-sm font-black text-white">{scanState.last_scan_summary || '尚未執行掃描'}</div>
            </div>
            <div className="bg-black/20 rounded-xl p-4 border border-white/5">
              <div className="text-[10px] uppercase tracking-widest text-text-muted font-bold mb-1">已下單筆數</div>
              <div className="text-2xl font-black font-mono text-brand-primary">{scanState.orders_placed}</div>
            </div>
            <div className="bg-black/20 rounded-xl p-4 border border-white/5">
              <div className="text-[10px] uppercase tracking-widest text-text-muted font-bold mb-1">候選股票數</div>
              <div className="text-2xl font-black font-mono text-white">{scanState.candidates_found}</div>
            </div>
          </div>

          <div className="bg-black/20 rounded-xl p-4 border border-white/5">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-black uppercase tracking-widest text-text-muted">近期成交快照</h4>
              <span className="text-[10px] text-text-muted">最近 {latestTrades.length} 筆</span>
            </div>
            <div className="space-y-2 max-h-[210px] overflow-y-auto pr-1">
              {latestTrades.length === 0 ? (
                <div className="h-[120px] flex items-center justify-center text-text-muted text-sm">暫無交易紀錄</div>
              ) : (
                latestTrades.map((t, i) => (
                  <div key={i} className="flex gap-3 p-2.5 bg-white/5 rounded-xl border border-white/5 hover:bg-white/10 transition-colors">
                    <div className="flex flex-col items-center shrink-0">
                      <span className="text-[10px] font-mono text-text-muted">{new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      <div className={`w-1 h-full mt-1 rounded-full ${t.action === 'BUY' ? 'bg-success' : 'bg-danger'}`}></div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between mb-0.5">
                        <span className="text-sm font-black text-text-main">{t.stock_id}</span>
                        <span className={`text-[10px] font-black px-1.5 py-0.5 rounded ${t.action === 'BUY' ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'}`}>
                          {t.action}
                        </span>
                      </div>
                      <p className="text-xs text-text-muted truncate">執行{t.action === 'BUY' ? '買入' : '賣出'} {t.shares} 股，成交價 {t.price.toFixed(2)}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <WatchlistPanel items={watchlist} isLoading={isWatchlistLoading} onRefresh={refreshWatchlist} />
      </div>

      <PositionsTable positions={positions} isLoading={isLoadingPortfolio} formatMoney={formatMoney} />

      <BacktestSection isScanRunning={scanState.is_scanning} />

      <TradeHistoryPanel trades={trades} formatMoney={formatMoney} onExport={handleExportCSV} />

      {isLoadingPortfolio && !portfolio && (
        <div className="panel p-6 flex items-center justify-center text-text-muted gap-3">
          <Loader2 className="w-5 h-5 animate-spin text-brand-primary" />
          Dashboard 數據載入中...
        </div>
      )}
    </div>
  );
}
