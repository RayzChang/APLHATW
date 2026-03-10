import { X, CheckCircle, AlertCircle, Loader2, Bell, BellOff } from 'lucide-react';
import { useState, useEffect } from 'react';
import api from '../api/axiosConfig';

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
}

interface BackendSettings {
    initial_capital: number;
    current_cash: number;
    current_assets: number;
    watchlist: string[];
    has_finmind_token: boolean;
    has_gemini_key: boolean;
    has_line_token: boolean;
    line_notify_enabled: boolean;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
    const [balance, setBalance] = useState('1000000');
    const [newSymbol, setNewSymbol] = useState('');
    const [watchlist, setWatchlist] = useState<string[]>(['2330', '2317', '2454', '2412', '0050']);
    const [backendInfo, setBackendInfo] = useState<BackendSettings | null>(null);
    const [lineEnabled, setLineEnabled] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [saveMsg, setSaveMsg] = useState<{ ok: boolean; msg: string } | null>(null);

    // Load from backend on open
    useEffect(() => {
        if (!isOpen) return;
        setSaveMsg(null);
        api.get('/api/settings/')
            .then(res => {
                const s: BackendSettings = res.data;
                setBackendInfo(s);
                setBalance(String(s.initial_capital));
                setWatchlist(s.watchlist);
                setLineEnabled(s.line_notify_enabled ?? false);
            })
            .catch(() => {
                // fallback to localStorage
                setBalance(localStorage.getItem('sim_balance') || '1000000');
                const saved = localStorage.getItem('user_watchlist');
                if (saved) try { setWatchlist(JSON.parse(saved)); } catch { /* ok */ }
            });
    }, [isOpen]);

    if (!isOpen) return null;

    const handleAddSymbol = () => {
        const sym = newSymbol.trim().toUpperCase();
        if (sym && !watchlist.includes(sym)) {
            setWatchlist([...watchlist, sym]);
            setNewSymbol('');
        }
    };

    const handleRemoveSymbol = (symbol: string) => {
        setWatchlist(watchlist.filter(s => s !== symbol));
    };

    const handleSave = async () => {
        setIsSaving(true);
        setSaveMsg(null);
        const newCapital = parseFloat(balance);
        if (isNaN(newCapital) || newCapital < 10_000) {
            setSaveMsg({ ok: false, msg: '初始資金最少需要 10,000 TWD' });
            setIsSaving(false);
            return;
        }

        const capitalChanged = backendInfo && newCapital !== backendInfo.initial_capital;

        try {
            const lineChanged = backendInfo && lineEnabled !== backendInfo.line_notify_enabled;
            const payload: Record<string, unknown> = { watchlist };
            if (lineChanged) {
                payload.line_notify_enabled = lineEnabled;
            }
            if (capitalChanged) {
                if (!confirm(`確定要將初始資金調整為 ${newCapital.toLocaleString()} 並重置所有模擬資料嗎？此動作無法復原！`)) {
                    setIsSaving(false);
                    return;
                }
                payload.initial_capital = newCapital;
                payload.reset_simulator = true;
            }

            const res = await api.post('/api/settings/', payload);
            const changes: string[] = res.data.changes || [];
            setSaveMsg({ ok: true, msg: changes.join('；') || '設定已儲存' });

            // sync localStorage
            localStorage.setItem('sim_balance', balance);
            localStorage.setItem('user_watchlist', JSON.stringify(watchlist));
            setBackendInfo(prev => prev ? { ...prev, initial_capital: newCapital, watchlist, line_notify_enabled: lineEnabled } : prev);
            setTimeout(() => {
                onClose();
            }, 500);
        } catch (e: unknown) {
            const errMsg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '無法連線至後端';
            setSaveMsg({ ok: false, msg: errMsg });
        } finally {
            setIsSaving(false);
        }
    };

    const ApiKeyBadge = ({ active, label }: { active: boolean; label: string }) => (
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm ${
            active ? 'border-success/30 bg-success/10 text-success' : 'border-danger/30 bg-danger/10 text-danger'
        }`}>
            {active
                ? <CheckCircle className="w-4 h-4 shrink-0" />
                : <AlertCircle className="w-4 h-4 shrink-0" />}
            <span className="font-bold">{label}</span>
            <span className="text-[11px] opacity-70">{active ? '已設定' : '未設定（請修改 .env）'}</span>
        </div>
    );

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="panel w-full max-w-2xl bg-panel border-white/10 shadow-2xl flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="flex items-center justify-between p-5 border-b border-white/5">
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        ⚙️ 系統設定
                    </h2>
                    <button onClick={onClose} className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 overflow-y-auto space-y-6">

                    {/* API Key Status */}
                    {backendInfo && (
                        <div className="space-y-3">
                            <label className="text-sm font-bold text-gray-300">🔑 API Key 狀態</label>
                            <div className="grid grid-cols-1 gap-2">
                                <ApiKeyBadge active={backendInfo.has_gemini_key} label="Gemini API Key" />
                                <ApiKeyBadge active={backendInfo.has_finmind_token} label="FinMind Token" />
                                <ApiKeyBadge active={backendInfo.has_line_token} label="LINE Notify Token" />
                            </div>
                            <p className="text-xs text-gray-500">API Key 設定請修改伺服器端的 <code className="bg-white/10 px-1 rounded">.env</code> 檔案後重啟後端</p>
                        </div>
                    )}

                    {/* Current Account Status */}
                    {backendInfo && (
                        <div className="bg-black/30 rounded-xl p-4 border border-white/5 grid grid-cols-3 gap-3 text-center">
                            <div>
                                <div className="text-[10px] text-text-muted uppercase tracking-widest font-bold mb-1">初始資金</div>
                                <div className="text-sm font-black font-mono">{backendInfo.initial_capital.toLocaleString()}</div>
                            </div>
                            <div>
                                <div className="text-[10px] text-text-muted uppercase tracking-widest font-bold mb-1">可用現金</div>
                                <div className="text-sm font-black font-mono">{backendInfo.current_cash.toLocaleString()}</div>
                            </div>
                            <div>
                                <div className="text-[10px] text-text-muted uppercase tracking-widest font-bold mb-1">總資產</div>
                                <div className="text-sm font-black font-mono">{backendInfo.current_assets.toLocaleString()}</div>
                            </div>
                        </div>
                    )}

                    {/* Initial Balance */}
                    <div className="space-y-3">
                        <label className="text-sm font-medium text-gray-300">💰 初始模擬資金 (TWD)</label>
                        <input
                            type="number"
                            value={balance}
                            onChange={(e) => setBalance(e.target.value)}
                            className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-brand-primary transition-all"
                            placeholder="1000000"
                        />
                        <p className="text-xs text-warning flex items-center gap-1">
                            ⚠️ 修改初始資金並儲存後，將清空所有模擬持倉與交易記錄（不可恢復）
                        </p>
                    </div>

                    {/* Watchlist */}
                    <div className="space-y-3">
                        <label className="text-sm font-medium text-gray-300">📑 模擬交易股票池</label>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                placeholder="輸入股票代號，如 2330，按 Enter 新增"
                                value={newSymbol}
                                onChange={(e) => setNewSymbol(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleAddSymbol()}
                                className="flex-1 bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-brand-primary transition-all"
                            />
                            <button onClick={handleAddSymbol} className="btn btn-secondary px-6">新增</button>
                        </div>
                        <div className="flex flex-wrap gap-2 pt-2 max-h-[120px] overflow-y-auto">
                            {watchlist.map(symbol => (
                                <span key={symbol} className="px-3 py-1 bg-white/5 border border-white/10 rounded-md text-sm text-gray-300 flex items-center gap-2 hover:border-white/20 transition-colors">
                                    {symbol}
                                    <button onClick={() => handleRemoveSymbol(symbol)} className="text-gray-500 hover:text-danger transition-colors">
                                        <X className="w-3 h-3" />
                                    </button>
                                </span>
                            ))}
                        </div>
                        <p className="text-xs text-gray-500">AI 每天自動掃描這些股票，找出買賣機會。建議 5-20 檔，過多會影響速度。</p>
                    </div>

                    {/* LINE Notification Toggle */}
                    <div className="space-y-3">
                        <label className="text-sm font-bold text-gray-300">🔔 LINE 推播通知</label>
                        <div className="flex items-center justify-between p-4 bg-black/20 rounded-xl border border-white/5">
                            <div className="flex items-center gap-3">
                                {lineEnabled
                                    ? <Bell className="w-5 h-5 text-brand-primary" />
                                    : <BellOff className="w-5 h-5 text-text-muted" />}
                                <div>
                                    <div className="text-sm font-bold text-white">
                                        {lineEnabled ? '通知已開啟' : '通知已關閉'}
                                    </div>
                                    <div className="text-[11px] text-text-muted">
                                        AI 買入、賣出、掃描完成時推送 LINE 訊息
                                    </div>
                                </div>
                            </div>
                            <button
                                onClick={() => setLineEnabled(!lineEnabled)}
                                className={`relative w-12 h-6 rounded-full transition-colors ${
                                    lineEnabled ? 'bg-brand-primary' : 'bg-white/20'
                                }`}
                            >
                                <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                                    lineEnabled ? 'translate-x-6' : ''
                                }`} />
                            </button>
                        </div>
                        {!backendInfo?.has_line_token && (
                            <p className="text-xs text-yellow-400 flex items-center gap-1">
                                ⚠️ LINE Bot 尚未設定 — 請在 .env 填入 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_USER_ID 後重啟後端
                            </p>
                        )}
                        {backendInfo?.has_line_token && (
                            <p className="text-xs text-gray-500">
                                已連接 LINE Bot。開啟後，AI 每次買入、賣出、完成掃描都會即時推送通知到你的 LINE。
                            </p>
                        )}
                    </div>

                    {/* Save Message */}
                    {saveMsg && (
                        <div className={`flex items-start gap-2 p-3 rounded-lg border text-sm ${
                            saveMsg.ok ? 'border-success/30 bg-success/10 text-success' : 'border-danger/30 bg-danger/10 text-danger'
                        }`}>
                            {saveMsg.ok
                                ? <CheckCircle className="w-4 h-4 shrink-0 mt-0.5" />
                                : <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />}
                            {saveMsg.msg}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-5 border-t border-white/5 flex items-center justify-end gap-3 bg-black/20">
                    <button onClick={onClose} className="btn btn-secondary">取消</button>
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="btn btn-primary gap-2 disabled:opacity-50 disabled:pointer-events-none"
                    >
                        {isSaving && <Loader2 className="w-4 h-4 animate-spin" />}
                        {isSaving ? '儲存中...' : '儲存設定'}
                    </button>
                </div>
            </div>
        </div>
    );
}
