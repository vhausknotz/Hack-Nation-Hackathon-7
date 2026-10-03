// Turns computed connections into plain-language reasons and evidence panels.
import type { EvidenceItem, EvidencePanel } from "../components/EvidenceDrawer";
import { effectExplainer, effectLabel, frequency, symptomRarity } from "./format";
import { external, mechanismSource, recordLink } from "./links";
import type { ConditionBundle, MechanismDict, Neighbor, Phenotype, SharedMechanism, SymptomDict } from "./types";

export interface Reason {
  text: string;
  kind: "machinery" | "symptom" | "gene";
  source: string;
  url?: string;
}

export function mechanismReason(m: SharedMechanism, a: string, b: string, dict: MechanismDict): Reason {
  switch (m.k) {
    case "interaction":
      return { text: `${a} and ${b} proteins bind each other`, kind: "machinery", source: `STRING, confidence ${m.score.toFixed(2)}`, url: external.string(a) };
    case "partner":
      return { text: `Both proteins bind ${m.symbol}`, kind: "machinery", source: "STRING", url: external.string(m.symbol) };
    default: {
      const [name, genes] = dict[m.id] ?? [m.id, 0];
      const { source, url } = mechanismSource(m.id);
      const where = m.k === "complex" ? "Both are parts of" : m.k === "pathway" ? "Same pathway:" : "Both involved in";
      return { text: `${where} ${name}`, kind: "machinery", source: genes ? `${source} · ${genes.toLocaleString("en-US")} genes` : source, url };
    }
  }
}

export function symptomName(id: string, dict: SymptomDict, plain = false): string {
  const entry = dict[id];
  if (!entry) return id;
  return plain && entry[1] ? entry[1] : entry[0];
}

/** The shorter of the plain and clinical names, for tight spaces like diagram labels. */
export function shortSymptomName(id: string, dict: SymptomDict): string {
  const [name, plain] = dict[id] ?? [id, null];
  return plain && plain.length <= name.length + 6 ? plain : name;
}

/** The one or two strongest reasons behind a connection, for cards. */
export function topReasons(n: Neighbor, gene: string, dict: ConditionBundle["dict"]): Reason[] {
  const out: Reason[] = [];
  if (n.same_gene) out.push({ text: `Caused by the same gene, ${gene}`, kind: "gene", source: "Curated gene-disease links" });
  if (n.mechanisms[0] && n.mech >= 0.15) out.push(mechanismReason(n.mechanisms[0], gene, n.gene, dict.mechanisms));
  const rare = n.symptoms.filter((s) => (dict.symptoms[s]?.[2] ?? 9999) <= 400);
  if (rare.length && n.sym >= 0.08) {
    const names = rare.slice(0, 2).map((s) => symptomName(s, dict.symptoms));
    out.push({ text: `Shares ${rare.length > 2 ? `${rare.length} uncommon symptoms, incl.` : "uncommon symptoms:"} ${names.join(", ")}`, kind: "symptom", source: "HPO annotations" });
  }
  return out.slice(0, 2);
}

export function connectionPanel(c: ConditionBundle, n: Neighbor): EvidencePanel {
  const items: EvidenceItem[] = [];
  for (const m of n.mechanisms) {
    const r = mechanismReason(m, c.gene.symbol, n.gene, c.dict.mechanisms);
    items.push({ label: r.text, detail: r.source, url: r.url });
  }
  for (const s of n.symptoms) {
    const count = c.dict.symptoms[s]?.[2] ?? 0;
    items.push({ label: `Shared symptom: ${symptomName(s, c.dict.symptoms)}`, detail: `HPO ${s} · ${symptomRarity(count)}`, url: external.hpo(s) });
  }
  const effect =
    n.effect === "different"
      ? "The two conditions are curated with different variant effects, so a therapy approach may not transfer directly."
      : n.effect === "same"
        ? "Both conditions are curated with the same variant effect, which makes shared therapy approaches more plausible."
        : "For at least one of them, the variant effect is not curated yet.";
  return {
    title: n.same_gene ? `${c.name} and ${n.name}: the same gene` : `Why ${c.gene.symbol} and ${n.gene} conditions may be connected`,
    tier: "hypothesis",
    summary: (
      <>
        <p>
          The atlas computed this connection from open data. Symptom similarity is <b>{Math.round(n.sym * 100)}</b>/100 (rare symptoms count more than common ones) and molecular-machinery similarity is <b>{Math.round(n.mech * 100)}</b>/100 (shared complexes, pathways, processes and protein partners).
        </p>
        <p className="mt-3">{effect}</p>
        {!n.same_category && <p className="mt-3">They affect different body systems, so the shared biology may play out in another tissue.</p>}
      </>
    ),
    itemsTitle: "What they share",
    items,
    note: "A hypothesis, not a finding. Each shared item below is recorded data; the connection itself still needs expert review.",
  };
}

export function geneEvidencePanel(c: ConditionBundle): EvidencePanel {
  return {
    title: `${c.gene.symbol} causes ${c.name}`,
    tier: "data",
    summary: (
      <p>
        Curated gene–disease link, rated <b>{c.gene.strength}</b> overall. Each curator below reviewed the published evidence independently.
      </p>
    ),
    items: c.gene.evidence.map((e) => ({
      label: e.source,
      detail: [e.confidence && `Classification: ${e.confidence}`, e.mechanism && `Mechanism: ${e.mechanism}`, e.inheritance && `Inheritance: ${e.inheritance.replace(/_/g, " ")}`, e.pmids?.length ? `${e.pmids.length} cited papers` : ""]
        .filter(Boolean)
        .join(" · "),
      url: e.url,
      date: e.date,
    })),
  };
}

export function effectPanel(c: ConditionBundle): EvidencePanel {
  const v = c.variant_effect.value;
  return {
    title: `How the ${c.gene.symbol} change acts: ${effectLabel[v].toLowerCase()}`,
    tier: "data",
    summary: <p>{effectExplainer[v]}</p>,
    items: c.variant_effect.sources.map((s) => ({ label: s.source, detail: `${s.value}${s.support ? ` (${s.support})` : ""}`, url: s.url })),
    note: v === "unknown" ? "Missing evidence: no curator has classified this mechanism yet." : undefined,
  };
}

export function symptomPanel(p: Phenotype, dict: SymptomDict): EvidencePanel {
  const [name, plain, count] = dict[p.id] ?? [p.id, null, 0];
  const items: EvidenceItem[] = [
    ...p.sources.map((s) => ({ label: `Annotation from ${s.replace(/ \(via .*\)/, "")}`, detail: s.includes("via") ? "Inherited from a broader disease entry" : undefined, url: recordLink(s.split(" ")[0]) ?? undefined })),
    ...p.refs.map((r) => ({ label: r, detail: "Cited publication", url: recordLink(r) ?? undefined })),
  ];
  return {
    title: plain ? `${plain} (${name})` : name,
    tier: "data",
    summary: (
      <p>
        Recorded for this condition in the Human Phenotype Ontology annotations{frequency(p.frequency) ? <>, seen in <b>{frequency(p.frequency)?.toLowerCase()}</b></> : ""}. Across the atlas, this symptom is {symptomRarity(count)}.
      </p>
    ),
    items: [...items, { label: `HPO term ${p.id}`, url: external.hpo(p.id) }],
  };
}
