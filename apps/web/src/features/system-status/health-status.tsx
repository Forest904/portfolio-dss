import type { ApiAvailability } from "@/lib/api-health";

type HealthStatusProps = {
  availability: ApiAvailability;
};

export function HealthStatus({ availability }: HealthStatusProps) {
  return (
    <section className="status-card" aria-labelledby="system-status-title">
      <div className="status-heading">
        <div>
          <p className="eyebrow">Local environment</p>
          <h2 id="system-status-title">System status</h2>
        </div>
        <span
          className={availability.available ? "status status-online" : "status status-offline"}
          role="status"
        >
          <span aria-hidden="true" className="status-dot" />
          {availability.available ? "API connected" : "API unavailable"}
        </span>
      </div>

      {availability.available ? (
        <p>
          The Portfolio DSS API is ready. Running service version {availability.health.version}.
        </p>
      ) : (
        <p>
          The web app is running, but the backend is not connected. Start the API and refresh this
          page. <span className="status-detail">{availability.reason}</span>
        </p>
      )}
    </section>
  );
}
