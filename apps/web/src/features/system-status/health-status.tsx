import { Notice } from "@/components/presentation";
import type { ApiAvailability } from "@/lib/api-health";

type HealthStatusProps = {
  availability: ApiAvailability;
};

export function HealthStatus({ availability }: HealthStatusProps) {
  if (availability.available) return null;

  return (
    <Notice kind="error" role="alert" title="API unavailable">
      <p>
        The web app is running, but the backend is not connected. Start the API and refresh this
        page. <span className="status-detail">{availability.reason}</span>
      </p>
    </Notice>
  );
}
