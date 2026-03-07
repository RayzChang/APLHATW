import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Settings } from 'lucide-react';

interface NavbarProps {
    onSettingsClick: () => void;
}

export function Navbar({ onSettingsClick }: NavbarProps) {
    const [taiex, setTaiex] = useState({ index: 0, change: 0 });
    const [isMarketOpen, setIsMarketOpen] = useState(false);

    const checkMarketOpen = () => {
        const now = new Date();
        const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
        const twTime = new Date(utc + (3600000 * 8));
        const day = twTime.getDay();
        const timeVal = twTime.getHours() * 100 + twTime.getMinutes();
        
        if (day === 0 || day === 6) return false;
        if (timeVal >= 900 && timeVal <= 1330) return true;
        return false;
    };

    useEffect(() => {
        const fetchTaiex = async () => {
            try {
                const response = await fetch('/api/index');
                if (response.ok) {
                    const data = await response.json();
                    if (data.index !== null) {
                        setTaiex({ index: data.index, change: data.change });
                        setIsMarketOpen(checkMarketOpen());
                    }
                }
            } catch (error) {
                console.error("Failed to fetch TAIEX", error);
            }
        };

        fetchTaiex();
        const interval = setInterval(fetchTaiex, 5000);
        return () => clearInterval(interval);
    }, []);

    const hasApiKey = !!localStorage.getItem('gemini_api_key');

    return (
        <nav className="h-16 border-b border-white/10 bg-panel px-6 flex items-center justify-between sticky top-0 z-50">
            <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                    <img src="/logo.png" alt="AlphaTW" className="h-8 w-auto object-contain drop-shadow-[0_0_8px_rgba(0,240,255,0.6)]" />
                    <span className="text-xl font-bold bg-gradient-to-r from-brand-400 to-indigo-400 bg-clip-text text-transparent transform translate-y-[2px]">
                        AlphaTW <span className="text-xs bg-brand-600/30 text-brand-300 px-2 py-0.5 rounded ml-2">WEB</span>
                    </span>
                </div>

                <div className="flex items-center gap-4 text-sm transform translate-y-[2px]">
                    <div className="flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${isMarketOpen ? 'bg-success' : 'bg-gray-500'} animate-pulse`} />
                        <span className={isMarketOpen ? 'text-success' : 'text-gray-400'}>
                            {isMarketOpen ? '市場開盤中' : '市場已收盤'}
                        </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${hasApiKey ? 'bg-success' : 'bg-danger'}`} />
                        <span className={hasApiKey ? "text-success" : "text-gray-400"}>
                            {hasApiKey ? 'API 已連線' : '未設定 API Key'}
                        </span>
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-4">
            <div className="flex bg-black/30 rounded-lg p-1">
                    <NavLink 
                        to="/" 
                        className={({ isActive }) => 
                            `px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${isActive ? 'bg-brand-600/20 text-brand-400' : 'text-gray-400 hover:text-gray-200'}`
                        }
                    >
                        交易平台
                    </NavLink>
                    <NavLink 
                        to="/picker" 
                        className={({ isActive }) => 
                            `px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${isActive ? 'bg-brand-600/20 text-brand-400' : 'text-gray-400 hover:text-gray-200'}`
                        }
                    >
                        選股器
                    </NavLink>
                </div>

                <button onClick={onSettingsClick} className="btn bg-white/5 hover:bg-white/10 border border-white/5 text-gray-200 gap-2">
                    <Settings className="h-4 w-4" />
                    設定
                </button>

                <div className="flex items-center gap-3 bg-black/40 border border-white/5 rounded-lg px-4 py-2">
                    <span className="text-sm text-gray-400">加權指數</span>
                    <span className="font-mono font-bold text-white">{taiex.index?.toLocaleString()}</span>
                    <span className={`text-sm font-mono ${taiex.change === null ? 'text-gray-400' : (taiex.change >= 0 ? 'text-success' : 'text-danger')}`}>
                        {taiex.change === null ? '' : (taiex.change > 0 ? '+' : '')}{taiex.change === null ? '0.00' : taiex.change}%
                    </span>
                </div>
            </div>
        </nav>
    );
}
