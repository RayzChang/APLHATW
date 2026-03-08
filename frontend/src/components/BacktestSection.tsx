import { useState } from 'react';
import { FlaskConical, ChevronDown, ChevronUp, Loader2, TrendingUp, TrendingDown, Trophy, AlertTriangle, Info, Globe, Layers } from 'lucide-react';
import { PerformanceChart } from './charts/PerformanceChart';
import api from '../api/axiosConfig';

interface BacktestTrade {
    symbol: string;
    name: string;
    action: 'BUY' | 'SELL';
    date: string;
    price: number;
    shares: number;
    value: number;
    fee: number;
    pnl: number | null;
    pnl_pct: number | null;
    reason: string;
    entry_price: number;
    entry_date: string;
}

interface SymbolStat {
    symbol: string;
    name: string;
    trades: number;
    total_pnl_pct: number;
    win_rate: number;
}

interface BacktestSummary {
    initial_capital: number;
    final_capital: number;
    total_return_pct: number;
    total_pnl: number;
    benchmark_return_pct: number;
    total_trades: number;
    closed_trades: number;
    win_trades: number;
    loss_trades: number;
    win_rate: number;
    max_drawdown_pct: number;
    profit_factor: number;
    max_concurrent_positions: number;
    days: number;
    symbols_scanned: number;
    trading_days: number;
    no_signal_reason: string;
}

interface BacktestResult {
    summary: BacktestSummary;
    equity_curve: Array<{ date: string; equity: number; benchmark: number }>;
    trades: BacktestTrade[];
    symbol_stats: SymbolStat[];
}

const PROGRESS_STEPS_SELECTED = [
    '連接 FinMind 數據庫...',
    '下載 ~50 支台灣各產業龍頭歷史 K 線...',
    '計算技術指標（RSI / KD / MACD / MA20 / ATR）...',
    '逐日模擬 AI 交易決策...',
    '執行風險控管（止損 2×ATR / 止盈 3×ATR）...',
    '計算績效統計（勝率、最大回撤、盈虧比）...',
    '對比 0050 同期持有績效...',
    '整理交易記錄，生成回測報告...',
];

const PROGRESS_STEPS_FULL = [
    '從 FinMind 取得全部上市/上櫃股票清單（約 3600 支）...',
    '建立 yfinance 批次下載佇列...',
    '批量下載第 1 批（~400 支）歷史 K 線...',
    '批量下載第 2 批（~400 支）歷史 K 線...',
    '批量下載第 3 批（~400 支）歷史 K 線...',
    '批量下載第 4 批（~400 支）歷史 K 線...',
    '計算全市場技術指標（RSI / KD / MACD / MA / ATR）...',
    '逐日模擬全市場 AI 掃描與交易決策...',
    '執行風險控管（止損 / 止盈 / 最長持倉）...',
    '計算績效統計，對比 0050 基準，生成完整回測報告...',
];

interface BacktestSectionProps {
    isScanRunning?: boolean;
}

export function BacktestSection({ isScanRunning = false }: BacktestSectionProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [isRunning, setIsRunning] = useState(false);
    const [result, setResult] = useState<BacktestResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [progress, setProgress] = useState(0);
    const [progressMsg, setProgressMsg] = useState('');
    const [isTradesExpanded, setIsTradesExpanded] = useState(false);
    const [days, setDays] = useState(30);
    const [threshold, setThreshold] = useState(3);
    const [fullMarket, setFullMarket] = useState(false);

    const runBacktest = async () => {
        // 全市場模式下，若掃描排程正在下載 yfinance，告知使用者等待
        if (fullMarket && isScanRunning) {
            setError('AI 全市場掃描正在執行中（正在批量下載市場資料），請等待掃描完成後再執行回測，通常需要 3–5 分鐘。');
            return;
        }

        setIsRunning(true);
        setError(null);
        setResult(null);
        setProgress(0);

        const steps = fullMarket ? PROGRESS_STEPS_FULL : PROGRESS_STEPS_SELECTED;
        const stepInterval_ms = fullMarket ? 18000 : 4000;

        let step = 0;
        const stepInterval = setInterval(() => {
            if (step < steps.length) {
                setProgressMsg(steps[step]);
                setProgress(Math.round((step + 1) / steps.length * 88));
                step++;
            }
        }, stepInterval_ms);

        try {
            const res = await api.post(
                '/api/backtest/portfolio',
                { days, buy_score_threshold: threshold, full_market: fullMarket },
                { timeout: 600_000 }   // 全市場最多 10 分鐘
            );
            clearInterval(stepInterval);
            setProgress(100);
            setProgressMsg('回測完成！');
            setResult(res.data);
        } catch (e: unknown) {
            clearInterval(stepInterval);
            const msg = (e as { response?: { data?: { detail?: string } }; message?: string })
                ?.response?.data?.detail
                ?? (e as { message?: string })?.message
                ?? '回測失敗，請確認後端連線正常';
            setError(msg);
        } finally {
            setIsRunning(false);
        }
    };

    const formatMoney = (val: number) =>
        new Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD', minimumFractionDigits: 0 }).format(val);

    const profitColor = (pct: number) => pct >= 0 ? 'text-danger' : 'text-success';

    const summary = result?.summary;

    return (
        <div className="panel overflow-hidden">
            {/* Header */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full p-6 flex justify-between items-center hover:bg-white/5 transition-colors"
            >
                        <h3 className="text-lg font-black tracking-tight flex items-center gap-2">
                                    <span className="bg-brand-primary w-1 h-5 rounded-full inline-block"></span>
                                    <FlaskConical className="w-5 h-5 text-brand-primary" />
                                    AI 回測模擬
                                    <span className="text-xs text-text-muted font-normal ml-1 hidden md:inline">
                                        {result?.summary?.symbols_scanned && result.summary.symbols_scanned > 200
                                            ? `全市場 ${result.summary.symbols_scanned} 支股票 · 100 萬模擬跟單績效`
                                            : '掃描台股各產業龍頭，模擬 100 萬跟單 AI 的歷史績效'
                                        }
                                    </span>
                                </h3>
                <div className="flex items-center gap-3">
                    {summary && summary.closed_trades > 0 && (
                        <span className={`text-sm font-black ${profitColor(summary.total_return_pct)}`}>
                            {summary.total_return_pct > 0 ? '+' : ''}{summary.total_return_pct.toFixed(2)}%
                        </span>
                    )}
                    {isExpanded ? <ChevronUp className="w-5 h-5 text-text-muted" /> : <ChevronDown className="w-5 h-5 text-text-muted" />}
                </div>
            </button>

            {isExpanded && (
                <div className="border-t border-card-border animate-in slide-in-from-top duration-300">
                    <div className="p-6 space-y-6">

                        {/* Mode Toggle */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <button
                                onClick={() => setFullMarket(false)}
                                disabled={isRunning}
                                className={`rounded-xl p-4 border text-left transition-all ${
                                    !fullMarket
                                        ? 'border-brand-primary bg-brand-primary/10'
                                        : 'border-white/10 bg-black/20 hover:bg-white/5'
                                }`}
                            >
                                <div className="flex items-center gap-2 mb-1">
                                    <Layers className={`w-4 h-4 ${!fullMarket ? 'text-brand-primary' : 'text-text-muted'}`} />
                                    <span className={`text-sm font-black ${!fullMarket ? 'text-white' : 'text-text-muted'}`}>
                                        精選標的模式
                                    </span>
                                    <span className="text-[10px] bg-white/10 text-text-muted px-1.5 py-0.5 rounded font-bold">快速</span>
                                </div>
                                <p className="text-[11px] text-text-muted">
                                    掃描台股各產業龍頭 ~50 支，FinMind 歷史 K 線，約 60~120 秒完成
                                </p>
                            </button>
                            <button
                                onClick={() => setFullMarket(true)}
                                disabled={isRunning}
                                className={`rounded-xl p-4 border text-left transition-all ${
                                    fullMarket
                                        ? 'border-yellow-400 bg-yellow-400/10'
                                        : 'border-white/10 bg-black/20 hover:bg-white/5'
                                }`}
                            >
                                <div className="flex items-center gap-2 mb-1">
                                    <Globe className={`w-4 h-4 ${fullMarket ? 'text-yellow-400' : 'text-text-muted'}`} />
                                    <span className={`text-sm font-black ${fullMarket ? 'text-yellow-400' : 'text-text-muted'}`}>
                                        全市場掃描模式
                                    </span>
                                    <span className="text-[10px] bg-yellow-400/20 text-yellow-400 px-1.5 py-0.5 rounded font-bold">真實</span>
                                </div>
                                <p className="text-[11px] text-text-muted">
                                    掃描全部台股 TWSE+TPEX ~3600 支，yfinance 批量下載，約 3~5 分鐘完成
                                </p>
                            </button>
                        </div>

                        {/* Intro */}
                        <div className={`border rounded-xl p-4 flex gap-3 ${
                            fullMarket
                                ? 'bg-yellow-400/5 border-yellow-400/20'
                                : 'bg-brand-primary/5 border-brand-primary/20'
                        }`}>
                            <Info className={`w-5 h-5 shrink-0 mt-0.5 ${fullMarket ? 'text-yellow-400' : 'text-brand-primary'}`} />
                            <div className="text-sm text-text-muted space-y-1.5">
                                {fullMarket ? (
                                    <>
                                        <p className="font-bold text-white">全市場回測：與 AI 即時交易系統同等邏輯</p>
                                        <p>
                                            從 FinMind 取得全部 TWSE + TPEX 普通股清單，透過 yfinance 批量下載所有歷史 K 線，
                                            對每支股票計算技術指標並逐日模擬交易，最接近 AI 系統真實的選股範疇。
                                        </p>
                                        <p className="text-[11px] text-yellow-400/80">
                                            ⚡ 需時約 3~5 分鐘 · 掃描 ~1500+ 支有效數據普通股 · 不受 FinMind 600次/小時限制
                                        </p>
                                    </>
                                ) : (
                                    <>
                                        <p className="font-bold text-white">精選標的快速回測</p>
                                        <p>
                                            掃描台股各產業龍頭（~50 支），以 100 萬本金跟單所有買賣訊號，
                                            快速驗證技術策略的歷史績效。
                                        </p>
                                    </>
                                )}
                                <p className="text-[11px]">
                                    買入條件：技術評分 ≥ 設定值（RSI/KD/MACD/MA20/布林帶五指標投票）
                                    · 止損 2×ATR · 止盈 3×ATR · 最長持倉 20 個交易日
                                </p>
                                {/* 免責說明 */}
                                <div className="mt-2 p-2.5 bg-white/5 rounded-lg border border-white/10">
                                    <p className="text-[10px] text-text-muted leading-relaxed">
                                        <span className="text-white font-bold">⚠️ 重要說明：</span>
                                        回測使用「技術指標評分」模擬買賣決策（免費、快速）。
                                        而真實 AI 即時交易系統在技術篩選後，還會呼叫四個 Gemini AI Agent（技術分析師 / 情緒分析師 / 風控師 / 首席決策官）進行深度精析，
                                        兩者的買賣時機點會有差異。
                                        <br />
                                        回測數據的用途是：驗證「技術指標策略」在歷史上是否能盈利，
                                        以及了解這個市場環境下 AI 系統大致會有的績效表現，而非精確預測 AI 的每一筆交易。
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Controls */}
                        <div className="flex flex-wrap items-center gap-3">
                            <div className="flex items-center gap-2">
                                <label className="text-sm text-text-muted font-bold whitespace-nowrap">回測天數</label>
                                <select
                                    value={days}
                                    onChange={(e) => setDays(Number(e.target.value))}
                                    disabled={isRunning}
                                    className="bg-black/30 border border-white/10 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-brand-primary"
                                >
                                    <option value={15}>15 天（約 10 交易日）</option>
                                    <option value={30}>30 天（約 20 交易日）</option>
                                    <option value={60}>60 天（約 40 交易日）</option>
                                    <option value={90}>90 天（約 60 交易日）</option>
                                </select>
                            </div>
                            <div className="flex items-center gap-2">
                                <label className="text-sm text-text-muted font-bold whitespace-nowrap">買入門檻</label>
                                <select
                                    value={threshold}
                                    onChange={(e) => setThreshold(Number(e.target.value))}
                                    disabled={isRunning}
                                    className="bg-black/30 border border-white/10 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-brand-primary"
                                >
                                    <option value={2}>評分 ≥ 2（積極、較多交易）</option>
                                    <option value={3}>評分 ≥ 3（推薦、多指標共振）</option>
                                    <option value={4}>評分 ≥ 4（保守、強確認訊號）</option>
                                    <option value={5}>評分 ≥ 5（極度保守、極少交易）</option>
                                </select>
                            </div>
                            <button
                                onClick={runBacktest}
                                disabled={isRunning}
                                className={`btn gap-2 px-6 py-2 hover:scale-105 text-sm disabled:opacity-50 disabled:pointer-events-none font-black ${
                                    fullMarket
                                        ? 'bg-gradient-to-r from-yellow-500 to-orange-500 text-black glow-purple'
                                        : 'btn-primary glow-purple bg-gradient-to-r from-brand-primary to-indigo-600'
                                }`}
                            >
                                {isRunning
                                    ? <><Loader2 className="w-4 h-4 animate-spin" /> 回測中...</>
                                    : fullMarket
                                        ? <><Globe className="w-4 h-4" /> 全市場 {days} 日回測</>
                                        : <><FlaskConical className="w-4 h-4" /> 執行 {days} 日回測</>
                                }
                            </button>
                        </div>

                        {/* Progress */}
                        {isRunning && (
                            <div className={`border rounded-xl p-4 space-y-3 ${
                                fullMarket
                                    ? 'bg-black/30 border-yellow-400/20'
                                    : 'bg-black/30 border-brand-primary/20'
                            }`}>
                                <div className="flex items-center gap-2">
                                    <Loader2 className={`w-4 h-4 animate-spin shrink-0 ${fullMarket ? 'text-yellow-400' : 'text-brand-primary'}`} />
                                    <span className={`text-sm font-bold ${fullMarket ? 'text-yellow-400' : 'text-brand-primary'}`}>
                                        {progressMsg || '初始化...'}
                                    </span>
                                </div>
                                <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all duration-1000 ${
                                            fullMarket
                                                ? 'bg-yellow-400 shadow-[0_0_8px_#facc15]'
                                                : 'bg-brand-primary shadow-[0_0_8px_#6366f1]'
                                        }`}
                                        style={{ width: `${progress}%` }}
                                    />
                                </div>
                                <p className="text-xs text-text-muted">
                                    {fullMarket
                                        ? '掃描全部台股（TWSE + TPEX ~3600 支），批量下載並逐日模擬，預計需要 3~5 分鐘...'
                                        : '下載 ~50 支股票歷史資料並逐日模擬，預計需要 60~120 秒...'
                                    }
                                </p>
                            </div>
                        )}

                        {/* Error */}
                        {error && (
                            <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 flex items-start gap-3">
                                <AlertTriangle className="w-5 h-5 text-danger shrink-0 mt-0.5" />
                                <div>
                                    <p className="text-sm font-bold text-danger">回測失敗</p>
                                    <p className="text-xs text-text-muted mt-1">{error}</p>
                                </div>
                            </div>
                        )}

                        {/* No Trades Warning */}
                        {result && summary && summary.closed_trades === 0 && (
                            <div className="bg-warning/10 border border-warning/30 rounded-xl p-4 flex items-start gap-3">
                                <AlertTriangle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
                                <div className="space-y-1">
                                    <p className="text-sm font-bold text-warning">回測完成，但未產生任何交易</p>
                                    <p className="text-xs text-text-muted">
                                        已掃描 <span className="text-white font-bold">{summary.symbols_scanned}</span> 個標的，
                                        <span className="text-white font-bold">{summary.trading_days}</span> 個交易日，
                                        均未達到買入門檻（評分 ≥ {threshold}）。
                                    </p>
                                    <p className="text-xs text-text-muted">
                                        建議：① 將「買入門檻」調低至「評分 ≥ 1」&nbsp;
                                        ② 延長回測天數 ③ 確認 FinMind Token 已在 .env 設定
                                    </p>
                                    {summary.no_signal_reason && (
                                        <details className="mt-2">
                                            <summary className="text-xs text-brand-primary cursor-pointer">查看診斷詳情</summary>
                                            <p className="text-[11px] text-text-muted mt-1 break-all">{summary.no_signal_reason}</p>
                                        </details>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Results */}
                        {result && summary && summary.closed_trades > 0 && (
                            <div className="space-y-6">
                                {/* Primary Result */}
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    {/* Main card */}
                                    <div className={`md:col-span-1 rounded-xl p-5 border text-center ${
                                        summary.total_return_pct >= 0
                                            ? 'bg-danger/10 border-danger/30'
                                            : 'bg-success/10 border-success/30'
                                    }`}>
                                        <div className="text-[10px] text-text-muted uppercase tracking-widest font-bold mb-2">
                                            {summary.days} 天後，100 萬變成
                                        </div>
                                        <div className={`text-3xl font-black font-mono mb-1 ${profitColor(summary.total_return_pct)}`}>
                                            {formatMoney(summary.final_capital)}
                                        </div>
                                        <div className={`text-xl font-black ${profitColor(summary.total_return_pct)}`}>
                                            {summary.total_return_pct > 0 ? '+' : ''}{summary.total_return_pct.toFixed(2)}%
                                        </div>
                                        <div className={`text-sm mt-1 ${profitColor(summary.total_pnl)}`}>
                                            {summary.total_pnl > 0 ? '+' : ''}{formatMoney(summary.total_pnl)}
                                        </div>
                                    </div>

                                    {/* Stats grid */}
                                    <div className="md:col-span-2 grid grid-cols-2 md:grid-cols-3 gap-3">
                                        <div className="bg-black/30 rounded-xl p-3 border border-white/5 text-center">
                                            <div className="text-[10px] text-text-muted uppercase tracking-widest font-bold mb-1">vs 0050 同期</div>
                                            <div className={`text-lg font-black font-mono ${profitColor(summary.benchmark_return_pct)}`}>
                                                {summary.benchmark_return_pct > 0 ? '+' : ''}{summary.benchmark_return_pct.toFixed(2)}%
                                            </div>
                                            <div className={`text-[10px] font-bold mt-0.5 ${
                                                summary.total_return_pct > summary.benchmark_return_pct ? 'text-success' : 'text-danger'
                                            }`}>
                                                {summary.total_return_pct > summary.benchmark_return_pct ? '優於大盤' : '遜於大盤'}
                                            </div>
                                        </div>
                                        <div className="bg-black/30 rounded-xl p-3 border border-white/5 text-center">
                                            <div className="text-[10px] text-text-muted uppercase tracking-widest font-bold mb-1">勝率</div>
                                            <div className={`text-lg font-black font-mono ${summary.win_rate >= 50 ? 'text-success' : 'text-danger'}`}>
                                                {summary.win_rate.toFixed(1)}%
                                            </div>
                                            <div className="text-[10px] text-text-muted">{summary.win_trades}勝 {summary.loss_trades}敗</div>
                                        </div>
                                        <div className="bg-black/30 rounded-xl p-3 border border-white/5 text-center">
                                            <div className="text-[10px] text-text-muted uppercase tracking-widest font-bold mb-1">最大回撤</div>
                                            <div className="text-lg font-black text-danger font-mono">{summary.max_drawdown_pct.toFixed(2)}%</div>
                                        </div>
                                        <div className="bg-black/30 rounded-xl p-3 border border-white/5 text-center">
                                            <div className="text-[10px] text-text-muted uppercase tracking-widest font-bold mb-1">盈虧比</div>
                                            <div className="text-lg font-black text-brand-primary font-mono">
                                                {summary.profit_factor >= 999 ? '∞' : summary.profit_factor.toFixed(2)}
                                            </div>
                                        </div>
                                        <div className="bg-black/30 rounded-xl p-3 border border-white/5 text-center">
                                            <div className="text-[10px] text-text-muted uppercase tracking-widest font-bold mb-1">交易次數</div>
                                            <div className="text-lg font-black text-white font-mono">{summary.closed_trades}</div>
                                            <div className="text-[10px] text-text-muted">最多同持 {summary.max_concurrent_positions} 檔</div>
                                        </div>
                                        <div className="bg-black/30 rounded-xl p-3 border border-white/5 text-center">
                                            <div className="text-[10px] text-text-muted uppercase tracking-widest font-bold mb-1">掃描標的</div>
                                            <div className="text-lg font-black text-white font-mono">{summary.symbols_scanned}</div>
                                            <div className="text-[10px] text-text-muted">{summary.trading_days} 個交易日</div>
                                        </div>
                                    </div>
                                </div>

                                {/* Equity Curve */}
                                <div className="bg-black/20 rounded-xl p-4 border border-white/5 h-[280px]">
                                    <PerformanceChart
                                        data={result.equity_curve}
                                        totalProfitPct={summary.total_return_pct}
                                    />
                                </div>

                                {/* Symbol Stats */}
                                {result.symbol_stats.length > 0 && (
                                    <div>
                                        <h4 className="text-sm font-black uppercase tracking-widest text-text-muted mb-3 flex items-center gap-2">
                                            <Trophy className="w-4 h-4 text-yellow-400" /> 標的績效排行
                                        </h4>
                                        <div className="flex flex-wrap gap-2">
                                            {result.symbol_stats.map((s, i) => (
                                                <div key={s.symbol} className={`bg-black/30 rounded-xl px-4 py-3 border flex items-center gap-3 ${
                                                    i === 0 ? 'border-yellow-400/40' :
                                                    s.total_pnl_pct > 0 ? 'border-success/20' : 'border-danger/20'
                                                }`}>
                                                    <div>
                                                        <div className="flex items-center gap-1">
                                                            <span className="text-xs font-black">{s.symbol}</span>
                                                            {i === 0 && <Trophy className="w-3 h-3 text-yellow-400" />}
                                                        </div>
                                                        <div className="text-[10px] text-text-muted">{s.name}</div>
                                                    </div>
                                                    <div className="text-right">
                                                        <div className={`text-sm font-black font-mono flex items-center gap-1 ${profitColor(s.total_pnl_pct)}`}>
                                                            {s.total_pnl_pct > 0
                                                                ? <TrendingUp className="w-3 h-3" />
                                                                : <TrendingDown className="w-3 h-3" />}
                                                            {s.total_pnl_pct > 0 ? '+' : ''}{s.total_pnl_pct.toFixed(2)}%
                                                        </div>
                                                        <div className="text-[10px] text-text-muted">{s.trades}次 · 勝{s.win_rate.toFixed(0)}%</div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Trade Log */}
                                <div className="border border-white/5 rounded-xl overflow-hidden">
                                    <button
                                        onClick={() => setIsTradesExpanded(!isTradesExpanded)}
                                        className="w-full flex justify-between items-center p-4 hover:bg-white/5 transition-colors"
                                    >
                                        <span className="text-sm font-black uppercase tracking-widest">完整交易記錄</span>
                                        <div className="flex items-center gap-2">
                                            <span className="text-xs text-text-muted">{result.trades.length} 筆</span>
                                            {isTradesExpanded ? <ChevronUp className="w-4 h-4 text-text-muted" /> : <ChevronDown className="w-4 h-4 text-text-muted" />}
                                        </div>
                                    </button>
                                    {isTradesExpanded && (
                                        <div className="overflow-x-auto border-t border-white/5 max-h-[400px] overflow-y-auto">
                                            <table className="w-full text-left text-xs min-w-[750px]">
                                                <thead className="sticky top-0 bg-[#1a2035]">
                                                    <tr className="bg-white/5 text-[10px] font-bold text-text-muted uppercase tracking-widest">
                                                        <th className="px-3 py-2">日期</th>
                                                        <th className="px-3 py-2 text-center">操作</th>
                                                        <th className="px-3 py-2">標的</th>
                                                        <th className="px-3 py-2 text-right">成交價</th>
                                                        <th className="px-3 py-2 text-right">股數</th>
                                                        <th className="px-3 py-2">原因</th>
                                                        <th className="px-3 py-2 text-right">損益%</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-white/5">
                                                    {result.trades.slice().reverse().map((t, i) => (
                                                        <tr key={i} className={`hover:bg-white/5 border-l-2 ${
                                                            t.action === 'BUY' ? 'border-l-success' : 'border-l-danger'
                                                        }`}>
                                                            <td className="px-3 py-2 font-mono text-text-muted">{t.date}</td>
                                                            <td className="px-3 py-2 text-center">
                                                                <span className={`px-1.5 py-0.5 rounded text-[9px] font-black uppercase ${
                                                                    t.action === 'BUY' ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'
                                                                }`}>{t.action === 'BUY' ? '買入' : '賣出'}</span>
                                                            </td>
                                                            <td className="px-3 py-2">
                                                                <span className="font-black">{t.symbol}</span>
                                                                <span className="text-text-muted ml-1 hidden md:inline">{t.name}</span>
                                                            </td>
                                                            <td className="px-3 py-2 text-right font-mono">{t.price.toFixed(2)}</td>
                                                            <td className="px-3 py-2 text-right font-mono">{t.shares.toLocaleString()}</td>
                                                            <td className="px-3 py-2 text-text-muted max-w-[180px] truncate">{t.reason}</td>
                                                            <td className="px-3 py-2 text-right font-mono font-bold">
                                                                {t.pnl_pct !== null ? (
                                                                    <span className={profitColor(t.pnl_pct)}>
                                                                        {t.pnl_pct > 0 ? '+' : ''}{t.pnl_pct.toFixed(2)}%
                                                                    </span>
                                                                ) : '—'}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
