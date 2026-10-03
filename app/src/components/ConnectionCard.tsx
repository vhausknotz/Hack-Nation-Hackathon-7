import { Link } from "react-router-dom";
import { categoryLabel } from "../lib/format";
import { routes } from "../lib/links";
import { connectionPanel, topReasons } from "../lib/reasons";
import type { ConditionBundle, Neighbor } from "../lib/types";
import { useEvidence } from "./EvidenceDrawer";
import { GeneChip, Meter } from "./ui";

// Display scales: the 99th percentile of each similarity across the atlas (see data/build/report.json).
const SYMPTOM_SCALE = 0.74;
const MACHINERY_SCALE = 0.95;

export function ConnectionCard({ c, n, selected, onSelect }: { c: ConditionBundle; n: Neighbor; selected: boolean; onSelect: () => void }) {
  const openEvidence = useEvidence();
  const reasons = topReasons(n, c.gene.symbol, c.dict);
  return (
    <article
      onClick={onSelect}
      className={`card group flex cursor-pointer flex-col gap-3 p-4 transition ${selected ? "border-machinery shadow-md ring-1 ring-machinery/30" : "hover:border-ink-faint hover:shadow-sm"}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to={routes.condition(n.id)} onClick={(e) => e.stopPropagation()} className="font-medium leading-snug hover:text-machinery">
            {n.name}
          </Link>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-ink-soft">
            <GeneChip symbol={n.gene} />
            <span>{categoryLabel(n.category)}</span>
          </div>
        </div>
      </div>
      <div className="space-y-1">
        <Meter tone="symptom" label="Symptoms" value={n.sym / SYMPTOM_SCALE} />
        <Meter tone="machinery" label="Machinery" value={Math.min(n.mech, 0.999) / MACHINERY_SCALE} />
      </div>
      <ul className="space-y-1.5 text-[13px] leading-snug">
        {reasons.map((r, i) => (
          <li key={i} className="flex gap-2">
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${r.kind === "symptom" ? "bg-symptom" : r.kind === "gene" ? "bg-ink" : "bg-machinery"}`} />
            <span>{r.text}</span>
          </li>
        ))}
      </ul>
      <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
        {n.effect === "different" && <Tag tone="caution" title="The two conditions are curated with different variant effects.">Different variant effect</Tag>}
        {n.effect === "same" && <Tag tone="ok" title="Both conditions are curated with the same variant effect.">Same variant effect</Tag>}
        {!n.same_category && <Tag tone="caution" title="They affect different body systems.">Different body system</Tag>}
        <button
          onClick={(e) => {
            e.stopPropagation();
            openEvidence(connectionPanel(c, n));
          }}
          className="ml-auto text-xs font-medium text-hypothesis hover:underline"
        >
          Evidence →
        </button>
      </div>
    </article>
  );
}

function Tag({ children, tone, title }: { children: string; tone: "caution" | "ok"; title: string }) {
  return (
    <span title={title} className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${tone === "caution" ? "bg-caution-soft text-caution" : "bg-symptom-soft text-symptom"}`}>
      {children}
    </span>
  );
}
