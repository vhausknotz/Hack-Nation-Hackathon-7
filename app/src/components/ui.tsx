import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export type Tier = "data" | "hypothesis" | "proof";

const TIER: Record<Tier, { label: string; className: string; line: string; help: string }> = {
  data: {
    label: "Data",
    className: "bg-ink-wash text-ink-soft border-ink-line",
    line: "border-ink-soft border-solid",
    help: "Observed: recorded in a curated database or reported in a paper.",
  },
  hypothesis: {
    label: "Hypothesis",
    className: "bg-hypothesis-soft text-hypothesis border-hypothesis/20",
    line: "border-hypothesis border-dashed",
    help: "Inferred by the atlas from the data. A lead to check, not a finding.",
  },
  proof: {
    label: "Clinical proof",
    className: "bg-proof-soft text-proof border-proof/20",
    line: "border-proof border-solid",
    help: "Shown in a clinical trial or an approval.",
  },
};

export function TierBadge({ tier }: { tier: Tier }) {
  const t = TIER[tier];
  return (
    <span title={t.help} className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium ${t.className}`}>
      <span className={`inline-block w-3 border-t-2 ${t.line}`} />
      {t.label}
    </span>
  );
}

export function TierLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-soft">
      {(Object.keys(TIER) as Tier[]).map((t) => (
        <span key={t} className="inline-flex items-center gap-2" title={TIER[t].help}>
          <span className={`inline-block w-5 border-t-2 ${TIER[t].line}`} />
          {TIER[t].label}
          <span className="hidden text-ink-faint sm:inline">— {TIER[t].help.split(":")[0].split(".")[0]}</span>
        </span>
      ))}
    </div>
  );
}

export function Chip({ children, to, tone = "neutral", title }: { children: ReactNode; to?: string; tone?: "neutral" | "symptom" | "machinery" | "caution"; title?: string }) {
  const tones = {
    neutral: "border-ink-line bg-white text-ink hover:border-ink-faint",
    symptom: "border-symptom/20 bg-symptom-soft/60 text-symptom hover:border-symptom/50",
    machinery: "border-machinery/20 bg-machinery-soft/60 text-machinery hover:border-machinery/50",
    caution: "border-caution/20 bg-caution-soft/60 text-caution",
  };
  const cls = `inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors ${tones[tone]}`;
  return to ? (
    <Link to={to} className={cls} title={title}>
      {children}
    </Link>
  ) : (
    <span className={cls} title={title}>
      {children}
    </span>
  );
}

export function GeneChip({ symbol }: { symbol: string }) {
  return (
    <Link
      to={`/g/${encodeURIComponent(symbol)}`}
      className="inline-flex items-center rounded-md bg-ink px-1.5 py-0.5 font-mono text-[11px] font-semibold tracking-wide text-white hover:bg-machinery"
      title={`Gene ${symbol}`}
    >
      {symbol}
    </Link>
  );
}

export function Section({ id, eyebrow, title, intro, children, aside }: { id?: string; eyebrow?: string; title: string; intro?: ReactNode; children: ReactNode; aside?: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24 border-t border-ink-line py-10">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl">
          {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
          <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
          {intro && <p className="mt-2 text-[15px] leading-relaxed text-ink-soft">{intro}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function Meter({ value, tone, label }: { value: number; tone: "symptom" | "machinery"; label: string }) {
  const pct = Math.max(4, Math.min(100, value * 100));
  return (
    <div className="flex items-center gap-2 text-[11px] text-ink-soft" title={`${label}: ${Math.round(value * 100)} / 100`}>
      <span className="w-16 shrink-0">{label}</span>
      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-ink-line">
        <span className={`block h-full rounded-full ${tone === "symptom" ? "bg-symptom" : "bg-machinery"}`} style={{ width: `${pct}%` }} />
      </span>
    </div>
  );
}

export function ExternalLink({ href, children, className = "" }: { href: string; children: ReactNode; className?: string }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className={`link ${className}`}>
      {children}
      <span aria-hidden className="ml-0.5 text-[0.8em]">↗</span>
    </a>
  );
}

export function Loading({ what = "Loading" }: { what?: string }) {
  return (
    <div className="flex items-center gap-3 py-24 text-ink-soft" role="status">
      <span className="h-2 w-2 animate-ping rounded-full bg-machinery" />
      {what}…
    </div>
  );
}

export function NotFoundBox({ what }: { what: string }) {
  return (
    <div className="py-24">
      <h1 className="text-2xl font-semibold">Not in the atlas</h1>
      <p className="mt-2 text-ink-soft">We couldn't find {what}. Try searching by gene, condition name or symptom.</p>
      <Link to="/" className="link mt-4 inline-block">
        Back to search
      </Link>
    </div>
  );
}
