// Variant-level evidence from ClinVar: what labs have reported for this condition, and a look-up for the
// exact variant on a family's genetic report. The per-gene list is fetched on demand from the MCP host
// (/variants/<gene>), so it never weighs down the website. Public classifications, not a diagnosis.
import { useState } from "react";
import { Link } from "react-router-dom";
import { LIVE_API } from "../lib/live";
import { routes } from "../lib/links";
import type { ConditionBundle, GeneVariants, VariantRow } from "../lib/types";

const CLASS: Record<VariantRow[3], { label: string; tone: string }> = {
  P: { label: "Disease-causing (pathogenic)", tone: "bg-rose-50 text-rose-800" },
  LP: { label: "Likely disease-causing", tone: "bg-rose-50 text-rose-700" },
  C: { label: "Labs disagree", tone: "bg-caution-soft text-caution" },
  VUS: { label: "Uncertain significance", tone: "bg-ink-wash text-ink-soft" },
  LB: { label: "Likely harmless", tone: "bg-emerald-50 text-emerald-800" },
  B: { label: "Harmless (benign)", tone: "bg-emerald-50 text-emerald-800" },
  O: { label: "Other classification", tone: "bg-ink-wash text-ink-soft" },
};
const STARS = ["no review criteria given", "one lab with criteria", "several labs agree", "expert panel", "practice guideline"];
export const TYPE_WORDS: Record<string, string> = {
  nonsense: "stop signal (nonsense)", frameshift: "frameshift", splice: "splice site", start: "start signal lost",
  missense: "one building block swapped (missense)", inframe: "small in-frame change", large: "large deletion or duplication",
  mitochondrial: "mitochondrial DNA change", intronic: "inside an intron", untranslated: "untranslated region", synonymous: "silent", other: "other",
};
const TRUNCATING = ["nonsense", "frameshift", "splice", "start", "large"];

const cache = new Map<string, Promise<GeneVariants | null>>();
function geneVariants(symbol: string) {
  if (!cache.has(symbol)) {
    cache.set(symbol, fetch(`${LIVE_API}/variants/${encodeURIComponent(symbol)}`).then(r => (r.ok ? r.json() : null)).catch(() => {
      cache.delete(symbol);
      return null;
    }));
  }
  return cache.get(symbol)!;
}

const AA: Record<string, string> = { A: "ala", R: "arg", N: "asn", D: "asp", C: "cys", Q: "gln", E: "glu", G: "gly", H: "his", I: "ile",
  L: "leu", K: "lys", M: "met", F: "phe", P: "pro", S: "ser", T: "thr", W: "trp", Y: "tyr", V: "val", X: "ter", "*": "ter" };

/** Accepts what a report or a parent might type: c.1631G>A, p.Arg544Gln, R544Q, rs12345, m.3243A>G, a ClinVar ID. */
export function matches(query: string, v: VariantRow) {
  const q = query.trim().toLowerCase().replace(/\s+/g, "").replace(/^p\.\(?/, "p.").replace(/\)$/, "");
  if (!q) return false;
  if (/^\d+$/.test(q)) return String(v[0]) === q;
  if (q.startsWith("rs")) return v[8].toLowerCase() === q;
  const hgvs = v[1].toLowerCase(), protein = v[2].toLowerCase();
  const local = hgvs.slice(hgvs.indexOf(":") + 1);
  if (local === q || hgvs === q || protein === q || protein === "p." + q) return true;
  const one = q.replace(/^p\./, "").toUpperCase().match(/^([A-Z*])(\d+)([A-Z*]|FS.*)$/);
  if (one && AA[one[1]]) {
    const tail = one[3].startsWith("FS") ? "fs" : AA[one[3]];
    return !!tail && protein.startsWith(`p.${AA[one[1]]}${one[2]}${tail}`);
  }
  return q.length >= 6 && (local.startsWith(q) || protein.startsWith(q));
}

export function VariantSection({ c }: { c: ConditionBundle }) {
  const v = c.variants;
  const gene = c.gene.symbol;
  if (!v) return null;
  const truncating = TRUNCATING.reduce((n, t) => n + (v.types[t] ?? 0), 0);
  const missense = v.types.missense ?? 0;
  const effect = c.variant_effect.value;
  let reading = "";
  if (v.plp >= 5) {
    if (effect === "loss_of_function" && truncating / v.plp >= 0.5) reading = `Most of them stop ${gene} from making its product, which fits how this condition is thought to work (loss of function).`;
    else if ((effect === "gain_of_function" || effect === "dominant_negative") && missense / v.plp >= 0.6) reading = `Most of them swap a single building block of the protein, as expected when an altered protein causes harm rather than a missing one.`;
    else if (truncating / v.plp >= 0.5) reading = `Most of them stop ${gene} from making its product.`;
    else if (missense / v.plp >= 0.6) reading = `Most of them swap a single building block of the protein (missense).`;
  }
  const types = Object.entries(v.types).slice(0, 4);
  return <div className="mt-4 rounded-xl border border-ink-line bg-white p-3 text-xs">
    <h3 className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Variants reported by genetic labs</h3>
    {v.plp > 0 ? <p className="mt-1.5 text-ink-soft">
      ClinVar lists <b className="font-semibold text-ink">{v.plp.toLocaleString()} {gene} variant{v.plp === 1 ? "" : "s"}</b> that labs classified as disease-causing for this condition
      {v.vus ? `, and ${v.vus.toLocaleString()} of uncertain significance` : ""}. {reading}
    </p> : <p className="mt-1.5 text-ink-soft">No ClinVar submission names this exact condition with a disease-causing {gene} variant yet{v.gene_unassigned_plp ? `; ${v.gene_unassigned_plp.toLocaleString()} disease-causing ${gene} variants were submitted without a specific condition` : ""}.</p>}
    {types.length > 0 && v.plp > 0 && <ul className="mt-2 flex flex-wrap gap-1.5">{types.map(([t, n]) => <li key={t} className="rounded-full bg-ink-wash px-2 py-0.5 text-ink-soft">{TYPE_WORDS[t] ?? t} · {n}</li>)}</ul>}
    {v.top.length > 0 && <p className="mt-2 text-ink-faint">Most reported: {v.top.map((t, k) => <span key={t[0]}>{k ? " · " : ""}<a className="underline" href={`https://www.ncbi.nlm.nih.gov/clinvar/variation/${t[0]}/`} target="_blank" rel="noreferrer">{t[2] || t[1].split(":")[1]}</a> ({t[4]} lab{t[4] === 1 ? "" : "s"})</span>)}</p>}
    <Lookup c={c} />
  </div>;
}

function Lookup({ c }: { c: ConditionBundle }) {
  const gene = c.gene.symbol;
  const [query, setQuery] = useState("");
  const [state, setState] = useState<{ status: "idle" | "loading" | "done" | "error"; data?: GeneVariants; hits?: VariantRow[] }>({ status: "idle" });
  const names = new Map<string, string>([[c.id, c.name], ...c.other_conditions_of_gene.map(o => [o.id, o.name] as [string, string])]);
  const search = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setState({ status: "loading" });
    const data = await geneVariants(gene);
    if (!data) return setState({ status: "error" });
    setState({ status: "done", data, hits: data.variants.filter(v => matches(query, v)).slice(0, 8) });
  };
  return <form onSubmit={search} className="mt-3 border-t border-ink-line pt-3">
    <label htmlFor="variant-q" className="block font-medium text-ink">Look up the variant on your genetic report</label>
    <div className="mt-1.5 flex gap-1.5">
      <input id="variant-q" value={query} onChange={e => setQuery(e.target.value)} placeholder={gene.startsWith("MT-") ? "e.g. m.3243A>G" : "e.g. c.1631G>A, p.Arg544Gln or R544Q"}
        className="min-w-0 flex-1 rounded-lg border border-ink-line px-2.5 py-1.5 text-xs outline-none focus:border-machinery" />
      <button className="rounded-lg bg-machinery px-3 py-1.5 font-semibold text-white hover:opacity-90" disabled={state.status === "loading"}>{state.status === "loading" ? "…" : "Look up"}</button>
    </div>
    {state.status === "error" && <p className="mt-2 text-caution">The variant list could not be loaded right now. You can search ClinVar directly: <a className="underline" href={`https://www.ncbi.nlm.nih.gov/clinvar/?term=${encodeURIComponent(`${gene}[gene] ${query}`)}`} target="_blank" rel="noreferrer">ClinVar ↗</a></p>}
    {state.status === "done" && state.hits && <div className="mt-2 space-y-2" aria-live="polite">
      {state.hits.length === 0 && <p className="text-ink-soft">Not found among {state.data!.total.toLocaleString()} ClinVar records for {gene}. Check the exact spelling on your report (the part starting with c. or p.). A variant missing from ClinVar is not necessarily new or harmful. <a className="underline" href={`https://www.ncbi.nlm.nih.gov/clinvar/?term=${encodeURIComponent(`${gene}[gene] ${query}`)}`} target="_blank" rel="noreferrer">Search ClinVar ↗</a></p>}
      {state.hits.map(v => <article key={v[0]} className="rounded-lg bg-ink-wash/60 p-2.5">
        <div className="flex flex-wrap items-center gap-1.5"><span className={`rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${CLASS[v[3]].tone}`}>{CLASS[v[3]].label}</span><span className="text-[10.5px] text-ink-faint">{STARS[v[4]]} · {v[5]} submission{v[5] === 1 ? "" : "s"}</span></div>
        <p className="mt-1 break-all font-mono text-[11px] text-ink">{v[1]}{v[2] && ` (${v[2]})`}</p>
        <p className="mt-1 text-ink-soft">{TYPE_WORDS[v[6]] ?? v[6]}{v[9] ? ` · last evaluated ${v[9]}` : ""}</p>
        {v[7].length > 0 && <p className="mt-1 text-ink-soft">Reported for: {v[7].map((i, k) => { const id = state.data!.conditions[i]; return <span key={id}>{k ? ", " : ""}{id === c.id ? <b className="font-semibold text-ink">this condition</b> : <Link className="underline" to={routes.condition(id)}>{names.get(id) ?? id}</Link>}</span>; })}</p>}
        {!v[7].length && v[10] && <p className="mt-1 text-ink-soft">Reported for: {v[10]}</p>}
        <a className="mt-1 inline-block font-semibold text-machinery underline" href={`https://www.ncbi.nlm.nih.gov/clinvar/variation/${v[0]}/`} target="_blank" rel="noreferrer">Full ClinVar record ↗</a>
      </article>)}
      <p className="text-[10.5px] leading-relaxed text-ink-faint">ClinVar collects what labs have submitted publicly (release {state.data!.release}); classifications change as evidence grows. The classification on your own lab report is the one that applies to you. Ask your genetics team before drawing conclusions.</p>
    </div>}
  </form>;
}
