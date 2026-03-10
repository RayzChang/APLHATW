export interface AnalysisDecision {
  action: string;
  confidence: number;
  reasoning: string;
  score?: number;
  score_breakdown?: string;
  position_size_pct?: number;
  stop_loss_price?: number;
  take_profit_price?: number;
}

export interface AnalysisResult {
  symbol: string;
  stock_id: string;
  name: string;
  current_price: number;
  technical_report?: string;
  sentiment_report?: string;
  risk_report?: string;
  decision?: AnalysisDecision;
  technical_summary?: unknown;
  sentiment_summary?: unknown;
  risk_summary?: unknown;
  timestamp?: string;
}
