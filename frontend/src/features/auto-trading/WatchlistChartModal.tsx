import { Loader2, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { fetchKlines } from '../../api/trading';
import type { KlinePoint, WatchlistQuote } from '../../types/trading';

interface WatchlistChartModalProps {
  item: WatchlistQuote | null;
  onClose: () => void;
}

function formatPrice(value: number) {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export function WatchlistChartModal({ item, onClose }: WatchlistChartModalProps) {
  const [data, setData] = useState<KlinePoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  useEffect(() => {
    if (!item) return;

    let active = true;
    setLoading(true);
    setError('');

    fetchKlines(item.symbol, 120)
      .then((res) => {
        if (!active) return;
        setData(res.data || []);
      })
      .catch((err: { response?: { data?: { detail?: string } }; message?: string }) => {
        if (!active) return;
        setError(err?.response?.data?.detail || err?.message || '無法載入 K 線圖');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [item]);

  const chart = useMemo(() => {
    if (!data.length) return null;

    const width = 760;
    const height = 360;
    const topPad = 30;
    const bottomPad = 34;
    const leftPad = 16;
    const rightPad = 12;
    const labelColumnWidth = 76;
    const plotRight = width - rightPad - labelColumnWidth;
    const bodyWidth = plotRight - leftPad;
    const bodyHeight = height - topPad - bottomPad;
    const rawMaxPrice = Math.max(...data.map((d) => d.high));
    const rawMinPrice = Math.min(...data.map((d) => d.low));
    const rawPriceRange = rawMaxPrice - rawMinPrice || 1;
    const pad = Math.max(rawPriceRange * 0.08, rawMaxPrice * 0.004);
    const maxPrice = rawMaxPrice + pad;
    const minPrice = Math.max(0, rawMinPrice - pad);
    const priceRange = maxPrice - minPrice || 1;
    const stepX = bodyWidth / data.length;
    const candleWidth = Math.max(4, Math.min(10, bodyWidth / data.length - 2));

    const y = (price: number) => topPad + ((maxPrice - price) / priceRange) * bodyHeight;

    const candles = data.map((point, index) => {
      const xCenter = leftPad + (index + 0.5) * stepX;
      const openY = y(point.open);
      const closeY = y(point.close);
      const highY = y(point.high);
      const lowY = y(point.low);
      const bullish = point.close >= point.open;
      const bodyTop = Math.min(openY, closeY);
      const bodyHeightPx = Math.max(2, Math.abs(closeY - openY));

      return {
        key: `${point.date}-${index}`,
        xCenter,
        openY,
        closeY,
        highY,
        lowY,
        bodyTop,
        bodyHeightPx,
        bullish,
        date: point.date,
        source: point,
      };
    });

    const yAxisLabels = Array.from({ length: 5 }, (_, i) => {
      const value = maxPrice - (priceRange * i) / 4;
      return { value, y: y(value) };
    });

    return { width, height, leftPad, rightPad, bottomPad, topPad, plotRight, bodyWidth, stepX, candles, candleWidth, yAxisLabels };
  }, [data]);

  const activeCandle = useMemo(() => {
    if (!chart || !chart.candles.length) return null;
    const index = hoveredIndex ?? chart.candles.length - 1;
    return chart.candles[Math.max(0, Math.min(chart.candles.length - 1, index))];
  }, [chart, hoveredIndex]);

  if (!item) return null;

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="panel w-full max-w-5xl max-h-[90vh] overflow-hidden border-white/10 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/5">
          <div>
            <div className="text-[11px] uppercase tracking-[0.3em] text-text-muted font-bold">技術圖</div>
            <div className="flex items-end gap-3 mt-1">
              <h3 className="text-2xl font-black text-white">{item.symbol}</h3>
              <span className="text-lg text-text-muted font-bold">{item.name}</span>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 text-text-muted hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-black/20 rounded-xl border border-white/5 p-4">
              <div className="text-[10px] uppercase tracking-widest text-text-muted font-bold mb-1">現價</div>
              <div className="text-2xl font-black font-mono text-white">{formatPrice(item.price)}</div>
            </div>
            <div className="bg-black/20 rounded-xl border border-white/5 p-4">
              <div className="text-[10px] uppercase tracking-widest text-text-muted font-bold mb-1">漲跌幅</div>
              <div className={`text-2xl font-black font-mono ${item.change_pct >= 0 ? 'text-danger' : 'text-success'}`}>
                {item.change_pct >= 0 ? '+' : ''}{item.change_pct.toFixed(2)}%
              </div>
            </div>
            <div className="bg-black/20 rounded-xl border border-white/5 p-4">
              <div className="text-[10px] uppercase tracking-widest text-text-muted font-bold mb-1">成交量 (張)</div>
              <div className="text-2xl font-black font-mono text-white">{item.volume.toLocaleString()}</div>
            </div>
            <div className="bg-black/20 rounded-xl border border-white/5 p-4">
              <div className="text-[10px] uppercase tracking-widest text-text-muted font-bold mb-1">資料來源</div>
              <div className="text-base font-black text-white">{item.is_realtime ? '即時' : '收盤'}</div>
            </div>
          </div>

          <div className="bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.18),_transparent_45%),linear-gradient(180deg,rgba(255,255,255,0.02),rgba(255,255,255,0.01))] border border-white/5 rounded-2xl p-4 min-h-[420px]">
            {loading ? (
              <div className="h-[380px] flex items-center justify-center gap-3 text-text-muted">
                <Loader2 className="w-5 h-5 animate-spin text-brand-primary" />
                載入 K 線中...
              </div>
            ) : error ? (
              <div className="h-[380px] flex items-center justify-center text-danger text-sm font-bold">{error}</div>
            ) : !chart ? (
              <div className="h-[380px] flex items-center justify-center text-text-muted text-sm">暫無 K 線資料</div>
            ) : (
              <div className="overflow-x-auto relative">
                <div className="absolute left-4 top-3 z-10 bg-black/35 border border-white/10 rounded-lg px-3 py-2 min-w-[220px]">
                  <div className="text-[10px] tracking-widest uppercase text-text-muted mb-1 font-bold">K 線資訊</div>
                  {activeCandle ? (
                    <>
                      <div className="text-[11px] text-white font-mono mb-1">{new Date(activeCandle.date).toLocaleDateString('zh-TW')}</div>
                      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
                        <span className="text-text-muted">開</span><span className="text-white font-mono text-right">{formatPrice(activeCandle.source.open)}</span>
                        <span className="text-text-muted">高</span><span className="text-white font-mono text-right">{formatPrice(activeCandle.source.high)}</span>
                        <span className="text-text-muted">低</span><span className="text-white font-mono text-right">{formatPrice(activeCandle.source.low)}</span>
                        <span className="text-text-muted">收</span><span className="text-white font-mono text-right">{formatPrice(activeCandle.source.close)}</span>
                        <span className="text-text-muted">量 (股)</span><span className="text-white font-mono text-right">{Math.round(activeCandle.source.volume).toLocaleString()}</span>
                      </div>
                    </>
                  ) : (
                    <div className="text-[11px] text-text-muted">滑鼠移到 K 線查看詳細資料</div>
                  )}
                </div>
                <svg
                  viewBox={`0 0 ${chart.width} ${chart.height}`}
                  className="w-full min-w-[760px] h-[380px]"
                  onMouseMove={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    const x = ((e.clientX - rect.left) / rect.width) * chart.width;
                    if (x < chart.leftPad || x > chart.plotRight) {
                      setHoveredIndex(null);
                      return;
                    }
                    const idx = Math.floor((x - chart.leftPad) / chart.stepX);
                    setHoveredIndex(Math.max(0, Math.min(chart.candles.length - 1, idx)));
                  }}
                  onMouseLeave={() => setHoveredIndex(null)}
                >
                  <defs>
                    <linearGradient id="chartBg" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="rgba(99,102,241,0.08)" />
                      <stop offset="100%" stopColor="rgba(15,23,42,0.02)" />
                    </linearGradient>
                  </defs>
                  <rect x="0" y="0" width={chart.width} height={chart.height} rx="18" fill="url(#chartBg)" />
                  {activeCandle && (
                    <line
                      x1={activeCandle.xCenter}
                      x2={activeCandle.xCenter}
                      y1={chart.topPad}
                      y2={chart.height - chart.bottomPad}
                      stroke="rgba(148,163,184,0.25)"
                      strokeDasharray="3 5"
                    />
                  )}
                  {chart.yAxisLabels.map((label, idx) => (
                    <g key={idx}>
                      <line x1={chart.leftPad} x2={chart.plotRight} y1={label.y} y2={label.y} stroke="rgba(255,255,255,0.08)" strokeDasharray="4 6" />
                      <text x={chart.width - chart.rightPad} y={label.y - 4} textAnchor="end" fill="rgba(148,163,184,0.9)" fontSize="11">
                        {formatPrice(label.value)}
                      </text>
                    </g>
                  ))}
                  {chart.candles.map((candle, idx) => (
                    <g key={candle.key}>
                      <line x1={candle.xCenter} x2={candle.xCenter} y1={candle.highY} y2={candle.lowY} stroke={candle.bullish ? '#10b981' : '#ef4444'} strokeWidth="1.4" />
                      <rect
                        x={candle.xCenter - chart.candleWidth / 2}
                        y={candle.bodyTop}
                        width={chart.candleWidth}
                        height={candle.bodyHeightPx}
                        rx="1.5"
                        fill={candle.bullish ? 'rgba(16,185,129,0.85)' : 'rgba(239,68,68,0.85)'}
                        stroke={hoveredIndex === idx ? '#f8fafc' : 'transparent'}
                        strokeWidth={hoveredIndex === idx ? '0.8' : '0'}
                      />
                    </g>
                  ))}
                  {chart.candles.filter((_, index) => index % Math.ceil(chart.candles.length / 6) === 0 || index === chart.candles.length - 1).map((candle) => (
                    <text key={`${candle.key}-date`} x={candle.xCenter} y={chart.height - 10} textAnchor="middle" fill="rgba(148,163,184,0.75)" fontSize="10">
                      {new Date(candle.date).toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' })}
                    </text>
                  ))}
                </svg>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
