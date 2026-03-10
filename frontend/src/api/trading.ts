import api from './axiosConfig';
import type { PortfolioResponse, PositionItem, ScanState, TradeRecord, WatchlistQuote } from '../types/trading';

export async function fetchTradingPortfolio() {
  const res = await api.get<PortfolioResponse>('/api/trading/portfolio');
  return res.data;
}

export async function fetchTradingPositions() {
  const res = await api.get<PositionItem[]>('/api/trading/positions');
  return res.data;
}

export async function fetchTradingTrades() {
  const res = await api.get<TradeRecord[]>('/api/trading/trades');
  return res.data;
}

export async function fetchScanStatus() {
  const res = await api.get<ScanState>('/api/trading/scan/status');
  return res.data;
}

export async function runScanCycle() {
  const res = await api.post('/api/trading/scan/run');
  return res.data;
}

export async function toggleAutoScan() {
  const res = await api.post('/api/trading/scan/toggle');
  return res.data;
}

export async function resetSimulation() {
  const res = await api.post('/api/trading/reset');
  return res.data;
}

export async function fetchQuote(symbol: string) {
  const res = await api.get(`/api/stock/quote/${symbol}`);
  return res.data;
}

export async function fetchWatchlistQuotes(symbols: string[]): Promise<WatchlistQuote[]> {
  const results = await Promise.allSettled(symbols.map((sym) => fetchQuote(sym)));
  return results
    .map((result, index) => {
      if (result.status !== 'fulfilled') return null;
      const data = result.value;
      return {
        symbol: symbols[index],
        name: data.name || symbols[index],
        price: data.price || 0,
        change: data.change || 0,
        change_pct: data.change_pct || 0,
        volume: Math.round((data.volume || 0) / 1000),
        is_realtime: data.is_realtime !== false,
      } satisfies WatchlistQuote;
    })
    .filter(Boolean) as WatchlistQuote[];
}
