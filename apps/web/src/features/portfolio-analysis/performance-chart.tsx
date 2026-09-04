import type { AnalysisSeriesPoint } from "./types";

type SeriesKey = "current" | "equal_weight" | "sp500_proxy";

const series: { key: SeriesKey; label: string; color: string }[] = [
  { key: "current", label: "Current portfolio", color: "#236449" },
  { key: "equal_weight", label: "Equal-weight portfolio", color: "#b06a26" },
  { key: "sp500_proxy", label: "S&P 500 (SPY ETF proxy)", color: "#426a8c" },
];

export function PerformanceChart({ points }: { points: AnalysisSeriesPoint[] }) {
  const width = 760;
  const height = 280;
  const padding = 26;
  const values = points.flatMap((point) => series.map(({ key }) => point[key].cumulative_return));
  const minimum = Math.min(0, ...values);
  const maximum = Math.max(0, ...values);
  const span = maximum - minimum || 1;
  const x = (index: number) => padding + (index / Math.max(1, points.length - 1)) * (width - 2 * padding);
  const y = (value: number) => height - padding - ((value - minimum) / span) * (height - 2 * padding);

  return (
    <figure className="chart-card" aria-labelledby="performance-chart-title">
      <figcaption>
        <p className="eyebrow">Observed growth</p>
        <h3 id="performance-chart-title">Cumulative return comparison</h3>
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Cumulative historical returns">
        <line x1={padding} x2={width - padding} y1={y(0)} y2={y(0)} className="chart-zero" />
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
      </svg>
      <div className="chart-legend">
        {series.map((item) => (
          <span key={item.key}><i style={{ background: item.color }} />{item.label}</span>
        ))}
      </div>
      <p className="chart-axis-copy">{points[0]?.date} to {points.at(-1)?.date}</p>
    </figure>
  );
}
