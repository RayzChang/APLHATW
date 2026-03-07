import { Play, RefreshCw, Upload, Download, Bot, Loader2 } from 'lucide-react';
import { PerformanceChart } from '../components/charts/PerformanceChart';
import { useState, useEffect } from 'react';

const MOCK_DATA = [
    { date: '2023-11-01', equity: 1000000, benchmark: 100 },
    { date: '2023-11-02', equity: 1005000, benchmark: 100.2 },
    { date: '2023-11-03', equity: 1012000, benchmark: 101.5 },
    { date: '2023-11-06', equity: 1008000, benchmark: 101.0 },
    { date: '2023-11-07', equity: 1025000, benchmark: 102.1 },
    { date: '2023-11-08', equity: 1032000, benchmark: 103.0 },
];

interface WatchlistItem {
    symbol: string;
    name: string;
    close: number;
    change_pct: number;
    recommendation: string;
    explanation: string[];
}

interface AgentDecision {
    action: "BUY" | "SELL" | "HOLD";
    confidence: number;
    reasoning: string;
    take_profit_price: number | null;
    stop_loss_price: number | null;
    position_size_pct: number;
}

interface AgentResult {
    symbol: string;
    name: string;
    current_price: number;
    decision: AgentDecision;
}

interface PortfolioSummary {
    total_assets: number;
    available_cash: number;
    total_profit: number;
    total_profit_pct: number;
}

interface PositionItem {
    id: number;
    symbol: string;
    name: string;
    amount: number;
    entry_price: number;
    current_price: number;
    profit: number;
    profit_pct: number;
    stop_loss_price: number | null;
    take_profit_price: number | null;
}

export function Dashboard() {
    const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
    const [watchlistProgress, setWatchlistProgress] = useState({ current: 0, total: 0 });
    const [isLoadingWatchlist, setIsLoadingWatchlist] = useState(true);
    
    // Portfolio States
    const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
    const [positions, setPositions] = useState<PositionItem[]>([]);
    const [isLoadingPortfolio, setIsLoadingPortfolio] = useState(true);

    // AI Agent States
    const [isAgentAnalyzing, setIsAgentAnalyzing] = useState(false);
    const [agentResult, setAgentResult] = useState<AgentResult | null>(null);

    // Market Scan State
    const [scanState, setScanState] = useState({ is_scanning: false, current: 0, total: 0, message: '' });

    const checkScanStatus = async () => {
        try {
            const res = await fetch('/api/simulation/scan/status');
            if (res.ok) {
                const data = await res.json();
                setScanState(data);
                return data.is_scanning;
            }
        } catch (e) {}
        return false;
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
                    fetchPortfolio();
                }
            }, 1000);
        }
        return () => clearInterval(interval);
    }, [scanState.is_scanning]);

    const executeAgentAnalysis = async () => {
        if (watchlist.length === 0) return;
        setIsAgentAnalyzing(true);
        try {
            const targetSymbol = watchlist[0].symbol; // 針對清單第一檔進行深度分析
            const authHeader = 'Basic ' + btoa('admin:changeme');
            const res = await fetch('/api/analyze/agent', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': authHeader
                },
                body: JSON.stringify({ symbols: [targetSymbol] })
            });
            if (res.ok) {
                const data = await res.json();
                setAgentResult(data);
            }
        } catch (error) {
            console.error('Failed to execute AI analysis:', error);
        } finally {
            setIsAgentAnalyzing(false);
        }
    };

    const handleScan = async () => {
        try {
            const authHeader = 'Basic ' + btoa('admin:changeme');
            const res = await fetch('/api/simulation/scan', { 
                method: 'POST',
                headers: { 'Authorization': authHeader }
            });
            if (res.ok) {
                const data = await res.json();
                if (data.ok) {
                    setScanState(prev => ({ ...prev, is_scanning: true, message: '準備啟動全市場掃描...' }));
                } else {
                    alert(data.message);
                }
            } else {
                alert('啟動失敗，請確認後端是否正在運行中！');
            }
        } catch (e) {
            console.error(e);
            alert('無法連線到伺服器，請確保 python launcher.py 正在執行中！');
        }
    };

    const handleReset = async () => {
        if (!confirm('確定要重置所有庫存與虛擬資金嗎？此動作無法復原！')) return;
        try {
            const authHeader = 'Basic ' + btoa('admin:changeme');
            const res = await fetch('/api/simulation/reset', { 
                method: 'POST',
                headers: { 'Authorization': authHeader }
            });
            if (res.ok) {
                alert('模擬交易庫存與資金已重置！');
                fetchPortfolio();
            } else {
                alert('重置失敗！');
            }
        } catch (e) {
            console.error(e);
            alert('無法連線到伺服器，請確保 python launcher.py 正在執行中！');
        }
    };


    const fetchWatchlist = async () => {
        setIsLoadingWatchlist(true);
        setWatchlist([]);
        setWatchlistProgress({ current: 0, total: 0 });
        try {
            const authHeader = 'Basic ' + btoa('admin:changeme');
            
            // 1. 取得清單代號
            const listRes = await fetch('/api/watchlist', {
                headers: { 'Authorization': authHeader }
            });
            if (!listRes.ok) return;
            const listData = await listRes.json();
            const symbols: string[] = listData.symbols || [];
            
            setWatchlistProgress({ current: 0, total: symbols.length });
            
            if (symbols.length === 0) {
                setIsLoadingWatchlist(false);
                return;
            }
            
            // 2. 逐檔分析以更新進度條
            const updatedResults: WatchlistItem[] = [];
            for (let i = 0; i < symbols.length; i++) {
                try {
                    const res = await fetch('/api/analyze', {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'Authorization': authHeader 
                        },
                        body: JSON.stringify({ symbols: [symbols[i]] })
                    });
                    if (res.ok) {
                        const data = await res.json();
                        if (data.results && data.results.length > 0) {
                            updatedResults.push(data.results[0]);
                            setWatchlist([...updatedResults]); // 即時更新畫面
                        }
                    }
                } catch (e) {
                    console.error('分析失敗', symbols[i], e);
                }
                setWatchlistProgress({ current: i + 1, total: symbols.length });
            }
        } catch (error) {
            console.error('Failed to fetch watchlist:', error);
        } finally {
            setIsLoadingWatchlist(false);
        }
    };
    
    const fetchPortfolio = async () => {
        setIsLoadingPortfolio(true);
        try {
            const authHeader = 'Basic ' + btoa('admin:changeme');
            const headers = { 'Authorization': authHeader };
            const summaryRes = await fetch('/api/portfolio/summary', { headers });
            if (summaryRes.ok) setPortfolio(await summaryRes.json());
            
            const posRes = await fetch('/api/portfolio/positions', { headers });
            if (posRes.ok) {
                const data = await posRes.json();
                setPositions(data.positions || []);
            }
        } catch(error) {
            console.error('Failed to fetch portfolio', error);
        } finally {
            setIsLoadingPortfolio(false);
        }
    };

    useEffect(() => {
        fetchWatchlist();
        fetchPortfolio();
    }, []);

    // 格式化金錢
    const formatMoney = (val: number) => {
        return new Intl.NumberFormat('zh-TW', { style: 'currency', currency: 'TWD', minimumFractionDigits: 0 }).format(val);
    };

    return (
        <div className="max-w-[1600px] mx-auto p-6">

            {/* Top Stats Row */}
            <div className="grid grid-cols-4 gap-4">
                <div className="panel p-5 border-l-4 border-brand-500">
                    <h3 className="text-gray-400 text-sm font-medium mb-1">虛擬總資產</h3>
                    <div className="text-2xl font-bold text-white mb-2">
                        {isLoadingPortfolio ? '...' : formatMoney(portfolio?.total_assets || 0)}
                    </div>
                </div>
                
                <div className="panel p-5">
                    <h3 className="text-gray-400 text-sm font-medium mb-1">可用現金</h3>
                    <div className="text-2xl font-bold text-white mb-2">
                        {isLoadingPortfolio ? '...' : formatMoney(portfolio?.available_cash || 0)}
                    </div>
                </div>
                
                <div className="panel p-5">
                    <h3 className="text-gray-400 text-sm font-medium mb-1">累積總獲利</h3>
                    <div className={`text-2xl font-bold mb-2 ${portfolio && portfolio.total_profit >= 0 ? 'text-success' : 'text-danger'}`}>
                        {isLoadingPortfolio ? '...' : `${portfolio && portfolio.total_profit > 0 ? '+' : ''}${formatMoney(portfolio?.total_profit || 0)}`}
                    </div>
                </div>
                
                <div className="panel p-5">
                    <h3 className="text-gray-400 text-sm font-medium mb-1">總報酬率</h3>
                    <div className={`text-2xl font-bold mb-2 ${portfolio && portfolio.total_profit_pct >= 0 ? 'text-success' : 'text-danger'}`}>
                        {isLoadingPortfolio ? '...' : `${portfolio && portfolio.total_profit_pct > 0 ? '+' : ''}${portfolio?.total_profit_pct.toFixed(2) || 0}%`}
                    </div>
                </div>
            </div>            {/* Top Cards Indicator */}
            {/* <TopCards
                totalAssets={1032000}
                availableCash={820000}
                holdingValue={212000}
                totalTrades={12}
                winRate={66.7}
                initialAssets={1000000}
            /> */}

            {/* Action Bar */}
            <div className="panel p-4 mb-6 flex items-center justify-between">
                <div className="flex gap-3">
                    <button 
                        onClick={executeAgentAnalysis}
                        disabled={isAgentAnalyzing || watchlist.length === 0}
                        className="btn btn-primary bg-indigo-600 hover:bg-indigo-500 gap-2 disabled:opacity-50"
                    >
                        {isAgentAnalyzing ? (
                            <><Loader2 className="w-4 h-4 animate-spin" /> 正在進行深度分析...</>
                        ) : (
                            <><Bot className="w-4 h-4" /> 執行 AI 交易分析</>
                        )}
                    </button>
                    <button onClick={() => { fetchWatchlist(); fetchPortfolio(); }} className="btn btn-secondary border border-white/10 gap-2">
                        <RefreshCw className="w-4 h-4" /> 更新報價
                    </button>
                    {scanState.is_scanning ? (
                        <div className="flex items-center gap-3 bg-brand-900/30 px-3 py-1.5 rounded-lg border border-brand-500/30 min-w-[200px]">
                            <Loader2 className="w-4 h-4 text-brand-400 animate-spin shrink-0" />
                            <div className="flex flex-col w-full">
                                <div className="flex justify-between text-xs text-brand-300 mb-1">
                                    <span className="truncate max-w-[150px]">{scanState.message}</span>
                                    <span>{scanState.total > 0 ? `${Math.round((scanState.current / scanState.total) * 100)}%` : ''}</span>
                                </div>
                                {scanState.total > 0 && (
                                    <div className="h-1 bg-black/50 rounded-full overflow-hidden w-full">
                                        <div 
                                            className="h-full bg-brand-500 rounded-full transition-all duration-300"
                                            style={{ width: `${(scanState.current / scanState.total) * 100}%` }}
                                        ></div>
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        <button onClick={handleScan} className="btn bg-brand-600/20 text-brand-400 hover:bg-brand-600/30 gap-2 shrink-0">
                            <Play className="w-4 h-4 fill-current" /> 手動觸發全市場掃描
                        </button>
                    )}
                </div>

                <div className="flex gap-3">
                    <button onClick={() => alert('尚未實作：匯出功能')} className="btn btn-secondary text-gray-400 hover:text-white gap-2">
                        <Download className="w-4 h-4" /> 匯出
                    </button>
                    <button onClick={() => alert('尚未實作：匯入功能')} className="btn btn-secondary text-gray-400 hover:text-white gap-2">
                        <Upload className="w-4 h-4 text-warning" /> 匯入
                    </button>
                    <button onClick={handleReset} className="btn bg-cyan-900/40 text-cyan-400 hover:bg-cyan-900/60 gap-2">
                        <RefreshCw className="w-4 h-4" /> 重置模擬
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Left Column (Chart + Positions) */}
                <div className="lg:col-span-2 space-y-6">
                    <PerformanceChart data={MOCK_DATA} />

                    <div className="panel p-5">
                        <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                            <span>📦</span> 現在庫存明細
                        </h3>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm">
                                <thead>
                                    <tr className="border-b border-white/5 text-gray-400">
                                        <th className="pb-3 font-medium">標的</th>
                                        <th className="pb-3 font-medium text-right">持有股數</th>
                                        <th className="pb-3 font-medium text-right">均價</th>
                                        <th className="pb-3 font-medium text-right">現價</th>
                                        <th className="pb-3 font-medium text-right">防護網</th>
                                        <th className="pb-3 font-medium text-right">未實現損益</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {isLoadingPortfolio ? (
                                        <tr><td colSpan={6} className="text-center py-4 text-gray-500">載入中...</td></tr>
                                    ) : positions.length === 0 ? (
                                        <tr><td colSpan={6} className="text-center py-4 text-gray-500">目前無任何庫存</td></tr>
                                    ) : (
                                        positions.map(p => (
                                            <tr key={p.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                                                <td className="py-3">
                                                    <div className="font-bold text-white">{p.symbol}</div>
                                                    <div className="text-xs text-gray-500">{p.name}</div>
                                                </td>
                                                <td className="py-3 text-right font-mono text-gray-300">{p.amount}</td>
                                                <td className="py-3 text-right font-mono text-gray-300">{p.entry_price.toFixed(2)}</td>
                                                <td className="py-3 text-right font-mono text-gray-300">{p.current_price.toFixed(2)}</td>
                                                <td className="py-3 text-right">
                                                    <div className="text-xs text-danger font-mono">SL: {p.stop_loss_price || '-'}</div>
                                                    <div className="text-xs text-success font-mono">TP: {p.take_profit_price || '-'}</div>
                                                </td>
                                                <td className={`py-3 text-right font-mono font-bold ${p.profit >= 0 ? 'text-success' : 'text-danger'}`}>
                                                    <div>{p.profit > 0 ? '+' : ''}{formatMoney(p.profit)}</div>
                                                    <div className="text-xs">{p.profit_pct > 0 ? '+' : ''}{p.profit_pct.toFixed(2)}%</div>
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div className="panel p-5">
                        <h3 className="text-lg font-bold text-white flex items-center gap-2 mb-4">
                            <span className="text-gray-400">📋</span> 歷史交易紀錄
                        </h3>
                        <div className="text-center py-8 text-gray-500 bg-black/20 rounded-lg border border-dashed border-white/10">
                            暫無交易紀錄
                        </div>
                    </div>
                </div>

                {/* Right Column (Watchlist / AI Logs) */}
                <div className="space-y-6">
                    <div className="panel p-5">
                        <h3 className="text-lg font-bold text-white flex items-center gap-2 justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <span className="text-cyan-400">📊</span> 觀察清單 · 技術指標
                            </div>
                            <div className="flex items-center gap-2">
                                <button 
                                    onClick={fetchWatchlist}
                                    className="p-1 hover:bg-white/10 rounded transition-colors text-gray-400 hover:text-white"
                                    disabled={isLoadingWatchlist}
                                >
                                    <RefreshCw className={`w-4 h-4 ${isLoadingWatchlist ? 'animate-spin' : ''}`} />
                                </button>
                                <span className="bg-white/10 text-xs px-2 py-0.5 rounded-full">{watchlist.length}</span>
                            </div>
                        </h3>

                        <div className="space-y-3 min-h-[150px]">
                            {isLoadingWatchlist && watchlistProgress.total > 0 && (
                                <div className="mb-4">
                                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                                        <span>正在讀取台股資料... ({watchlistProgress.current}/{watchlistProgress.total})</span>
                                        <span>{Math.round((watchlistProgress.current / watchlistProgress.total) * 100) || 0}%</span>
                                    </div>
                                    <div className="h-1.5 bg-black/50 rounded-full overflow-hidden">
                                        <div 
                                            className="h-full bg-cyan-500 rounded-full transition-all duration-300"
                                            style={{ width: `${(watchlistProgress.current / watchlistProgress.total) * 100}%` }}
                                        ></div>
                                    </div>
                                </div>
                            )}

                            {isLoadingWatchlist && watchlistProgress.total === 0 ? (
                                <div className="flex flex-col items-center justify-center h-full text-gray-400 py-8">
                                    <Loader2 className="w-8 h-8 animate-spin mb-2 text-brand-500" />
                                    <span className="text-sm">正在取得自選清單...</span>
                                </div>
                            ) : watchlist.length === 0 && !isLoadingWatchlist ? (
                                <div className="text-center text-gray-500 py-8">
                                    清單為空
                                </div>
                            ) : (
                                watchlist.map((item) => {
                                    const isUp = item.change_pct > 0;
                                    const isDown = item.change_pct < 0;
                                    
                                    let dotColor = 'bg-gray-500';
                                    if (item.recommendation.includes('買')) dotColor = 'bg-success';
                                    else if (item.recommendation.includes('賣')) dotColor = 'bg-danger';

                                    return (
                                        <div key={item.symbol} className="p-3 bg-black/20 border border-white/5 rounded-lg hover:border-white/10 transition-colors cursor-pointer group">
                                            <div className="flex justify-between items-center mb-2">
                                                <span className="font-bold text-white group-hover:text-brand-400 transition-colors">
                                                    {item.name} ({item.symbol})
                                                </span>
                                                <div className="text-right">
                                                    <span className={`block font-mono ${isUp ? 'text-success' : isDown ? 'text-danger' : 'text-white'}`}>
                                                        {item.close.toLocaleString()}
                                                    </span>
                                                    <span className={`text-xs ${isUp ? 'text-success' : isDown ? 'text-danger' : 'text-gray-400'}`}>
                                                        {isUp ? '+' : ''}{item.change_pct.toFixed(2)}%
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="text-xs text-gray-400 space-y-1">
                                                <p className="flex items-start gap-2">
                                                    <span className={`w-2 h-2 rounded-full mt-1 shrink-0 ${dotColor}`}></span>
                                                    <span className="line-clamp-2 leading-relaxed">
                                                        {item.recommendation}：{item.explanation.slice(0, 2).join(' · ')}
                                                    </span>
                                                </p>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    </div>

                    <div className="panel p-5 flex-1 min-h-[400px] flex flex-col">
                        <h3 className="text-lg font-bold text-white flex items-center gap-2 justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <span className="text-fuchsia-400">🧠</span> AI 決策日誌
                            </div>
                            <span className="bg-brand-600/20 text-brand-400 text-xs px-2 py-0.5 rounded-full">BETA</span>
                        </h3>

                        <div className="flex-1 rounded-lg border border-white/5 bg-black/40 p-4 flex flex-col">
                            {isAgentAnalyzing ? (
                                <div className="flex-1 flex flex-col items-center justify-center text-center h-full space-y-4">
                                    <div className="w-16 h-16 bg-indigo-500/20 rounded-full flex items-center justify-center relative">
                                        <div className="absolute inset-0 rounded-full border-t-2 border-indigo-500 animate-spin"></div>
                                        <Bot className="w-8 h-8 text-indigo-400 animate-pulse" />
                                    </div>
                                    <div className="space-y-1">
                                        <p className="text-white font-medium">四位專家正在激辯中...</p>
                                        <p className="text-sm text-indigo-400">正在分析技術指標、新聞情緒與帳戶風險</p>
                                    </div>
                                </div>
                            ) : agentResult ? (
                                <div className="space-y-4">
                                    <div className="flex justify-between items-center border-b border-white/5 pb-3">
                                        <div>
                                            <span className="text-sm text-gray-400">分析標的</span>
                                            <div className="text-lg font-bold text-white">{agentResult.name} ({agentResult.symbol})</div>
                                        </div>
                                        <div className="text-right">
                                            <span className="text-sm text-gray-400">最終決策</span>
                                            <div className={`text-xl font-black ${
                                                agentResult.decision.action === 'BUY' ? 'text-success' : 
                                                agentResult.decision.action === 'SELL' ? 'text-danger' : 'text-warning'
                                            }`}>
                                                {agentResult.decision.action === 'BUY' ? '建議買進' : 
                                                 agentResult.decision.action === 'SELL' ? '建議賣出' : '持續觀望'}
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div className="bg-white/5 rounded p-3 text-sm">
                                        <span className="text-fuchsia-400 mb-1 block font-bold">💡 首席觀點 & 核心邏輯</span>
                                        <p className="text-gray-300 leading-relaxed">{agentResult.decision.reasoning}</p>
                                    </div>

                                    <div className="grid grid-cols-2 gap-3 mt-4">
                                        <div className="bg-black/30 border border-white/5 rounded p-3">
                                            <div className="text-xs text-gray-500 mb-1">信心水準</div>
                                            <div className="text-white font-mono text-lg">{(agentResult.decision.confidence * 100).toFixed(0)}%</div>
                                        </div>
                                        <div className="bg-black/30 border border-white/5 rounded p-3">
                                            <div className="text-xs text-gray-500 mb-1">建議資金配置</div>
                                            <div className="text-white font-mono text-lg">{agentResult.decision.position_size_pct}%</div>
                                        </div>
                                        <div className="bg-black/30 border border-white/5 rounded p-3">
                                            <div className="text-xs text-gray-500 mb-1">停利目標價</div>
                                            <div className="text-success font-mono text-lg">{agentResult.decision.take_profit_price || '-'}</div>
                                        </div>
                                        <div className="bg-black/30 border border-white/5 rounded p-3">
                                            <div className="text-xs text-gray-500 mb-1">建議停損價</div>
                                            <div className="text-danger font-mono text-lg">{agentResult.decision.stop_loss_price || '-'}</div>
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="flex-1 flex flex-col items-center justify-center text-center h-full">
                                    <div className="w-16 h-16 bg-indigo-500/20 rounded-full flex items-center justify-center mb-4">
                                        <Bot className="w-8 h-8 text-indigo-400" />
                                    </div>
                                    <p className="text-white font-medium mb-1">點擊「執行 AI 交易分析」開始</p>
                                    <p className="text-sm text-gray-500 max-w-[200px]">AI 將啟動 4 位專家進行深度分析</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
}
