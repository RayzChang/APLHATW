import api from './axiosConfig';
import type { AnalysisResult } from '../types/analysis';

export async function analyzeSymbol(symbol: string) {
  const res = await api.get<AnalysisResult>(`/api/analysis/symbol/${symbol.trim()}`);
  return res.data;
}
