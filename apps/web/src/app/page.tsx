import { HealthStatus } from "@/features/system-status/health-status";
import { checkApiHealth } from "@/lib/api-health";

export const dynamic = "force-dynamic";

export default async function Home() {
  const availability = await checkApiHealth();

  return (
    <main>
      <div className="page-shell">
        <header className="hero">
          <p className="product-mark">Portfolio DSS</p>
          <h1>Make portfolio trade-offs easier to understand.</h1>
          <p className="hero-copy">
            A decision support system for comparing return, risk, and uncertainty—without pretending
            forecasts are guarantees.
          </p>
        </header>

        <HealthStatus availability={availability} />

        <section className="principles" aria-label="Product principles">
          <article>
            <span>01</span>
            <h2>Understand</h2>
            <p>See what a portfolio owns and where its risks are concentrated.</p>
          </article>
          <article>
            <span>02</span>
            <h2>Compare</h2>
            <p>Put current and alternative allocations on equal footing.</p>
          </article>
          <article>
            <span>03</span>
            <h2>Decide</h2>
            <p>Make assumptions and uncertainty visible before acting.</p>
          </article>
        </section>

        <footer>Educational decision support—not trading automation or financial advice.</footer>
      </div>
    </main>
  );
}
