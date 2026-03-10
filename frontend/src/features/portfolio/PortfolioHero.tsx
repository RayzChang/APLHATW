import { Bot, Cpu, Loader2, RefreshCw, Search } from 'lucide-react';
import type { PortfolioResponse, ScanState } from '../../types/trading';

interface PortfolioHeroProps {
  portfolio: PortfolioResponse | null;
  scanState: ScanState;
  isLoading: boolean;
  onRefresh: () => void;
  onToggleAutoScan: () => void;
  onRunScan: () => void;
  onReset: () => void;
}

const formatMoney = (val: number) =>
  new Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD', minimumFractionDigits: 0 }).format(val);

export function PortfolioHero({
  portfolio,
  scanState,
  isLoading,
  onRefresh,
  onToggleAutoScan,
  onRunScan,
  onReset,
}: PortfolioHeroProps) {
  const cashPct =
    portfolio?.total_assets && portfolio.total_assets > 0
      ? `${((portfolio.cash / portfolio.total_assets) * 100).toFixed(1)}%`
      : '－';

  return (
    <div className="space-y-6">
      <div className="panel bg-[#1a2035] flex flex-col md:flex-row items-stretch divide-y md:divide-y-0 md:divide-x divide-white/10">
        {[
          ['💰 虛擬總資產', formatMoney(portfolio?.total_assets || 1000000), 'bg-brand-primary'],
          ['💵 可用現金', formatMoney(portfolio?.cash || 0), 'bg-text-muted'],
          ['📈 累積總獲利', `${(portfolio?.total_profit || 0) > 0 ? '+' : ''}${formatMoney(portfolio?.total_profit || 0)}`, 'bg-success'],
          ['🎯 綜合報酬率', `${(portfolio?.total_profit_pct || 0).toFixed(2)}%`, 'bg-brand-primary'],
        ].map(([label, value, barColor], idx) => (
          <div key={idx} className="flex-1 p-4 flex items-center gap-4">
            <div className={`w-1.5 h-10 rounded-full ${barColor}`}></div>
            <div>
              <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-1">{label}</div>
              <div
                className={`text-2xl font-black font-mono tracking-tighter ${
                  idx >= 2 ? ((portfolio?.total_profit || 0) >= 0 ? 'text-danger' : 'text-success') : 'text-white'
                }`}
              >
                {isLoading ? '---' : value}
              </div>
              {idx === 1 && <div className="text-[10px] text-text-muted mt-0.5">佔總資產 {cashPct}</div>}
            </div>
          </div>
        ))}
      </div>

      <div className="panel p-3 px-5 flex flex-wrap items-center justify-between gap-4 border-brand-primary/20 bg-brand-primary/5">
        <div className="flex flex-wrap items-center gap-4">
          <button onClick={onRefresh} className="btn btn-secondary gap-2 px-4 py-2 text-sm">
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} /> 刷新數據
          </button>

          <div className="flex items-center gap-3 px-4 py-1.5 bg-black/40 rounded-xl border border-white/10 ml-2">
            <span className="text-sm font-bold text-white flex items-center gap-2">
              <Bot className={`w-4 h-4 ${scanState.auto_scan_enabled ? 'text-brand-primary animate-pulse' : 'text-text-muted'}`} />
              全天候自動交易
            </span>
            <button
              onClick={onToggleAutoScan}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                scanState.auto_scan_enabled ? 'bg-brand-primary' : 'bg-gray-600'
              }`}
            >
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${scanState.auto_scan_enabled ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>

          {scanState.is_scanning && !scanState.auto_scan_enabled ? (
            <div className="flex items-center gap-3 bg-black/40 px-4 py-2 rounded-xl border border-brand-primary/30 min-w-[350px]">
              <Loader2 className="w-4 h-4 text-brand-primary animate-spin shrink-0" />
              <div className="flex flex-col w-full">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-brand-primary font-bold">{scanState.message}</span>
                  <span className="text-text-muted">{scanState.total > 0 ? `${Math.round((scanState.current / scanState.total) * 100)}%` : ''}</span>
                </div>
                {scanState.total > 0 && (
                  <div className="h-1 flex-1 bg-white/10 rounded-full overflow-hidden w-full">
                    <div className="h-full bg-brand-primary rounded-full transition-all duration-500 shadow-[0_0_10px_#6366f1]" style={{ width: `${(scanState.current / scanState.total) * 100}%` }}></div>
                  </div>
                )}
              </div>
            </div>
          ) : !scanState.auto_scan_enabled ? (
            <button onClick={onRunScan} className="btn btn-primary glow-purple gap-2 px-6 py-2 bg-gradient-to-r from-brand-primary to-indigo-600 hover:scale-105 text-sm">
              <Search className="w-4 h-4" /> 執行單次 AI 分析
            </button>
          ) : null}
        </div>

        <div className="flex items-center gap-4">
          {scanState.auto_scan_enabled && (
            <div className="flex items-center gap-2 text-xs font-mono bg-black/40 px-3 py-1.5 rounded-lg border border-white/5">
              <span className="text-text-muted">狀態:</span>
              <span
                className={`font-black uppercase tracking-wider ${
                  scanState.market_status === 'OPEN'
                    ? 'text-success animate-pulse'
                    : scanState.market_status === 'WAITING'
                      ? 'text-text-muted'
                      : 'text-yellow-400'
                }`}
              >
                {scanState.market_status === 'OPEN' ? '開盤中-運作中' : scanState.market_status === 'CLOSED' ? '已休市-待機中' : '等待連線...'}
              </span>
            </div>
          )}
          <button onClick={onReset} className="btn btn-danger gap-2 px-4 py-2 text-sm">
            <RefreshCw className="w-4 h-4" /> 重置模擬
          </button>
        </div>
      </div>

      <div className="panel p-5 border border-white/5 space-y-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-brand-primary" />
            <h3 className="text-sm font-black uppercase tracking-widest">AI 自動交易系統說明</h3>
          </div>
          <div className="flex items-center gap-2 bg-black/30 px-3 py-1.5 rounded-lg border border-white/5">
            <span className="text-[10px] text-text-muted font-bold tracking-wider">今日 API 預估花費:</span>
            <span className="text-sm font-mono font-black text-warning">${scanState.daily_api_cost_twd?.toFixed(1) || '0.0'} <span className="text-[10px]">TWD</span></span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="bg-black/20 rounded-xl p-3 border border-white/5">
            <div className="text-xs font-black text-white mb-1">全市場自動掃描</div>
            <div className="text-[10px] text-text-muted leading-relaxed">交易時間內自動掃描台股全市場，每次完成後冷卻 15 分鐘，兼顧效率與 API 成本。</div>
          </div>
          <div className="bg-black/20 rounded-xl p-3 border border-white/5">
            <div className="text-xs font-black text-white mb-1">兩段式決策</div>
            <div className="text-[10px] text-text-muted leading-relaxed">先做技術篩選，再由分析 pipeline 與決策引擎生成交易訊號，只在高信心時下單。</div>
          </div>
          <div className="bg-black/20 rounded-xl p-3 border border-white/5">
            <div className="text-xs font-black text-white mb-1">風控自動接手</div>
            <div className="text-[10px] text-text-muted leading-relaxed">持倉建立後，停損、止盈、保本與追蹤止損由風控引擎持續監控。</div>
          </div>
        </div>
      </div>
    </div>
  );
}
