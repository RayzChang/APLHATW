import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import api from '../../api/axiosConfig';

interface NavbarProps {
    onSettingsClick: () => void;
}

export function Navbar({ onSettingsClick }: NavbarProps) {
    const [taiex, setTaiex] = useState({ index: 0, change: 0, change_pct: 0 });
    const [marketStatus, setMarketStatus] = useState({ is_open: false, message: '載入中...' });

    useEffect(() => {
        const fetchMarketData = async () => {
            try {
                const indexRes = await api.get('/api/market/index');
                if (indexRes.data && indexRes.data.index) {
                    setTaiex({ 
                        index: indexRes.data.index, 
                        change: indexRes.data.change,
                        change_pct: indexRes.data.change_pct
                    });
                }
                const statusRes = await api.get('/api/market/status');
                if (statusRes.data) {
                    setMarketStatus(statusRes.data);
                }
            } catch (error) {
                console.error("Failed to fetch market data", error);
            }
        };

        fetchMarketData();
        const interval = setInterval(fetchMarketData, 5000);
        return () => clearInterval(interval);
    }, []);

    const navLinkClass = ({ isActive }: { isActive: boolean }) => 
        `px-6 py-2 rounded-lg text-sm font-bold transition-all duration-300 flex items-center gap-2 ${
            isActive 
            ? 'bg-brand-primary/10 text-brand-primary shadow-[0_0_15px_rgba(99,102,241,0.2)] border border-brand-primary/30' 
            : 'text-text-muted hover:text-text-main hover:bg-white/5'
        }`;

    return (
        <nav className="h-20 border-b border-card-border bg-bg-main/80 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-50">
            {/* Left: Logo */}
            <div className="flex items-center gap-3">
                <div className="relative group">
                    <img src="/logo.png" alt="AlphaTW" className="h-10 w-auto object-contain drop-shadow-[0_0_10px_rgba(99,102,241,0.5)] transition-transform group-hover:scale-110" />
                </div>
                <div className="flex flex-col">
                    <span className="text-xl font-black tracking-tighter text-text-main">
                        Alpha<span className="text-brand-primary">TW</span>
                    </span>
                    <span className="text-[10px] uppercase tracking-widest text-brand-primary/60 font-bold">Terminal v2.0</span>
                </div>
            </div>

            {/* Center: Navigation Group */}
            <div className="flex items-center bg-black/20 rounded-xl p-1 border border-white/5">
                <NavLink to="/" className={navLinkClass}>
                    交易平台
                </NavLink>
                <NavLink to="/picker" className={navLinkClass}>
                    選股器
                </NavLink>
                <button 
                    onClick={onSettingsClick}
                    className="px-6 py-2 rounded-lg text-sm font-bold text-text-muted hover:text-text-main hover:bg-white/5 transition-all"
                >
                    系統設定
                </button>
            </div>

            {/* Right: TAIEX Cluster */}
            <div className="flex items-center gap-8">
                <div className="flex flex-col items-end">
                    <span className="text-[10px] font-bold text-text-muted uppercase tracking-wider mb-0.5">加權指數</span>
                    <div className="flex items-baseline gap-3">
                        <span className="text-2xl font-black font-mono text-text-main leading-none">
                            {taiex.index?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </span>
                        <div className={`flex flex-col items-end leading-tight ${taiex.change >= 0 ? 'text-danger' : 'text-success'}`}>
                            <span className="text-xs font-bold font-mono">
                                {taiex.change >= 0 ? '▲' : '▼'} {Math.abs(taiex.change).toFixed(2)}
                            </span>
                            <span className="text-[10px] font-bold font-mono">
                                ({taiex.change_pct >= 0 ? '+' : ''}{taiex.change_pct}%)
                            </span>
                        </div>
                    </div>
                </div>

                <div className="h-10 w-[1px] bg-white/10" />

                <div className="flex items-center gap-2 bg-white/5 px-3 py-1.5 rounded-lg border border-white/5">
                    <span className={`w-2 h-2 rounded-full ${marketStatus.is_open ? 'bg-success shadow-[0_0_8px_#10b981]' : 'bg-text-muted'} ${marketStatus.is_open ? 'animate-pulse' : ''}`} />
                    <span className={`text-xs font-bold ${marketStatus.is_open ? 'text-success' : 'text-text-muted'}`}>
                        {marketStatus.message}
                    </span>
                </div>
            </div>
        </nav>
    );
}
