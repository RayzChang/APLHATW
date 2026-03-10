export interface EquityPoint {
  date: string;
  equity: number;
  benchmark: number;
}

export interface ScanState {
  is_scanning: boolean;
  current: number;
  total: number;
  message: string;
  auto_scan_enabled: boolean;
  market_status: string;
  daily_api_cost_twd: number;
  last_scan_time: string | null;
  last_scan_summary: string;
  stocks_screened: number;
  candidates_found: number;
  orders_placed: number;
}

export interface PositionItem {
  stock_id: string;
  name: string;
  shares: number;
  avg_cost: number;
  entry_price: number;
  current_price: number;
  market_value?: number;
  profit: number;
  profit_pct: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  stop_loss_price: number | null;
  take_profit_price: number | null;
  status?: '保本啟動' | '追蹤止損中' | '正常';
  break_even_price?: number;
  hold_days?: number;
}

export interface TradeRecord {
  timestamp: string;
  action: string;
  stock_id: string;
  stock_name?: string;
  shares: number;
  price: number;
  total_value: number;
  fee: number;
  profit?: number | null;
  profit_pct?: number | null;
}

export interface WatchlistQuote {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  volume: number;
  is_realtime: boolean;
}

export interface KlinePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PortfolioResponse {
  total_assets: number;
  cash: number;
  positions_value: number;
  total_profit: number;
  total_profit_pct: number;
  total_pnl?: number;
  total_pnl_pct?: number;
  equity_curve?: EquityPoint[];
  position_count?: number;
  positions?: PositionItem[];
  portfolio_v2?: {
    positions: Array<{ unrealized_pnl?: number }>;
  };
  scan_state?: ScanState;
}
