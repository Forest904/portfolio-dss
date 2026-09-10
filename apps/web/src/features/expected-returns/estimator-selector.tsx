import { useId } from "react";
import type { EstimatorId } from "./types";

export const estimatorLabels = {
  historical_mean: "Historical mean",
  simple_forecast: "Simple forecast (recent returns weighted more)",
};

export function EstimatorSelector({ value, onChange }: { value: EstimatorId; onChange: (value: EstimatorId) => void }) {
  const description = useId();
  return <fieldset><legend>Expected-return model</legend>
    <label>Estimator <select value={value} aria-describedby={description} onChange={(e) => onChange(e.target.value as EstimatorId)}>
      {Object.entries(estimatorLabels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
    </select></label>
    <p className="fine-print" id={description}>Historical mean weights every observation equally. Simple forecast gives recent daily returns more weight, with a fixed 63-trading-observation half-life. Neither guarantees future returns. Risk still uses historical covariance.</p>
  </fieldset>;
}
