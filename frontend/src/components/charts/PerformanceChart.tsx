import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

interface PerformanceData {
    date: string;
    equity: number;
    benchmark: number;
}

interface PerformanceChartProps {
    data: PerformanceData[];
    totalProfitPct?: number;
}

export function PerformanceChart({ data, totalProfitPct = 0 }: PerformanceChartProps) {
    let normalizedData: any[] = [];

    if (!data || data.length <= 1) {
        // Render a flatline if there's no real curve yet
        const today = new Date().toLocaleDateString('zh-TW', { month: '2-digit', day: '2-digit' });
        
        normalizedData = [
            { date: '起始', equityPct: 1, benchmarkPct: 1 },
            { date: today, equityPct: 1, benchmarkPct: 1 }
        ];
    } else {
        const initialEquity = data[0].equity || 1;
        const initialBenchmark = data[0].benchmark || 1;

        normalizedData = data.map((d) => ({
            ...d,
            // normalize to 1.0 = 100%, protect against division by zero
            equityPct: initialEquity !== 0 ? d.equity / initialEquity : 1,
            benchmarkPct: initialBenchmark !== 0 ? d.benchmark / initialBenchmark : 1,
        }));
    }

    return (
        <div className="w-full h-full flex flex-col">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <span className="text-brand-400">📈</span> 績效走勢
                </h3>
                <div className={`text-sm font-black px-3 py-1 rounded-full border ${
                    totalProfitPct > 0 ? 'bg-danger/20 text-danger border-danger/20' : 
                    totalProfitPct < 0 ? 'bg-success/20 text-success border-success/20' : 
                    'bg-white/10 text-text-muted border-white/10'
                }`}>
                    {totalProfitPct > 0 ? '+' : ''}{totalProfitPct === 0 ? '0.00' : totalProfitPct.toFixed(2)}%
                </div>
            </div>
            <div className="h-[320px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={normalizedData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
                        <XAxis
                            dataKey="date"
                            stroke="#6b7280"
                            fontSize={12}
                            tickLine={false}
                            axisLine={false}
                            minTickGap={30}
                        />
                        <YAxis
                            stroke="#6b7280"
                            fontSize={12}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(value) => `${(value * 100 - 100).toFixed(0)}%`}
                            domain={[(dataMin: number) => Math.min(dataMin, 0.95), (dataMax: number) => Math.max(dataMax, 1.05)]}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#1a1e29', borderColor: '#ffffff20', color: '#fff' }}
                            itemStyle={{ color: '#fff' }}
                            formatter={(value: any, name: any) => {
                                if (name === '總資產') return [`${(value * 100 - 100).toFixed(2)}%`, name];
                                if (name === '0050 基準') return [`${(value * 100 - 100).toFixed(2)}%`, name];
                                return [value, name];
                            }}
                            labelStyle={{ color: '#9ca3af' }}
                        />
                        <Legend verticalAlign="top" height={36} iconType="circle" />
                        <Line
                            type="monotone"
                            dataKey="equityPct"
                            name="總資產"
                            stroke="#3b82f6"
                            strokeWidth={2}
                            dot={false}
                        />
                        <Line
                            type="monotone"
                            dataKey="benchmarkPct"
                            name="0050 基準"
                            stroke="#f59e0b"
                            strokeWidth={2}
                            strokeDasharray="5 5"
                            dot={false}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
