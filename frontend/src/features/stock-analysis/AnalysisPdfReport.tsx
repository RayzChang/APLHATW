import ReactMarkdown from 'react-markdown';
import type { AnalysisResult } from '../../types/analysis';

interface AnalysisPdfReportProps {
  result: AnalysisResult;
  generatedAt: string;
}

const pageStyle: React.CSSProperties = {
  width: '794px',
  background: '#f8fafc',
  color: '#0f172a',
  padding: '40px',
  fontFamily: '"Noto Sans TC", "Microsoft JhengHei", sans-serif',
};

const cardStyle: React.CSSProperties = {
  background: '#ffffff',
  border: '1px solid #e2e8f0',
  borderRadius: '18px',
  padding: '20px',
  boxShadow: '0 10px 30px rgba(15, 23, 42, 0.06)',
};

const reportStyle: React.CSSProperties = {
  ...cardStyle,
  marginTop: '18px',
};

function formatCurrency(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }

  return `$${value.toLocaleString()}`;
}

function formatPercent(value?: number | null, multiply = false) {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return '--';
  }

  const normalized = multiply ? value * 100 : value;
  return `${normalized.toFixed(1)}%`;
}

function ReportMarkdown({ content }: { content?: string }) {
  if (!content) {
    return <p style={{ color: '#64748b', lineHeight: 1.7 }}>暫無資料</p>;
  }

  return (
    <ReactMarkdown
      components={{
        h1: ({ ...props }) => <h1 style={{ fontSize: '24px', fontWeight: 800, marginBottom: '12px' }} {...props} />,
        h2: ({ ...props }) => <h2 style={{ fontSize: '20px', fontWeight: 800, marginBottom: '10px' }} {...props} />,
        h3: ({ ...props }) => <h3 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '8px' }} {...props} />,
        p: ({ ...props }) => <p style={{ color: '#334155', lineHeight: 1.8, marginBottom: '10px' }} {...props} />,
        ul: ({ ...props }) => <ul style={{ paddingLeft: '20px', color: '#334155', lineHeight: 1.8, marginBottom: '10px' }} {...props} />,
        li: ({ ...props }) => <li style={{ marginBottom: '6px' }} {...props} />,
        strong: ({ ...props }) => <strong style={{ color: '#0f172a', fontWeight: 800 }} {...props} />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

export function AnalysisPdfReport({ result, generatedAt }: AnalysisPdfReportProps) {
  const decision = result.decision;

  return (
    <div style={pageStyle}>
      <div style={{ ...cardStyle, background: 'linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%)', color: '#f8fafc' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '20px', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontSize: '13px', letterSpacing: '0.2em', textTransform: 'uppercase', opacity: 0.72, marginBottom: '12px' }}>
              AlphaTW AI Stock Report
            </div>
            <h1 style={{ fontSize: '40px', margin: 0, fontWeight: 900 }}>{result.name || result.symbol}</h1>
            <div style={{ marginTop: '10px', fontSize: '18px', opacity: 0.92 }}>
              {result.symbol} | 即時價格 {formatCurrency(result.current_price)}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div
              style={{
                display: 'inline-block',
                padding: '10px 18px',
                borderRadius: '999px',
                background: 'rgba(255,255,255,0.12)',
                border: '1px solid rgba(255,255,255,0.2)',
                fontSize: '14px',
                fontWeight: 800,
                letterSpacing: '0.16em',
              }}
            >
              {decision?.action || 'HOLD'}
            </div>
            <div style={{ marginTop: '18px', fontSize: '13px', opacity: 0.8 }}>分析時間</div>
            <div style={{ marginTop: '6px', fontSize: '16px', fontWeight: 700 }}>{generatedAt}</div>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginTop: '18px' }}>
        <div style={cardStyle}>
          <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 700, marginBottom: '8px' }}>AI 信心度</div>
          <div style={{ fontSize: '30px', fontWeight: 900 }}>{formatPercent(decision?.confidence, true)}</div>
        </div>
        <div style={cardStyle}>
          <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 700, marginBottom: '8px' }}>建議倉位</div>
          <div style={{ fontSize: '30px', fontWeight: 900 }}>{formatPercent(decision?.position_size_pct)}</div>
        </div>
        <div style={cardStyle}>
          <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 700, marginBottom: '8px' }}>止盈目標價</div>
          <div style={{ fontSize: '30px', fontWeight: 900 }}>{formatCurrency(decision?.take_profit_price)}</div>
        </div>
        <div style={cardStyle}>
          <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 700, marginBottom: '8px' }}>止損防護價</div>
          <div style={{ fontSize: '30px', fontWeight: 900 }}>{formatCurrency(decision?.stop_loss_price)}</div>
        </div>
      </div>

      <div style={reportStyle}>
        <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 700, letterSpacing: '0.08em', marginBottom: '10px' }}>
          決策摘要
        </div>
        <div style={{ fontSize: '22px', fontWeight: 800, lineHeight: 1.6 }}>{decision?.reasoning || '目前無完整決策摘要。'}</div>
        {decision?.score_breakdown ? (
          <div style={{ marginTop: '14px', paddingTop: '14px', borderTop: '1px solid #e2e8f0', color: '#475569', lineHeight: 1.8 }}>
            {decision.score_breakdown}
          </div>
        ) : null}
      </div>

      <div style={reportStyle}>
        <div style={{ fontSize: '20px', fontWeight: 900, marginBottom: '14px' }}>技術面與趨勢動量報告</div>
        <ReportMarkdown content={result.technical_report} />
      </div>

      <div style={reportStyle}>
        <div style={{ fontSize: '20px', fontWeight: 900, marginBottom: '14px' }}>市場輿論與新聞情緒報告</div>
        <ReportMarkdown content={result.sentiment_report} />
      </div>

      <div style={reportStyle}>
        <div style={{ fontSize: '20px', fontWeight: 900, marginBottom: '14px' }}>風險與資金控管評估報告</div>
        <ReportMarkdown content={result.risk_report} />
      </div>

      <div style={{ marginTop: '20px', textAlign: 'right', fontSize: '12px', color: '#64748b' }}>
        本報告由 AlphaTW 智慧選股偵查組自動生成，僅供研究與模擬參考。
      </div>
    </div>
  );
}
