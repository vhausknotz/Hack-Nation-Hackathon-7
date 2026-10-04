import { Link, Outlet, useLocation } from "react-router-dom";
import { SearchBox } from "./SearchBox";

export function Logo({ compact = false, iconOnly = false }: { compact?: boolean; iconOnly?: boolean }) {
  return (
    <Link to="/" className="flex shrink-0 items-center gap-2.5 font-semibold tracking-tight" aria-label="Rare Disease Atlas home">
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <path d="M16 16L6 8M16 16L27 10M16 16L24 26M6 8L27 10" stroke="#94a3b8" strokeWidth="1.2" fill="none" />
        <circle cx="16" cy="16" r="5" fill="#4f46e5" />
        <circle cx="6" cy="8" r="2.5" fill="#0d9488" />
        <circle cx="27" cy="10" r="2.5" fill="#94a3b8" />
        <circle cx="24" cy="26" r="2.5" fill="#94a3b8" />
      </svg>
      {!iconOnly && <span className={`whitespace-nowrap ${compact ? "hidden sm:inline" : ""}`}>Rare Disease Atlas</span>}
    </Link>
  );
}

export function Layout() {
  const { pathname } = useLocation();
  const home = pathname === "/";
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-ink-line/70 bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-5">
          <Logo compact={!home} />
          {!home && (
            <div className="ml-auto w-full max-w-md">
              <SearchBox size="sm" />
            </div>
          )}
          {home && (
            <nav className="ml-auto flex gap-5 text-sm text-ink-soft">
              <Link to="/agents" className="hover:text-ink">
                For agents
              </Link>
              <Link to="/about" className="hover:text-ink">
                How it works
              </Link>
            </nav>
          )}
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-5">
        <Outlet />
      </main>
      <footer className="mt-16 border-t border-ink-line bg-ink-wash">
        <div className="mx-auto grid max-w-6xl gap-6 px-5 py-10 text-sm text-ink-soft md:grid-cols-3">
          <div>
            <Logo />
            <p className="mt-3 leading-relaxed">An evidence-backed map of monogenic rare diseases, built for patient groups and researchers. Every link shows where it comes from.</p>
          </div>
          <div>
            <div className="eyebrow mb-2">Built on open data</div>
            <p className="leading-relaxed">MONDO · HPO · Orphanet · Gene2Phenotype · GenCC · ClinGen · HGNC · Complex Portal · Reactome · Gene Ontology · STRING</p>
            <Link to="/about" className="link mt-2 inline-block">
              Sources and methods
            </Link>
          </div>
          <div>
            <div className="eyebrow mb-2">Please note</div>
            <p className="leading-relaxed">A research-coordination tool, not medical advice. Computed connections are hypotheses for experts to check.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
