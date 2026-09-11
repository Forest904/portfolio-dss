import { PortfolioWorkspace } from "@/features/guided-builder/guided-builder";
import { HealthStatus } from "@/features/system-status/health-status";
import { checkApiHealth } from "@/lib/api-health";

export const dynamic = "force-dynamic";

export default async function Home() {
  const availability = await checkApiHealth();

  return (
    <main>
      <div className="page-shell">
        <header className="site-header">
          <a className="brand" href="#top" aria-label="Portfolio DSS home">
            <span className="brand-mark" aria-hidden="true">PD</span>
            <span>Portfolio DSS</span>
          </a>
          <span className="header-context">Decision support · USD portfolios</span>
        </header>

        <section className="hero" id="top">
          <p className="product-mark">Understand · Compare · Decide</p>
          <h1>Make portfolio trade-offs easier to understand.</h1>
          <p className="hero-copy">
            Compare return, risk, and uncertainty without treating estimates as guarantees.
          </p>
        </section>

        <HealthStatus availability={availability} />
        <PortfolioWorkspace />

        <footer>
          <p><strong>Portfolio DSS</strong> helps you understand, compare, and decide with assumptions visible.</p>
          <p>Educational decision support—not trading automation or financial advice.</p>
        </footer>
      </div>
    </main>
  );
}
