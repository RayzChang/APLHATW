interface TopCardsProps {
    totalAssets: number;
    availableCash: number;
    holdingValue: number;
    totalTrades: number;
    winRate: number;
    initialAssets: number;
}

export function TopCards({
    totalAssets,
    availableCash,
    holdingValue,
    totalTrades,
    winRate,
    initialAssets,
}: TopCardsProps) {
    const profit = totalAssets - initialAssets;
    const profitPercent = (profit / initialAssets) * 100;
    const cashPct = (totalAssets && totalAssets > 0)
        ? ((availableCash / totalAssets) * 100).toFixed(1) + '%'
        : '－';

    return (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="panel p-5">
                <h3 className="text-sm font-medium text-gray-400 mb-1">總資產</h3>
                <p className="text-2xl font-bold text-white mb-2">
                    ${totalAssets.toLocaleString()}
                </p>
                <p className="text-sm text-gray-500 flex items-center gap-2">
                    初始投入 ${initialAssets.toLocaleString()}
                    <span className={profit >= 0 ? 'text-success' : 'text-danger'}>
                        ({profit > 0 ? '+' : ''}{profitPercent.toFixed(1)}%)
                    </span>
                </p>
            </div>

            <div className="panel p-5">
                <h3 className="text-sm font-medium text-gray-400 mb-1">可用現金</h3>
                <p className="text-2xl font-bold text-white mb-2">
                    ${availableCash.toLocaleString()}
                </p>
                <p className="text-sm text-gray-500">
                    佔總資產 {cashPct}
                </p>
            </div>

            <div className="panel p-5">
                <h3 className="text-sm font-medium text-gray-400 mb-1">持股市值</h3>
                <p className="text-2xl font-bold text-white mb-2">
                    ${holdingValue.toLocaleString()}
                </p>
                <p className="text-sm text-gray-500">
                    成本 $0 (0.00%)
                </p>
            </div>

            <div className="panel p-5">
                <h3 className="text-sm font-medium text-gray-400 mb-1">總交易次數</h3>
                <p className="text-2xl font-bold text-white mb-2">{totalTrades}</p>
                <p className="text-sm text-gray-500">勝率 {winRate.toFixed(1)}%</p>
            </div>
        </div>
    );
}
