import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';

interface PerformanceData {
    date: string;
    equity: number;
    benchmark: number;
}

interface PerformanceChartProps {
    data: PerformanceData[];
}

export function PerformanceChart({ data }: PerformanceChartProps) {
    // 假設資料中的第一筆日期是基準 100%
    const initialEquity = data.length > 0 ? data[0].equity : 1;
    const initialBenchmark = data.length > 0 ? data[0].benchmark : 1;

    const normalizedData = data.map((d) => ({
        ...d,
        equityValue: d.equity,
        benchmarkValue: d.benchmark,
        // normalize to 1.0 = 100%
        equityPct: d.equity / initialEquity,
        benchmarkPct: d.benchmark / initialBenchmark,
    }));

    return (
        <div className="panel p-5 mt-4 min-h-[400px]">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <span className="text-brand-400">📈</span> 績效走勢
                </h3>
                <div className="text-xs bg-brand-500/20 text-brand-400 px-2 py-1 rounded-md">
                    {data.length > 0 ? `+${((data[data.length - 1].equity / initialEquity - 1) * 100).toFixed(2)}%` : '+0%'}
                </div>
            </div>
            <div className="h-[320px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={normalizedData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <defs>
                            <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                            </linearGradient>
                        </defs>
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
                            domain={['auto', 'auto']}
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
                        <Area
                            type="monotone"
                            dataKey="equityPct"
                            name="總資產"
                            stroke="#3b82f6"
                            strokeWidth={2}
                            fillOpacity={1}
                            fill="url(#colorEquity)"
                        />
                        <Area
                            type="monotone"
                            dataKey="benchmarkPct"
                            name="0050 基準"
                            stroke="#f59e0b"
                            strokeDasharray="5 5"
                            fill="transparent"
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
