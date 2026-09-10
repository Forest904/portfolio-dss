import type { AnalysisSeriesPoint } from "./types";

type SeriesKey = "current" | "equal_weight" | "sp500_proxy";

const series: { key: SeriesKey; label: string; color: string }[] = [
  { key: "current", label: "Current portfolio", color: "#236449" },
  { key: "equal_weight", label: "Equal-weight portfolio", color: "#b06a26" },
  { key: "sp500_proxy", label: "S&P 500 (SPY ETF proxy)", color: "#426a8c" },
];
const axisPercent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 0 });

export function PerformanceChart({ points }: { points: AnalysisSeriesPoint[] }) {
  const width = 760;
  const height = 320;
  const left = 70, right = 24, top = 24, bottom = 54;
  const values = points.flatMap((point) => series.map(({ key }) => point[key].cumulative_return));
  const minimum = Math.min(0, ...values);
  const maximum = Math.max(0, ...values);
  const span = maximum - minimum || 1;
  const x = (index: number) => left + (index / Math.max(1, points.length - 1)) * (width - left - right);
  const y = (value: number) => height - bottom - ((value - minimum) / span) * (height - top - bottom);
  const tickIndexes = [0, Math.floor((points.length - 1) / 2), Math.max(0, points.length - 1)];

  return (
    <figure className="chart-card" aria-labelledby="performance-chart-title">
      <figcaption>
        <p className="eyebrow">Observed growth</p>
        <h3 id="performance-chart-title">Cumulative return comparison</h3>
      </figcaption>
      <div className="performance-chart-scroll" role="region" aria-label="Historical return chart, scroll horizontally" tabIndex={0}><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Cumulative historical returns with percentage and date axes">
        {[0, 1, 2, 3, 4].map((index) => { const value = minimum + index / 4 * span; return <g key={index} className="chart-tick"><line x1={left} x2={width - right} y1={y(value)} y2={y(value)} /><text x={left - 10} y={y(value) + 4} textAnchor="end">{axisPercent.format(value)}</text></g>; })}
        <line x1={left} x2={width - right} y1={y(0)} y2={y(0)} className="chart-zero" />
        {series.map(({ key, label, color }) => (
          <polyline
            key={key}
            aria-label={label}
            points={points.map((point, index) => `${x(index)},${y(point[key].cumulative_return)}`).join(" ")}
            fill="none"
            stroke={color}
            strokeWidth="3"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {tickIndexes.map((index) => <text key={index} x={x(index)} y={height - 24} textAnchor={index === 0 ? "start" : index === points.length - 1 ? "end" : "middle"}>{points[index]?.date}</text>)}
        <text x={(left + width - right) / 2} y={height - 4} textAnchor="middle">Observation date</text>
        <text transform={`translate(18 ${(top + height - bottom) / 2}) rotate(-90)`} textAnchor="middle">Cumulative return (%)</text>
      </svg></div>
      <div className="chart-legend">
        {series.map((item) => (
          <span key={item.key}><i style={{ background: item.color }} />{item.label}</span>
        ))}
      </div>
      <p className="chart-axis-copy">{points[0]?.date} to {points.at(-1)?.date}</p>
    </figure>
  );
}
