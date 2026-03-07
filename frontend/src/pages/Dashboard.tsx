import { RefreshCw, Bot, Loader2, TrendingUp, ChevronDown, ChevronUp } from 'lucide-react';
import { PerformanceChart } from '../components/charts/PerformanceChart';
import { useState, useEffect } from 'react';
import api from '../api/axiosConfig';

interface PortfolioSummary {
    total_assets: number;
    cash: number;
    total_profit: number;
    total_profit_pct: number;
    equity_curve?: Array<{
        date: string;
        equity: number;
        benchmark: number;
    }>;
}

interface PositionItem {
    stock_id: string;
    name: string;
    shares: number;
    avg_cost: number;
    current_price: number;
    profit: number;
    profit_pct: number;
    stop_loss_price: number | null;
    take_profit_price: number | null;
    status?: '保本啟動' | '追蹤止損中' | '正常';
    break_even_price?: number;
    hold_days?: number;
}

interface TradeRecord {
    timestamp: string;
    action: string;
    stock_id: string;
    stock_name?: string;
    shares: number;
    price: number;
    total_value: number;
    fee: number;
    profit?: number;
    profit_pct?: number;
}

export function Dashboard() {
    // Portfolio States
    const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
    const [positions, setPositions] = useState<PositionItem[]>([]);
    const [trades, setTrades] = useState<TradeRecord[]>([]);
    const [isLoadingPortfolio, setIsLoadingPortfolio] = useState(true);
    const [isTradesExpanded, setIsTradesExpanded] = useState(true);

    const [watchlist] = useState([
        { symbol: '2330', name: '台積電', price: 1040, change: 1.45, rsi: 62, volume: 34500 },
        { symbol: '2317', name: '鴻海', price: 215, change: -0.23, rsi: 48, volume: 89000 },
        { symbol: '2454', name: '聯發科', price: 1280, change: 0.50, rsi: 74, volume: 12000 },
    ]);

    // Market Scan State
    const [scanState, setScanState] = useState({ is_scanning: false, current: 0, total: 0, message: '' });

    const checkScanStatus = async () => {
        try {
            const res = await api.get('/api/simulation/scan/status');
            setScanState(res.data);
            return res.data.is_scanning;
        } catch (e) {
            return false;
        }
    };

    useEffect(() => {
        checkScanStatus();
    }, []);

    useEffect(() => {
        let interval: ReturnType<typeof setInterval>;
        if (scanState.is_scanning) {
            interval = setInterval(async () => {
                const isStillScanning = await checkScanStatus();
                if (!isStillScanning) {
                    refreshAllData();
                }
            }, 1000);
        }
        return () => clearInterval(interval);
    }, [scanState.is_scanning]);


    const handleScan = async () => {
        try {
            const res = await api.post('/api/simulation/run_cycle');
            if (res.status === 200 || res.status === 202) {
                setScanState(prev => ({ ...prev, is_scanning: true, message: '準備啟動全市場掃描...' }));
            }
        } catch (e) {
            alert('啟動失敗，請確認後端是否正在運行中！');
        }
    };

    const handleReset = async () => {
        if (!confirm('確定要重置所有模擬交易紀錄嗎？此動作無法復原！')) return;
        try {
            const res = await api.post('/api/simulation/reset');
            if (res.status === 200) {
                alert('模擬交易庫存與資金已重置！');
                refreshAllData();
            }
        } catch (e) {
            alert('重置失敗！');
        }
    };

    
    const fetchPortfolio = async () => {
        try {
            const res = await api.get('/api/simulation/portfolio');
            setPortfolio(res.data);
        } catch (error) {
            console.error('Failed to fetch portfolio:', error);
        }
    };

    const fetchPositions = async () => {
        try {
            const res = await api.get('/api/simulation/positions');
            setPositions(res.data || []);
        } catch (error) {
            console.error('Failed to fetch positions:', error);
        }
    };

    const fetchTrades = async () => {
        try {
            const res = await api.get('/api/simulation/trades');
            setTrades(res.data || []);
        } catch (error) {
            console.error('Failed to fetch trades:', error);
        }
    };

    const refreshAllData = async () => {
        setIsLoadingPortfolio(true);
        await Promise.all([
            fetchPortfolio(),
            fetchPositions(),
            fetchTrades()
        ]);
        setIsLoadingPortfolio(false);
    };

    useEffect(() => {
        refreshAllData();
        const interval = setInterval(refreshAllData, 30000); // Poll every 30s
        return () => clearInterval(interval);
    }, []);

    // 格式化金錢
    const formatMoney = (val: number) => {
        return new Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD', minimumFractionDigits: 0 }).format(val);
    };

    const cashPct = (portfolio?.total_assets && portfolio.total_assets > 0)
        ? ((portfolio.cash / portfolio.total_assets) * 100).toFixed(1) + '%'
        : '－';

    return (
        <div className="max-w-[1400px] mx-auto px-6 py-6 md:py-8 space-y-6 animate-in fade-in duration-700 pb-12">

            {/* SECTION 1: Top Stats Cards */}
            <div className="panel bg-[#1a2035] flex flex-col md:flex-row items-stretch divide-y md:divide-y-0 md:divide-x divide-white/10">
                <div className="flex-1 p-4 flex items-center gap-4">
                    <div className="w-1.5 h-10 rounded-full bg-brand-primary"></div>
                    <div>
                        <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-1">💰 虛擬總資產</div>
                        <div className="text-2xl font-black text-white font-mono tracking-tighter">
                            {isLoadingPortfolio ? '---' : formatMoney(portfolio?.total_assets || 1000000)}
                        </div>
                    </div>
                </div>

                <div className="flex-1 p-4 flex items-center gap-4">
                    <div className="w-1.5 h-10 rounded-full bg-text-muted"></div>
                    <div>
                        <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-1">💵 可用現金</div>
                        <div className="text-2xl font-black text-white font-mono tracking-tighter">
                            {isLoadingPortfolio ? '---' : formatMoney(portfolio?.cash || 0)}
                        </div>
                        <div className="text-[10px] text-text-muted mt-0.5">
                            佔總資產 {cashPct}
                        </div>
                    </div>
                </div>

                <div className="flex-1 p-4 flex items-center gap-4">
                    <div className="w-1.5 h-10 rounded-full bg-success"></div>
                    <div>
                        <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-1">📈 累積總獲利</div>
                        <div className={`text-2xl font-black font-mono tracking-tighter ${(portfolio?.total_profit || 0) >= 0 ? 'text-danger' : 'text-success'}`}>
                            {(portfolio?.total_profit || 0) > 0 ? '+' : ''}{formatMoney(portfolio?.total_profit || 0)}
                        </div>
                    </div>
                </div>

                <div className="flex-1 p-4 flex items-center gap-4">
                    <div className="w-1.5 h-10 rounded-full bg-brand-primary"></div>
                    <div>
                        <div className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-1">🎯 綜合報酬率</div>
                        <div className={`text-2xl font-black font-mono tracking-tighter ${(portfolio?.total_profit_pct || 0) >= 0 ? 'text-danger' : 'text-success'}`}>
                            {(portfolio?.total_profit_pct || 0).toFixed(2)}%
                        </div>
                    </div>
                </div>
            </div>

            {/* SECTION 2: Action Bar */}
            <div className="panel p-3 px-5 flex flex-wrap items-center justify-between gap-4 border-brand-primary/20 bg-brand-primary/5">
                <div className="flex flex-wrap items-center gap-4">
                    <button onClick={refreshAllData} className="btn btn-secondary gap-2 px-4 py-2 text-sm">
                        <RefreshCw className={`w-4 h-4 ${isLoadingPortfolio ? 'animate-spin' : ''}`} /> 刷新數據
                    </button>
                    
                    {scanState.is_scanning ? (
                        <div className="flex items-center gap-3 bg-black/40 px-4 py-2 rounded-xl border border-brand-primary/30 min-w-[350px]">
                            <Loader2 className="w-4 h-4 text-brand-primary animate-spin shrink-0" />
                            <div className="flex flex-col w-full">
                                <div className="flex justify-between text-xs mb-1">
                                    <span className="text-brand-primary font-bold">{scanState.message}</span>
                                    <span className="text-text-muted">{scanState.total > 0 ? `${Math.round((scanState.current / scanState.total) * 100)}%` : ''}</span>
                                </div>
                                {scanState.total > 0 && (
                                    <div className="h-1 flex-1 bg-white/10 rounded-full overflow-hidden w-full">
                                        <div 
                                            className="h-full bg-brand-primary rounded-full transition-all duration-500 shadow-[0_0_10px_#6366f1]"
                                            style={{ width: `${(scanState.current / scanState.total) * 100}%` }}
                                        ></div>
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        <div className="flex items-center gap-3">
                            <button 
                                onClick={handleScan}
                                className="btn btn-primary glow-purple gap-2 px-6 py-2 bg-gradient-to-r from-brand-primary to-indigo-600 hover:scale-105 text-sm"
                            >
                                <Bot className="w-4 h-4" /> 執行 AI 交易分析 (全市場)
                            </button>
                            <span className="text-xs text-text-muted whitespace-nowrap hidden md:inline-block">
                                AI將自動掃描全市場2,000+支股票，篩選最佳買賣時機
                            </span>
                        </div>
                    )}
                </div>

                <button onClick={handleReset} className="btn btn-danger gap-2 px-4 py-2 text-sm">
                    <RefreshCw className="w-4 h-4" /> 重置模擬
                </button>
            </div>

            {/* SECTION 3: Split View 6:4 */}
            <div className="flex flex-col lg:flex-row gap-6 items-stretch">
                {/* Left: Performance Chart */}
                <div className="w-full lg:w-[60%] panel p-6 h-[320px] flex flex-col">
                    <div className="flex-1 w-full h-full relative">
                        {!isLoadingPortfolio ? (
                            <PerformanceChart 
                                data={portfolio?.equity_curve || []} 
                                totalProfitPct={portfolio?.total_profit_pct || 0}
                            />
                        ) : (
                            <div className="h-full flex flex-col items-center justify-center text-text-muted gap-3">
                                 <Loader2 className="w-10 h-10 animate-spin text-brand-primary" />
                                 <span className="font-bold tracking-widest text-xs uppercase">分析引擎啟動中...</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right: AI Logs & Watchlist */}
                <div className="w-full lg:flex-1 flex flex-col gap-4">
                    {/* Top Right: AI Logs */}
                    <div className="panel p-4 flex-1 flex flex-col min-h-0">
                        <div className="flex justify-between items-center mb-3">
                            <h3 className="text-sm font-black uppercase tracking-widest flex items-center gap-2">
                                <Bot className="w-4 h-4 text-brand-primary" /> AI 決策日誌
                            </h3>
                            <span className="bg-brand-primary text-white text-[10px] px-2 py-0.5 rounded-full font-bold">
                                {trades.length}
                            </span>
                        </div>
                        <div className="flex-1 overflow-y-auto pr-1 space-y-2">
                            {trades.length === 0 ? (
                                <div className="h-full flex flex-col items-center justify-center py-4 text-text-muted">
                                    <Bot className="w-8 h-8 opacity-20 mb-2" />
                                    <span className="text-sm font-bold">等待AI執行分析...</span>
                                    <span className="text-[10px] opacity-70">點擊執行AI交易分析開始</span>
                                </div>
                            ) : (
                                trades.slice().reverse().slice(0, 20).map((t, i) => (
                                    <div key={i} className="flex gap-3 p-2.5 bg-white/5 rounded-xl border border-white/5 hover:bg-white/10 transition-colors">
                                        <div className="flex flex-col items-center shrink-0">
                                            <span className="text-[10px] font-mono text-text-muted">{new Date(t.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                                            <div className={`w-1 h-full mt-1 rounded-full ${
                                                t.action === 'BUY' ? 'bg-success' : t.action === 'SELL' ? 'bg-danger' : 'bg-gray-500'
                                            }`}></div>
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex justify-between mb-0.5">
                                                <span className="text-sm font-black text-text-main">{t.stock_id}</span>
                                                <span className={`text-[10px] font-black px-1.5 py-0.5 rounded ${
                                                    t.action === 'BUY' ? 'bg-success/20 text-success' : 
                                                    t.action === 'SELL' ? 'bg-danger/20 text-danger' : 'bg-white/10 text-text-muted'
                                                }`}>
                                                    {t.action}
                                                </span>
                                            </div>
                                            <p className="text-xs text-text-muted truncate">
                                                執行{t.action === 'BUY' ? '買入' : '賣出'} {t.shares} 股，成交價 {t.price.toFixed(2)}
                                            </p>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Bottom Right: Watchlist & RSI */}
                    <div className="panel p-4 flex-1 flex flex-col min-h-0">
                        <h3 className="text-sm font-black uppercase tracking-widest flex items-center gap-2 mb-3">
                            <TrendingUp className="w-4 h-4 text-brand-primary" /> 觀察清單 & 技術指標
                        </h3>
                        <div className="flex-1 overflow-y-auto pr-1 space-y-2">
                            {watchlist.map((item, i) => (
                                <div key={i} className="flex items-center justify-between p-2 hover:bg-white/5 rounded-lg transition-colors">
                                    <div className="flex flex-col w-[25%] shrink-0">
                                        <span className="text-xs font-black text-text-main">{item.symbol}</span>
                                        <span className="text-[10px] text-text-muted truncate">{item.name}</span>
                                    </div>
                                    <div className="text-right flex flex-col w-[25%] shrink-0">
                                        <span className="text-xs font-mono font-bold">{item.price.toLocaleString()}</span>
                                        <span className={`text-[10px] font-mono font-bold ${item.change >= 0 ? 'text-danger' : 'text-success'}`}>
                                            {item.change >= 0 ? '+' : ''}{item.change}%
                                        </span>
                                    </div>
                                    <div className="text-right flex flex-col w-[25%] shrink-0 pr-2">
                                        <span className="text-xs font-mono font-bold">{(item.volume || 0).toLocaleString()}</span>
                                        <span className="text-[10px] text-text-muted">張</span>
                                    </div>
                                    <div className="flex flex-col items-end gap-1 w-[25%] shrink-0">
                                        <span className={`text-[9px] font-black px-1.5 py-0.5 rounded leading-none ${
                                            (item.rsi || 50) > 70 ? 'bg-danger/20 text-danger' : 
                                            (item.rsi || 50) < 30 ? 'bg-success/20 text-success' : 'bg-white/10 text-text-muted'
                                        }`}>
                                            {(item.rsi || 50) > 70 ? '超買' : (item.rsi || 50) < 30 ? '超賣' : '正常'}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* SECTION 4: Positions Table */}
            <div className="panel overflow-hidden">
                <div className="p-6 border-b border-card-border flex justify-between items-center">
                    <h3 className="text-lg font-black tracking-tight flex items-center gap-2">
                        <span className="bg-brand-primary w-1 h-5 rounded-full inline-block"></span>
                        當前持倉庫存
                    </h3>
                </div>
                <div className="overflow-x-auto w-full">
                    <table className="w-full text-left table-fixed min-w-[1000px]">
                        <thead>
                            <tr className="bg-white/5 text-[10px] font-bold text-text-muted uppercase tracking-widest">
                                <th className="px-4 py-3 w-[12%]">標的</th>
                                <th className="px-4 py-3 w-[8%] text-right">持有股數</th>
                                <th className="px-4 py-3 w-[8%] text-right">均價</th>
                                <th className="px-4 py-3 w-[8%] text-right">現價</th>
                                <th className="px-4 py-3 w-[10%] text-right">防護網(止損)</th>
                                <th className="px-4 py-3 w-[9%] text-right">止盈價</th>
                                <th className="px-4 py-3 w-[9%] text-right">保本價</th>
                                <th className="px-4 py-3 w-[10%] text-right">未實現損益</th>
                                <th className="px-4 py-3 w-[8%] text-right">損益%</th>
                                <th className="px-4 py-3 w-[8%] text-right">持倉天數</th>
                                <th className="px-4 py-3 w-[10%] text-center">狀態</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                            {isLoadingPortfolio ? (
                                <tr><td colSpan={11} className="text-center py-6 text-text-muted italic"><Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" /> 帳戶數據對接中...</td></tr>
                            ) : positions.length === 0 ? (
                                <tr>
                                    <td colSpan={11} className="text-center py-6 text-text-muted text-sm border-0">
                                        <div className="flex items-center justify-center gap-2 opacity-50">
                                            <Bot className="w-4 h-4" />
                                            <span className="font-bold tracking-widest uppercase">目前無任何倉位，等待 AI 建立部位</span>
                                        </div>
                                    </td>
                                </tr>
                            ) : (
                                positions.map((p, idx) => (
                                    <tr key={`${p.stock_id}-${idx}`} className="hover:bg-brand-primary/5 transition-colors group">
                                        <td className="px-4 py-4">
                                            <div className="font-black text-text-main group-hover:text-brand-primary transition-colors text-sm">{p.stock_id}</div>
                                            <div className="text-[10px] text-text-muted font-bold truncate">{p.name || '台股標的'}</div>
                                        </td>
                                        <td className="px-4 py-4 text-right font-mono text-sm font-bold">{(p.shares || 0).toLocaleString()}</td>
                                        <td className="px-4 py-4 text-right font-mono text-sm">{(p.avg_cost || 0).toFixed(2)}</td>
                                        <td className="px-4 py-4 text-right font-mono text-sm font-black text-text-main">{(p.current_price || 0).toFixed(2)}</td>
                                        <td className="px-4 py-4 text-right font-mono text-xs text-danger font-bold">{p.stop_loss_price?.toFixed(2) || '---'}</td>
                                        <td className="px-4 py-4 text-right font-mono text-xs text-brand-primary font-bold">{p.take_profit_price?.toFixed(2) || '---'}</td>
                                        <td className="px-4 py-4 text-right font-mono text-xs font-bold text-text-muted">{p.break_even_price?.toFixed(2) || '---'}</td>
                                        <td className="px-4 py-4 text-right font-mono">
                                            <div className={`text-sm font-black ${(p.profit || 0) >= 0 ? 'text-danger' : 'text-success'}`}>
                                                {(p.profit || 0) > 0 ? '+' : ''}{formatMoney(p.profit || 0)}
                                            </div>
                                        </td>
                                        <td className="px-4 py-4 text-right font-mono text-sm font-bold">
                                            <span className={`${(p.profit_pct || 0) >= 0 ? 'text-danger' : 'text-success'}`}>
                                                {(p.profit_pct || 0) > 0 ? '+' : ''}{(p.profit_pct || 0).toFixed(2)}%
                                            </span>
                                        </td>
                                        <td className="px-4 py-4 text-right font-mono text-xs text-text-muted">{p.hold_days !== undefined ? `${p.hold_days}天` : '---'}</td>
                                        <td className="px-4 py-4 text-center">
                                            <span className={`inline-block px-2 py-1 rounded-full text-[9px] font-black uppercase tracking-widest leading-none ${
                                                p.profit_pct > 2 ? 'bg-brand-primary/20 text-brand-primary' :
                                                p.profit_pct < -2 ? 'bg-danger/20 text-danger' : 'bg-white/10 text-text-muted'
                                            }`}>
                                                {p.status || (p.profit_pct > 5 ? '追蹤止損中' : p.profit_pct > 2 ? '保本啟動' : '正常')}
                                            </span>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* SECTION 5: Trade History Collapsible */}
            <div className="panel overflow-hidden mb-6">
                <button 
                    onClick={() => setIsTradesExpanded(!isTradesExpanded)}
                    className="w-full p-6 flex justify-between items-center hover:bg-white/5 transition-colors"
                >
                    <h3 className="text-lg font-black tracking-tight flex items-center gap-2">
                        <span className="bg-text-muted w-1 h-5 rounded-full inline-block"></span>
                        歷史交易紀錄
                    </h3>
                    <div className="flex items-center gap-3">
                        <span className="text-xs text-text-muted font-bold">近期 {trades.length} 筆</span>
                        {isTradesExpanded ? <ChevronUp className="w-5 h-5 text-text-muted" /> : <ChevronDown className="w-5 h-5 text-text-muted" />}
                    </div>
                </button>
                
                {isTradesExpanded && (
                    <div className="overflow-x-auto w-full border-t border-card-border animate-in slide-in-from-top duration-300">
                        <table className="w-full text-left table-fixed min-w-[1000px]">
                            <thead>
                                <tr className="bg-white/5 text-[10px] font-bold text-text-muted uppercase tracking-widest">
                                    <th className="px-4 py-3 w-[8%]">時間</th>
                                    <th className="px-4 py-3 w-[8%] text-center">操作</th>
                                    <th className="px-4 py-3 w-[10%]">股票代碼</th>
                                    <th className="px-4 py-3 w-[12%]">股票名稱</th>
                                    <th className="px-4 py-3 w-[10%] text-right">股數</th>
                                    <th className="px-4 py-3 w-[10%] text-right">成交價</th>
                                    <th className="px-4 py-3 w-[12%] text-right">總額</th>
                                    <th className="px-4 py-3 w-[10%] text-right">手續費</th>
                                    <th className="px-4 py-3 w-[10%] text-right">損益</th>
                                    <th className="px-4 py-3 w-[10%] text-right">損益%</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {trades.length === 0 ? (
                                    <tr><td colSpan={10} className="text-center py-0 h-[80px] text-text-muted italic text-sm border-0">暫無交易紀錄</td></tr>
                                ) : (
                                    trades.slice().reverse().map((t, i) => (
                                        <tr key={i} className={`group hover:bg-white/5 transition-colors border-l-4 ${
                                            t.action === 'BUY' ? 'border-l-success' : 'border-l-danger'
                                        }`}>
                                            <td className="px-4 py-3 text-xs text-text-muted font-mono">
                                                {t.timestamp ? new Date(t.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '--:--'}
                                            </td>
                                            <td className="px-4 py-3 text-center">
                                                <span className={`px-2 py-1 rounded text-[9px] font-black uppercase tracking-widest ${
                                                    t.action === 'BUY' ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'
                                                }`}>
                                                    {t.action === 'BUY' ? '買入' : '賣出'}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 font-black text-text-main text-sm">{t.stock_id}</td>
                                            <td className="px-4 py-3 text-[10px] text-text-muted truncate">{t.stock_name || '台股標的'}</td>
                                            <td className="px-4 py-3 text-right font-mono text-sm">{(t.shares || 0).toLocaleString()}</td>
                                            <td className="px-4 py-3 text-right font-mono text-sm font-bold">{(t.price || 0).toFixed(2)}</td>
                                            <td className="px-4 py-3 text-right font-mono text-sm font-black text-text-main">{formatMoney(t.total_value || 0)}</td>
                                            <td className="px-4 py-3 text-right font-mono text-[10px] text-text-muted">{formatMoney(t.fee || 0)}</td>
                                            <td className="px-4 py-3 text-right font-mono text-sm font-bold">
                                                {t.profit !== undefined ? (
                                                    <span className={t.profit >= 0 ? 'text-danger' : 'text-success'}>
                                                        {t.profit > 0 ? '+' : ''}{formatMoney(t.profit)}
                                                    </span>
                                                ) : '---'}
                                            </td>
                                            <td className="px-4 py-3 text-right font-mono text-sm font-bold">
                                                {t.profit_pct !== undefined ? (
                                                    <span className={t.profit_pct >= 0 ? 'text-danger' : 'text-success'}>
                                                        {t.profit_pct > 0 ? '+' : ''}{(t.profit_pct).toFixed(2)}%
                                                    </span>
                                                ) : '---'}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
