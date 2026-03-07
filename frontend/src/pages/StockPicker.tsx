import { useState } from 'react';
import { Search, Activity, BookOpen, ShieldAlert, Cpu } from 'lucide-react';

export function StockPicker() {
  const [symbol, setSymbol] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!symbol.trim()) return;

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const authHeader = 'Basic ' + btoa('admin:changeme');
      const response = await fetch('/api/analyze/manual', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': authHeader
        },
        body: JSON.stringify({ symbols: [symbol] })
      });

      const data = await response.json();
      if (!response.ok || data.error) {
        throw new Error(data.error || '分析失敗，請檢查代號是否正確。');
      }
      
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-auto bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-brand-300 to-indigo-300 bg-clip-text text-transparent">AI 選股器 (手動分析)</h1>
          <p className="text-gray-400 mt-2">輸入台股代號（如 2330），讓多組 AI 探員為您進行全方位深度分析，並提供進出場建議。</p>
        </div>

        <form onSubmit={handleAnalyze} className="flex gap-4 mb-8">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="輸入股票代號..."
              className="w-full pl-10 pr-4 py-3 bg-panel border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-brand-500 transition-colors"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !symbol.trim()}
            className="btn btn-primary px-8 py-3 rounded-xl flex items-center gap-2 disabled:opacity-50"
          >
            {loading ? (
              <span className="animate-spin w-5 h-5 border-2 border-white/20 border-t-white rounded-full" />
            ) : (
              <Cpu className="h-5 w-5" />
            )}
            {loading ? '分析中...' : '開始分析'}
          </button>
        </form>

        {error && (
          <div className="bg-danger/10 border border-danger/30 text-danger px-4 py-3 rounded-xl mb-6">
            {error}
          </div>
        )}

        {result && !loading && (
          <div className="space-y-6 animate-fade-in pb-12">
            {/* Header */}
            <div className="flex items-end gap-4 bg-panel border border-white/5 p-6 rounded-2xl">
              <div>
                <h2 className="text-3xl font-bold text-white tracking-tight">{result.name}</h2>
                <span className="text-brand-400 font-mono mt-1 block">{result.symbol}</span>
              </div>
              <div className="ml-auto text-right">
                <div className="text-sm text-gray-400 mb-1">目前股價</div>
                <div className="text-3xl font-mono font-bold text-white">
                  ${result.current_price?.toLocaleString()}
                </div>
              </div>
            </div>

            {/* AI Decision Panel */}
            <div className="bg-gradient-to-br from-panel to-black/40 border border-brand-500/20 p-6 rounded-2xl relative overflow-hidden">
              <div className="absolute top-0 left-0 w-1 h-full bg-brand-500" />
              <h3 className="text-lg font-medium text-brand-300 mb-4 flex items-center gap-2">
                <Cpu className="h-5 w-5" />
                首席決策長綜合判定
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
                <div className="bg-black/40 rounded-xl p-4">
                  <div className="text-sm text-gray-400 mb-1">建議操作</div>
                  <div className={`text-2xl font-bold ${
                    result.decision.action === 'BUY' ? 'text-success' : 
                    result.decision.action === 'SELL' ? 'text-danger' : 'text-warning'
                  }`}>
                    {result.decision.action === 'BUY' ? '強烈建議買進' : 
                     result.decision.action === 'SELL' ? '建議賣出 / 避開' : '建議觀望'}
                  </div>
                </div>
                <div className="bg-black/40 rounded-xl p-4">
                  <div className="text-sm text-gray-400 mb-1">AI 信心水準</div>
                  <div className="text-2xl font-bold text-white">
                    {(result.decision.confidence * 100).toFixed(0)}%
                  </div>
                </div>
                <div className="bg-black/40 rounded-xl p-4">
                  <div className="text-sm text-gray-400 mb-1">停損建議</div>
                  <div className="text-2xl font-mono text-danger">
                    {result.decision.stop_loss_price ? `$${result.decision.stop_loss_price}` : '無'}
                  </div>
                </div>
                <div className="bg-black/40 rounded-xl p-4">
                  <div className="text-sm text-gray-400 mb-1">停利目標</div>
                  <div className="text-2xl font-mono text-success">
                    {result.decision.take_profit_price ? `$${result.decision.take_profit_price}` : '無'}
                  </div>
                </div>
              </div>
              
              <div className="bg-black/40 rounded-xl p-5 border border-white/5">
                <div className="text-sm text-gray-400 mb-2">決策邏輯</div>
                <p className="text-gray-200 leading-relaxed text-lg">
                  {result.decision.reasoning}
                </p>
              </div>
            </div>

            {/* Reports Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Tech */}
              <div className="bg-panel border border-white/5 p-6 rounded-2xl flex flex-col">
                <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                  <Activity className="h-5 w-5 text-indigo-400" />
                  技術面與基本面分析
                </h3>
                <div className="prose prose-invert prose-sm max-w-none text-gray-300 leading-relaxed flex-1 whitespace-pre-wrap">
                  {result.reports?.technical}
                </div>
              </div>

              {/* Sentiment */}
              <div className="bg-panel border border-white/5 p-6 rounded-2xl flex flex-col">
                <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-purple-400" />
                  市場消息情緒洞察
                </h3>
                <div className="prose prose-invert prose-sm max-w-none text-gray-300 leading-relaxed flex-1 whitespace-pre-wrap">
                  {result.reports?.sentiment}
                </div>
              </div>

              {/* Risk */}
              <div className="bg-panel border border-white/5 p-6 rounded-2xl flex flex-col">
                <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                  <ShieldAlert className="h-5 w-5 text-rose-400" />
                  風險控管評估
                </h3>
                <div className="prose prose-invert prose-sm max-w-none text-gray-300 leading-relaxed flex-1 whitespace-pre-wrap">
                  {result.reports?.risk}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
