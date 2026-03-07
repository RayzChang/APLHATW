import { X } from 'lucide-react';
import { useState, useEffect } from 'react';

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
    const [apiKey, setApiKey] = useState('');
    const [balance, setBalance] = useState('1000000');
    const [temperature, setTemperature] = useState('0.7');
    const [intervalMin, setIntervalMin] = useState('15');
    
    const defaultWatchlist = ['2330', '0050'];
    const [watchlist, setWatchlist] = useState<string[]>(defaultWatchlist);
    const [newSymbol, setNewSymbol] = useState('');
    
    // Load saved settings from localStorage on open
    useEffect(() => {
        if (isOpen) {
            setApiKey(localStorage.getItem('gemini_api_key') || '');
            setBalance(localStorage.getItem('sim_balance') || '1000000');
            setTemperature(localStorage.getItem('ai_temp') || '0.7');
            setIntervalMin(localStorage.getItem('schedule_interval') || '15');
            const savedWatchlist = localStorage.getItem('user_watchlist');
            if (savedWatchlist) {
                try {
                    setWatchlist(JSON.parse(savedWatchlist));
                } catch (e) { }
            }
        }
    }, [isOpen]);

    if (!isOpen) return null;

    const handleAddSymbol = () => {
        if (newSymbol.trim() && !watchlist.includes(newSymbol.trim())) {
            setWatchlist([...watchlist, newSymbol.trim()]);
            setNewSymbol('');
        }
    };

    const handleRemoveSymbol = (symbol: string) => {
        setWatchlist(watchlist.filter(s => s !== symbol));
    };

    const handleSave = async () => {
        // Save to browser storage
        localStorage.setItem('gemini_api_key', apiKey);
        localStorage.setItem('sim_balance', balance);
        localStorage.setItem('ai_temp', temperature);
        localStorage.setItem('schedule_interval', intervalMin);
        localStorage.setItem('user_watchlist', JSON.stringify(watchlist));
        
        // Push to backend
        try {
            await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ gemini_key: apiKey })
            });
            alert('設定已儲存並同步至系統');
        } catch (e) {
            alert('設定已儲存 (前端)，但同步至後端失敗');
        }
        onClose();
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="panel w-full max-w-2xl bg-panel border-white/10 shadow-2xl flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="flex items-center justify-between p-5 border-b border-white/5">
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <span className="text-brand-500">⚙️</span> 系統設定
                    </h2>
                    <button onClick={onClose} className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 overflow-y-auto space-y-6">

                    {/* Section 1: API Key */}
                    <div className="space-y-3">
                        <label className="text-sm font-medium text-gray-300 flex items-center justify-between">
                            <span>🔑 Gemini API Key</span>
                            <a href="#" className="text-brand-400 hover:text-brand-300 text-xs">取得免費 API Key →</a>
                        </label>
                        <input
                            type="password"
                            placeholder="AIzaSy..."
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 text-white placeholder:text-gray-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-all font-mono"
                        />
                        <p className="text-xs text-gray-500 flex items-center gap-1">
                            <span>🔒</span> API Key 僅儲存在您的瀏覽器中，不會傳送到我們的伺服器
                        </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        {/* Section 2: 初始模擬資金 */}
                        <div className="space-y-3">
                            <label className="text-sm font-medium text-gray-300">💰 初始模擬資金 (元)</label>
                            <input
                                type="number"
                                value={balance}
                                onChange={(e) => setBalance(e.target.value)}
                                className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-brand-500 transition-all"
                            />
                        </div>
                        {/* Section 3: AI 溫度 */}
                        <div className="space-y-3">
                            <label className="text-sm font-medium text-gray-300">🌡️ AI 溫度 (0.0-1.0)</label>
                            <input
                                type="number"
                                step="0.1"
                                value={temperature}
                                onChange={(e) => setTemperature(e.target.value)}
                                className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-brand-500 transition-all"
                            />
                        </div>
                    </div>

                    {/* Section 4: 排程間隔 */}
                    <div className="space-y-3">
                        <label className="text-sm font-medium text-gray-300">⏰ 排程間隔 (分鐘)</label>
                        <input
                            type="number"
                            value={intervalMin}
                            onChange={(e) => setIntervalMin(e.target.value)}
                            className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-brand-500 transition-all"
                        />
                        <p className="text-xs text-gray-500">設定 AI 自動分析的間隔時間 (5-60 分鐘)，僅在開盤時段執行</p>
                    </div>

                    {/* Section 5: 自選觀察清單 */}
                    <div className="space-y-3">
                        <label className="text-sm font-medium text-gray-300">📑 自選觀察清單</label>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                placeholder="輸入股票代號，如 2330"
                                value={newSymbol}
                                onChange={(e) => setNewSymbol(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleAddSymbol()}
                                className="flex-1 bg-black/20 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-brand-500 transition-all"
                            />
                            <button onClick={handleAddSymbol} className="btn btn-secondary px-6">新增</button>
                        </div>
                        <div className="flex flex-wrap gap-2 pt-2">
                            {watchlist.map(symbol => (
                                <span key={symbol} className="px-3 py-1 bg-white/5 border border-white/10 rounded-md text-sm text-gray-300 flex items-center gap-2">
                                    {symbol}
                                    <button onClick={() => handleRemoveSymbol(symbol)} className="text-gray-500 hover:text-white"><X className="w-3 h-3" /></button>
                                </span>
                            ))}
                        </div>
                        <button onClick={() => setWatchlist(defaultWatchlist)} className="text-sm text-brand-400 hover:text-brand-300 border border-brand-500/30 rounded px-3 py-1.5 mt-2">恢復預設清單</button>
                        <p className="text-xs text-gray-500 mt-2">AI 會分析清單中的所有股票，也會透過搜尋自動發現清單外的標的</p>
                    </div>

                </div>

                {/* Footer */}
                <div className="p-5 border-t border-white/5 flex items-center justify-between bg-black/20">
                    <p className="text-xs text-warning flex items-center gap-1">
                        <span>⚠️</span> 修改初始資金將重置所有模擬資料
                    </p>
                    <div className="flex gap-3">
                        <button onClick={onClose} className="btn btn-secondary">取消</button>
                        <button onClick={handleSave} className="btn btn-primary">儲存設定</button>
                    </div>
                </div>

            </div>
        </div>
    );
}
