import { useState, useEffect, useRef } from 'react';
import { Search, Activity, BookOpen, ShieldAlert, Cpu, ChevronDown, ChevronUp, ExternalLink, Loader2, CheckCircle2, CircleDashed, Clock, History } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { analyzeSymbol } from '../api/analysis';
import type { AnalysisResult } from '../types/analysis';

interface AnalysisHistory {
    symbol: string;
    name: string;
    action: string;
    timestamp: number;
}

const HOTKEYS = [
    { symbol: '2330', name: '台積電' },
    { symbol: '2317', name: '鴻海' },
    { symbol: '2454', name: '聯發科' },
    { symbol: '2412', name: '中華電' },
    { symbol: '0050', name: '元大台灣50' },
    { symbol: '2603', name: '長榮' }
];

const LOADING_STEPS = [
    "取得即時報價",
    "計算技術指標",
    "技術分析師分析中...",
    "市場情緒分析",
    "風控評估",
    "首席決策官決策"
];

export function StockPicker() {
  const [symbol, setSymbol] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState('');
  
  // Storage and Loading States
  const [history, setHistory] = useState<AnalysisHistory[]>([]);
  const [loadingStep, setLoadingStep] = useState(0);
  const [timeLeft, setTimeLeft] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  
  // Accordion states
  const [expandedReport, setExpandedReport] = useState<string | null>('technical');

  useEffect(() => {
      const saved = localStorage.getItem('recent_analysis');
      if (saved) {
          try { setHistory(JSON.parse(saved)); } catch (e) {}
      }
  }, []);

  const handleAnalyzeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    startAnalysis(symbol);
  };

  const startAnalysis = async (targetSymbol: string) => {
    if (!targetSymbol.trim()) return;
    setSymbol(targetSymbol);
    setLoading(true);
    setResult(null);
    setError('');
    
    // 四個 AI Agent 各約 20~30 秒，總計預估 120 秒
    setLoadingStep(0);
    setTimeLeft(120);
    
    let currentStep = 0;
    let ticks = 0;
    
    if (timerRef.current) clearInterval(timerRef.current);
    
    timerRef.current = setInterval(() => {
        ticks++;
        // 每 20 秒推進一個步驟（6 個步驟 × 20 秒 = 120 秒）
        if (ticks % 20 === 0 && currentStep < 5) {
            currentStep++;
            setLoadingStep(currentStep);
        }
        setTimeLeft(prev => Math.max(0, prev - 1));
    }, 1000);

    try {
      const response = await analyzeSymbol(targetSymbol.trim());
      
      const newHistoryItem: AnalysisHistory = {
          symbol: targetSymbol,
          name: response.name || targetSymbol,
          action: response.decision?.action || 'HOLD',
          timestamp: Date.now()
      };
      
      setHistory(prev => {
          const filtered = prev.filter(item => item.symbol !== targetSymbol);
          const updated = [newHistoryItem, ...filtered].slice(0, 5);
          localStorage.setItem('recent_analysis', JSON.stringify(updated));
          return updated;
      });

      // Force finish animation
      setLoadingStep(5);
      clearInterval(timerRef.current!);
      setTimeout(() => {
          setResult(response);
          setLoading(false);
      }, 500);

    } catch (err: any) {
      clearInterval(timerRef.current!);
      setError(err?.response?.data?.detail || err.message || '分析失敗，請檢查代號是否正確。');
      setLoading(false);
    }
  };

  const toggleAccordion = (reportId: string) => {
    setExpandedReport(expandedReport === reportId ? null : reportId);
  };

  const formatTimeAgo = (ts: number) => {
      const diff = Math.floor((Date.now() - ts) / 1000 / 60);
      if (diff < 1) return '剛剛';
      if (diff < 60) return `${diff} 分鐘前`;
      const hours = Math.floor(diff / 60);
      if (hours < 24) return `${hours} 小時前`;
      return new Date(ts).toLocaleDateString();
  };

  return (
    <div className="flex-1 overflow-auto bg-bg-main p-4 md:p-8">
      <div className="max-w-5xl mx-auto pb-12 pt-[40px] md:pt-[60px] animate-in fade-in slide-in-from-bottom-4 duration-700">
        
        {/* Search Header - centered but pushed up */}
        {!result && !loading && (
            <div className="mb-12">
              <div className="text-center mb-8">
                <h1 className="text-4xl font-black text-text-main mb-4 tracking-tighter">
                  Alpha<span className="text-brand-primary underline decoration-2 underline-offset-8">TW</span> 智慧選股偵查組
                </h1>
                <p className="text-text-muted max-w-xl mx-auto text-sm leading-relaxed font-medium">
                  輸入台股標的代號，深度掃描 K 線型態、社群情緒與帳戶風險，提供精準操作建議。
                </p>
              </div>

              <form onSubmit={handleAnalyzeSubmit} className="flex gap-4 mb-6 max-w-2xl mx-auto group">
                <div className="relative flex-1">
                  <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-text-muted group-focus-within:text-brand-primary transition-colors" />
                  <input
                    type="text"
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    placeholder="例如：2330 或 2454"
                    className="w-full pl-12 pr-4 py-4 bg-card-bg border border-card-border rounded-xl text-text-main placeholder-text-muted/50 focus:outline-none focus:border-brand-primary/50 transition-all text-lg font-mono shadow-2xl"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!symbol.trim()}
                  className="btn btn-primary glow-purple px-10 py-4 rounded-xl flex items-center gap-3 disabled:opacity-30"
                >
                  <Cpu className="h-5 w-5" />
                  <span className="font-black tracking-widest">開始調研</span>
                </button>
              </form>

              {/* Hotkeys */}
              <div className="max-w-2xl mx-auto flex flex-wrap justify-center gap-3 mb-12">
                  {HOTKEYS.map(hk => (
                      <button 
                        key={hk.symbol}
                        onClick={() => startAnalysis(hk.symbol)}
                        className="px-4 py-2 bg-white/5 border border-white/10 hover:border-brand-primary/50 hover:bg-white/10 hover:shadow-[0_0_10px_rgba(99,102,241,0.2)] rounded-lg text-xs font-bold text-text-muted hover:text-white transition-all duration-300 flex items-center gap-2"
                      >
                          <span className="font-mono text-brand-primary">{hk.symbol}</span>
                          {hk.name}
                      </button>
                  ))}
              </div>

              {/* History */}
              {history.length > 0 && (
                  <div className="max-w-2xl mx-auto animate-in fade-in duration-500">
                      <h3 className="text-sm font-black text-text-muted uppercase tracking-widest flex items-center gap-2 mb-4">
                          <History className="w-4 h-4" /> 最近分析紀錄
                      </h3>
                      <div className="flex flex-col gap-2">
                          {history.map((h, i) => (
                              <button 
                                key={i}
                                onClick={() => startAnalysis(h.symbol)}
                                className="w-full bg-white/5 border border-white/5 hover:bg-white/10 p-4 rounded-xl flex items-center justify-between group transition-all"
                              >
                                  <div className="flex items-center gap-4">
                                      <span className="font-mono text-lg font-black text-brand-primary group-hover:scale-110 transition-transform">{h.symbol}</span>
                                      <span className="font-bold text-white">{h.name}</span>
                                      <span className="text-[10px] text-text-muted ml-2 bg-black/20 px-2 py-1 rounded-full whitespace-nowrap hidden sm:inline-block">{formatTimeAgo(h.timestamp)}</span>
                                  </div>
                                  <div className={`px-3 py-1 text-[10px] font-black uppercase tracking-widest rounded-full border ${
                                      h.action === 'BUY' ? 'bg-danger/10 text-danger border-danger/20' :
                                      h.action === 'SELL' ? 'bg-success/10 text-success border-success/20' :
                                      'bg-warning/10 text-warning border-warning/20'
                                  }`}>
                                      {h.action}
                                  </div>
                              </button>
                          ))}
                      </div>
                  </div>
              )}
            </div>
        )}

        {error && !loading && (
          <div className="panel bg-danger/5 border-danger/20 p-5 max-w-2xl mx-auto flex items-center gap-4 animate-in zoom-in-95 duration-300">
            <div className="p-2 bg-danger/10 rounded-lg">
                <ShieldAlert className="w-6 h-6 text-danger" />
            </div>
            <div className="flex-1">
                <h4 className="text-sm font-bold text-danger">分析任務中斷</h4>
                <p className="text-xs text-danger/80">{error}</p>
            </div>
            <button onClick={() => setError('')} className="btn px-4 py-2 text-xs">重新搜尋</button>
          </div>
        )}

        {/* LOADING SIMULATION */}
        {loading && (
            <div className="panel p-8 md:p-12 max-w-2xl mx-auto flex flex-col items-center animate-in zoom-in-95 duration-500 shadow-2xl border-brand-primary/20">
                <div className="relative mb-8">
                    <div className="absolute inset-0 bg-brand-primary/20 blur-3xl rounded-full animate-pulse"></div>
                    <div className="text-6xl md:text-8xl font-black font-mono text-white tracking-tighter relative z-10 drop-shadow-2xl">
                        {symbol}
                    </div>
                </div>
                
                <div className="w-full max-w-sm space-y-4 mb-10">
                    {LOADING_STEPS.map((step, index) => {
                        const prev = index < loadingStep;
                        const current = index === loadingStep;
                        return (
                            <div key={index} className={`flex items-center gap-4 transition-all duration-500 ${prev || current ? 'opacity-100 translate-x-0' : 'opacity-30 -translate-x-4'}`}>
                                {prev ? <CheckCircle2 className="w-5 h-5 text-brand-primary shrink-0" /> : 
                                 current ? <Loader2 className="w-5 h-5 text-white animate-spin shrink-0" /> : 
                                 <CircleDashed className="w-5 h-5 text-text-muted shrink-0" />}
                                <span className={`font-bold text-sm ${current ? 'text-white' : prev ? 'text-brand-primary/80' : 'text-text-muted'}`}>
                                    {step}
                                </span>
                            </div>
                        )
                    })}
                </div>

                <div className="flex items-center gap-2 text-brand-primary/80 font-mono bg-brand-primary/10 px-6 py-3 rounded-full border border-brand-primary/20 text-sm font-bold">
                    <Clock className="w-4 h-4 animate-pulse" /> 預估剩餘時間：{timeLeft} 秒
                </div>
            </div>
        )}

        {/* RESULT ANALYSIS VIEW */}
        {result && !loading && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-8 duration-700">
            
            <div className="flex justify-between items-center mb-6">
                 <button onClick={() => setResult(null)} className="btn bg-white/5 border-white/10 hover:bg-white/10 text-xs px-4 py-2">
                    ← 返回搜尋
                 </button>
            </div>

            {/* Top Half: 60/40 Split */}
            <div className="flex flex-col lg:flex-row gap-6">
                
                {/* 60% Left Section */}
                <div className="panel w-full lg:w-[60%] p-8 relative overflow-hidden flex flex-col justify-between">
                    <div className="absolute top-0 right-0 w-64 h-64 bg-brand-primary/10 blur-[100px] rounded-full pointer-events-none"></div>
                    
                    <div>
                        <div className="flex justify-between items-start mb-6">
                            <div>
                                <h2 className="text-4xl md:text-5xl lg:text-6xl font-black text-white mb-2 tracking-tight">{result.name}</h2>
                                <div className="flex items-center gap-3">
                                    <span className="bg-white/10 text-white font-mono text-sm px-3 py-1 rounded-md border border-white/10 font-black">{result.symbol}</span>
                                    <span className="text-3xl lg:text-4xl font-mono font-black text-brand-primary ml-2">${result.current_price?.toLocaleString()}</span>
                                </div>
                            </div>
                            <div className={`px-4 lg:px-6 py-2 lg:py-3 border-2 rounded-xl text-xl lg:text-2xl font-black tracking-widest uppercase transform rotate-2 ${
                                result.decision?.action === 'BUY' ? 'border-danger text-danger bg-danger/10 shadow-[0_0_20px_rgba(239,68,68,0.2)]' : 
                                result.decision?.action === 'SELL' ? 'border-success text-success bg-success/10 shadow-[0_0_20px_rgba(16,185,129,0.2)]' : 
                                'border-warning text-warning bg-warning/10'
                            }`}>
                                {result.decision?.action}
                            </div>
                        </div>

                        <div className="mb-8 w-full">
                            <div className="flex justify-between items-center mb-2">
                                <span className="text-xs font-black tracking-widest uppercase text-text-muted">AI 信心百分比</span>
                                <span className="font-mono font-black text-white">{((result.decision?.confidence || 0) * 100).toFixed(0)}%</span>
                            </div>
                            <div className="h-3 w-full bg-black/40 rounded-full overflow-hidden border border-white/5">
                                <div 
                                    className="h-full bg-gradient-to-r from-brand-primary to-purple-500 rounded-full shadow-[0_0_15px_#6366f1]"
                                    style={{ width: `${(result.decision?.confidence || 0) * 100}%` }}
                                />
                            </div>
                        </div>

                        <div className="p-6 bg-white/5 rounded-2xl border border-white/5 relative z-10 backdrop-blur-sm">
                            <h3 className="text-xs text-text-muted font-black uppercase tracking-widest mb-3 flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-brand-primary"></span>
                                總體決策理據
                            </h3>
                            <p className="text-white text-lg md:text-xl leading-relaxed font-medium">
                                {result.decision?.reasoning}
                            </p>
                        </div>
                    </div>
                </div>

                {/* 40% Right Section (2x2 Cards) */}
                <div className="w-full lg:w-[40%] grid grid-cols-2 grid-rows-2 gap-[12px] h-full min-h-[400px]">
                     <div className="panel p-6 flex flex-col justify-center bg-gradient-to-br from-[#111827] to-[#1a2035] h-full">
                         <span className="text-[10px] text-text-muted font-black uppercase tracking-widest mb-2">進場參考價</span>
                         <div className="text-3xl lg:text-4xl font-black font-mono text-white">${result.current_price?.toLocaleString() || '-'}</div>
                     </div>
                     <div className="panel p-6 flex flex-col justify-center bg-gradient-to-br from-[#111827] to-[#1a2035] border-t-4 border-t-danger/50 h-full">
                         <span className="text-[10px] text-text-muted font-black uppercase tracking-widest mb-2">止盈目標價</span>
                         <div className="text-3xl lg:text-4xl font-black font-mono text-danger">${result.decision?.take_profit_price || '-'}</div>
                     </div>
                     <div className="panel p-6 flex flex-col justify-center bg-gradient-to-br from-[#111827] to-[#1a2035] border-t-4 border-t-success/50 h-full">
                         <span className="text-[10px] text-text-muted font-black uppercase tracking-widest mb-2">止損防護價</span>
                         <div className="text-3xl lg:text-4xl font-black font-mono text-success">${result.decision?.stop_loss_price || '-'}</div>
                     </div>
                     <div className="panel p-6 flex flex-col justify-center bg-gradient-to-br from-[#111827] to-[#1a2035] border-t-4 border-t-brand-primary/50 h-full">
                         <span className="text-[10px] text-text-muted font-black uppercase tracking-widest mb-2">建議倉位比例</span>
                         {result.decision?.action === 'HOLD' && (result.decision?.position_size_pct === 0 || !result.decision?.position_size_pct) ? (
                            <div>
                                <div className="text-2xl lg:text-3xl font-black text-text-muted">觀望</div>
                                <div className="text-[10px] text-text-muted/60 mt-1 font-bold">等待更佳進場時機</div>
                            </div>
                         ) : (
                            <div className="text-3xl lg:text-4xl font-black font-mono text-brand-primary">{result.decision?.position_size_pct || '0'}%</div>
                         )}
                     </div>
                </div>

            </div>

            {/* Bottom Half: Detailed Reports (Accordions) */}
            <div className="space-y-4 pt-4">
                <h3 className="text-lg font-black text-white px-2 mb-2">📑 探員深度研報</h3>
                
               {/* Technical Report */}
               <div className={`panel overflow-hidden transition-all duration-300 ${expandedReport === 'technical' ? 'border-brand-primary/50 shadow-[0_0_20px_rgba(99,102,241,0.1)]' : ''}`}>
                  <button 
                    onClick={() => toggleAccordion('technical')}
                    className="w-full px-6 py-5 flex items-center justify-between hover:bg-white/5 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl bg-brand-primary/10 flex items-center justify-center border border-brand-primary/20">
                            <Activity className="w-5 h-5 text-brand-primary" />
                        </div>
                        <div className="text-left">
                            <div className="text-white font-black">📈 技術面與趨勢動量報告</div>
                        </div>
                    </div>
                    {expandedReport === 'technical' ? <ChevronUp className="w-5 h-5 text-text-muted" /> : <ChevronDown className="w-5 h-5 text-text-muted" />}
                  </button>
                  <div className={`px-6 overflow-hidden transition-all duration-500 ease-in-out ${expandedReport === 'technical' ? 'max-h-[1000px] pb-6 opacity-100' : 'max-h-0 opacity-0'}`}>
                        <div className="pt-4 border-t border-card-border text-text-muted text-sm leading-relaxed whitespace-pre-wrap">
                            <ReactMarkdown
                                components={{
                                    strong: ({node, ...props}) => <span className="font-bold text-[#f9fafb]" {...props} />,
                                    ul: ({node, ...props}) => <ul className="list-disc pl-5 my-2 marker:text-brand-primary" {...props} />,
                                    li: ({node, ...props}) => <li className="mb-1" {...props} />,
                                    p: ({node, ...props}) => <p className="mb-[8px]" {...props} />
                                }}
                            >
                                {result.technical_report}
                            </ReactMarkdown>
                        </div>
                  </div>
               </div>

               {/* Sentiment Report */}
               <div className={`panel overflow-hidden transition-all duration-300 ${expandedReport === 'sentiment' ? 'border-brand-primary/50 shadow-[0_0_20px_rgba(99,102,241,0.1)]' : ''}`}>
                  <button 
                    onClick={() => toggleAccordion('sentiment')}
                    className="w-full px-6 py-5 flex items-center justify-between hover:bg-white/5 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
                            <BookOpen className="w-5 h-5 text-indigo-400" />
                        </div>
                        <div className="text-left">
                            <div className="text-white font-black">🎭 市場輿論與新聞情緒報告</div>
                        </div>
                    </div>
                    {expandedReport === 'sentiment' ? <ChevronUp className="w-5 h-5 text-text-muted" /> : <ChevronDown className="w-5 h-5 text-text-muted" />}
                  </button>
                  <div className={`px-6 overflow-hidden transition-all duration-500 ease-in-out ${expandedReport === 'sentiment' ? 'max-h-[1000px] pb-6 opacity-100' : 'max-h-0 opacity-0'}`}>
                        <div className="pt-4 border-t border-card-border text-text-muted text-sm leading-relaxed whitespace-pre-wrap">
                            <ReactMarkdown
                                components={{
                                    strong: ({node, ...props}) => <span className="font-bold text-[#f9fafb]" {...props} />,
                                    ul: ({node, ...props}) => <ul className="list-disc pl-5 my-2 marker:text-brand-primary" {...props} />,
                                    li: ({node, ...props}) => <li className="mb-1" {...props} />,
                                    p: ({node, ...props}) => <p className="mb-[8px]" {...props} />
                                }}
                            >
                                {result.sentiment_report}
                            </ReactMarkdown>
                        </div>
                  </div>
               </div>

               {/* Risk Report */}
               <div className={`panel overflow-hidden transition-all duration-300 ${expandedReport === 'risk' ? 'border-brand-primary/50 shadow-[0_0_20px_rgba(99,102,241,0.1)]' : ''}`}>
                  <button 
                    onClick={() => toggleAccordion('risk')}
                    className="w-full px-6 py-5 flex items-center justify-between hover:bg-white/5 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl bg-rose-500/10 flex items-center justify-center border border-rose-500/20">
                            <ShieldAlert className="w-5 h-5 text-rose-400" />
                        </div>
                        <div className="text-left">
                            <div className="text-white font-black">🛡️ 風險與資金控管評估報告</div>
                        </div>
                    </div>
                    {expandedReport === 'risk' ? <ChevronUp className="w-5 h-5 text-text-muted" /> : <ChevronDown className="w-5 h-5 text-text-muted" />}
                  </button>
                  <div className={`px-6 overflow-hidden transition-all duration-500 ease-in-out ${expandedReport === 'risk' ? 'max-h-[1000px] pb-6 opacity-100' : 'max-h-0 opacity-0'}`}>
                        <div className="pt-4 border-t border-card-border text-text-muted text-sm leading-relaxed whitespace-pre-wrap">
                            <ReactMarkdown
                                components={{
                                    strong: ({node, ...props}) => <span className="font-bold text-[#f9fafb]" {...props} />,
                                    ul: ({node, ...props}) => <ul className="list-disc pl-5 my-2 marker:text-brand-primary" {...props} />,
                                    li: ({node, ...props}) => <li className="mb-1" {...props} />,
                                    p: ({node, ...props}) => <p className="mb-[8px]" {...props} />
                                }}
                            >
                                {result.risk_report}
                            </ReactMarkdown>
                        </div>
                  </div>
               </div>
            </div>

            <div className="flex justify-center pt-8 pb-12 gap-4 flex-wrap">
                <button 
                  onClick={() => setResult(null)}
                  className="btn btn-primary px-8 py-3 text-sm font-black flex items-center gap-2"
                >
                    <Search className="w-4 h-4" /> 重新分析其他標的
                </button>
                <button 
                  onClick={() => window.open(`https://tw.stock.yahoo.com/quote/${result.symbol}`, '_blank')}
                  className="btn bg-white/5 border border-white/10 hover:bg-white/10 px-8 py-3 text-[12px] font-black uppercase text-text-muted hover:text-white transition-all flex items-center gap-2"
                >
                    <ExternalLink className="w-4 h-4" /> Yahoo 股市即時報價
                </button>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}
