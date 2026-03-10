import { Bot, Loader2 } from 'lucide-react';
import type { PositionItem } from '../../types/trading';

interface PositionsTableProps {
  positions: PositionItem[];
  isLoading: boolean;
  formatMoney: (value: number) => string;
}

export function PositionsTable({ positions, isLoading, formatMoney }: PositionsTableProps) {
  return (
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
            {isLoading ? (
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
                      (p.profit_pct || 0) > 2 ? 'bg-brand-primary/20 text-brand-primary' :
                      (p.profit_pct || 0) < -2 ? 'bg-danger/20 text-danger' : 'bg-white/10 text-text-muted'
                    }`}>
                      {p.status || ((p.profit_pct || 0) > 5 ? '追蹤止損中' : (p.profit_pct || 0) > 2 ? '保本啟動' : '正常')}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
