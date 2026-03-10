import { ChevronDown, ChevronUp, Download } from 'lucide-react';
import { useState } from 'react';
import type { TradeRecord } from '../../types/trading';

interface TradeHistoryPanelProps {
  trades: TradeRecord[];
  formatMoney: (value: number) => string;
  onExport: () => void;
}

export function TradeHistoryPanel({ trades, formatMoney, onExport }: TradeHistoryPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const hasNumber = (value: number | null | undefined): value is number => typeof value === 'number' && Number.isFinite(value);

  return (
    <div className="panel overflow-hidden mb-6">
      <button onClick={() => setIsExpanded(!isExpanded)} className="w-full p-6 flex justify-between items-center hover:bg-white/5 transition-colors">
        <h3 className="text-lg font-black tracking-tight flex items-center gap-2">
          <span className="bg-text-muted w-1 h-5 rounded-full inline-block"></span>
          歷史交易紀錄
        </h3>
        <div className="flex items-center gap-3">
          {trades.length > 0 && (
            <button onClick={(e) => { e.stopPropagation(); onExport(); }} className="btn btn-secondary gap-1.5 px-3 py-1.5 text-[11px]">
              <Download className="w-3.5 h-3.5" /> 匯出 CSV
            </button>
          )}
          <span className="text-xs text-text-muted font-bold">近期 {trades.length} 筆</span>
          {isExpanded ? <ChevronUp className="w-5 h-5 text-text-muted" /> : <ChevronDown className="w-5 h-5 text-text-muted" />}
        </div>
      </button>

      {isExpanded && (
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
                  <tr key={i} className={`group hover:bg-white/5 transition-colors border-l-4 ${t.action === 'BUY' ? 'border-l-success' : 'border-l-danger'}`}>
                    <td className="px-4 py-3 text-xs text-text-muted font-mono">{t.timestamp ? new Date(t.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--:--'}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-1 rounded text-[9px] font-black uppercase tracking-widest ${t.action === 'BUY' ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'}`}>
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
                      {hasNumber(t.profit) ? <span className={t.profit >= 0 ? 'text-danger' : 'text-success'}>{t.profit > 0 ? '+' : ''}{formatMoney(t.profit)}</span> : '---'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm font-bold">
                      {hasNumber(t.profit_pct) ? <span className={t.profit_pct >= 0 ? 'text-danger' : 'text-success'}>{t.profit_pct > 0 ? '+' : ''}{t.profit_pct.toFixed(2)}%</span> : '---'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
