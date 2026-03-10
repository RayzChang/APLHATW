import { Loader2, RefreshCcw, TrendingUp } from 'lucide-react';
import type { WatchlistQuote } from '../../types/trading';

interface WatchlistPanelProps {
  items: WatchlistQuote[];
  isLoading: boolean;
  onRefresh: () => void;
}

export function WatchlistPanel({ items, isLoading, onRefresh }: WatchlistPanelProps) {
  return (
    <div className="panel p-4 flex-1 flex flex-col min-h-0">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-black uppercase tracking-widest flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-brand-primary" /> 即時觀察清單
        </h3>
        <button onClick={onRefresh} disabled={isLoading} className="p-1 hover:bg-white/10 rounded-lg transition-colors">
          <RefreshCcw className={`w-3.5 h-3.5 text-text-muted ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto pr-1 space-y-1">
        {isLoading && items.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <Loader2 className="w-5 h-5 animate-spin text-brand-primary" />
          </div>
        ) : (
          items.map((item, i) => (
            <div key={i} className="flex items-center justify-between p-2 hover:bg-white/5 rounded-lg transition-colors">
              <div className="flex flex-col w-[28%] shrink-0">
                <div className="flex items-center gap-1">
                  <span className="text-xs font-black text-text-main">{item.symbol}</span>
                  {!item.is_realtime && <span className="text-[8px] bg-text-muted/20 text-text-muted px-1 rounded leading-none">收盤</span>}
                </div>
                <span className="text-[10px] text-text-muted truncate">{item.name}</span>
              </div>
              <div className="text-right flex flex-col w-[28%] shrink-0">
                <span className="text-xs font-mono font-bold">{item.price.toLocaleString()}</span>
                <span className={`text-[10px] font-mono font-bold ${item.change_pct >= 0 ? 'text-danger' : 'text-success'}`}>
                  {item.change_pct >= 0 ? '+' : ''}{item.change_pct.toFixed(2)}%
                </span>
              </div>
              <div className="text-right flex flex-col w-[22%] shrink-0">
                <span className="text-xs font-mono font-bold">{(item.volume || 0).toLocaleString()}</span>
                <span className="text-[10px] text-text-muted">張</span>
              </div>
              <div className="flex flex-col items-end gap-1 w-[22%] shrink-0">
                <span className={`text-[9px] font-black px-1.5 py-0.5 rounded leading-none ${
                  item.change_pct > 3 ? 'bg-danger/20 text-danger' :
                  item.change_pct < -3 ? 'bg-success/20 text-success' :
                  item.change_pct > 0 ? 'bg-danger/10 text-danger' : 'bg-success/10 text-success'
                }`}>
                  {item.change_pct > 3 ? '強勢' : item.change_pct < -3 ? '弱勢' : item.change_pct > 0 ? '上漲' : '下跌'}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
