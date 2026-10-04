import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ConnectionCard } from "../components/ConnectionCard";
import { useEvidence } from "../components/EvidenceDrawer";
import { PathDiagram } from "../components/PathDiagram";
import { VariantSection } from "../components/Variants";
import { Chip, ExternalLink, GeneChip, Loading, NotFoundBox, Section, TierLegend } from "../components/ui";
import { getCondition } from "../lib/data";
import { capitalize, categoryLabel, effectExplainer, effectLabel, frequency, rarity, symptomRarity } from "../lib/format";
import { external, mechanismSource, routes } from "../lib/links";
import { effectPanel, geneEvidencePanel, mechanismReason, symptomName, symptomPanel } from "../lib/reasons";
import type { ConditionBundle, Neighbor } from "../lib/types";

type Tab = "overall" | "symptoms" | "machinery";

export default function ConditionPage() {
  const { id = "" } = useParams();
  const [c, setC] = useState<ConditionBundle | null | undefined>(undefined);
  useEffect(() => {
    setC(undefined);
    window.scrollTo(0, 0);
    getCondition(decodeURIComponent(id)).then(setC, () => setC(null));
  }, [id]);
  if (c === undefined) return <Loading what="Loading condition" />;
  if (c === null) return <NotFoundBox what={`a condition with ID ${id}`} />;
  return <Condition key={c.id} c={c} />;
}

function Condition({ c }: { c: ConditionBundle }) {
  const open = useEvidence();
  const [tab, setTab] = useState<Tab>("overall");
  const [showAll, setShowAll] = useState(false);
  const ranked = useMemo(() => rank(c.neighbors, tab), [c, tab]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = ranked.find((n) => n.id === selectedId) ?? ranked[0];
  const r = rarity(c.prevalence);
  const strongest = c.gene.evidence.find((e) => e.confidence && /definitive|strong/i.test(e.confidence));
  const nameDiffers = c.disease_name.toLowerCase() !== c.name.toLowerCase() && !c.synthetic;

  return (
    <div className="pb-10">
      {/* ---------- header ---------- */}
      <header className="pt-10">
        <div className="eyebrow">Condition · {categoryLabel(c.category)}</div>
        <h1 className="mt-2 max-w-4xl text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">{c.name}</h1>
        <p className="mt-3 flex flex-wrap items-center gap-2 text-[15px] text-ink-soft">
          Caused by changes in the <GeneChip symbol={c.gene.symbol} /> gene{c.gene.name ? <span className="text-ink-faint">({c.gene.name})</span> : null}
          {c.inheritance.length > 0 && <span>· {c.inheritance.map((i) => i.replace(" inheritance", "").toLowerCase()).join(", ")}</span>}
        </p>
        {nameDiffers && (
          <p className="mt-2 text-sm text-ink-soft">
            Listed in the MONDO disease ontology as <span className="font-medium text-ink">“{c.disease_name}”</span>.
          </p>
        )}
        {c.synthetic && (
          <p className="mt-2 text-sm text-ink-soft">
            The gene-specific form of <span className="font-medium text-ink">“{c.disease_name}”</span>, which several genes can cause.
          </p>
        )}
        {c.also_known_as.length > 0 && <AlsoKnownAs names={c.also_known_as} />}
        {c.definition && (
          <p className="mt-5 max-w-3xl text-[15px] leading-relaxed text-ink-soft">
            {c.definition} <span className="whitespace-nowrap text-xs text-ink-faint">— MONDO definition</span>
          </p>
        )}

        <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Fact label="How rare" value={r?.headline ?? "Unknown"} detail={r?.detail ?? "No prevalence estimate in Orphanet"} href={c.prevalence?.url} />
          <Fact label="How the gene change acts" value={effectLabel[c.variant_effect.value]} detail="Tap for sources" onClick={() => open(effectPanel(c))} warn={c.variant_effect.value === "unknown"} />
          <Fact label="Gene–disease evidence" value={capitalize(strongest?.confidence ?? c.gene.strength)} detail={`${c.gene.evidence.length} curation source${c.gene.evidence.length === 1 ? "" : "s"}`} onClick={() => open(geneEvidencePanel(c))} />
          <Fact label="Symptoms recorded" value={String(c.phenotype_count)} detail={c.onset.length ? `Onset: ${c.onset.map((o) => o.replace(" onset", "")).join(", ").toLowerCase()}` : "Onset not recorded"} />
        </div>
        {c.variants && <div className="max-w-3xl"><VariantSection c={c} /></div>}
      </header>

      {/* ---------- 1. who shares your biology ---------- */}
      <Section
        id="connections"
        eyebrow="1 · Who shares your biology?"
        title="Conditions connected to this one"
        intro={
          <>
            Ranked by shared <span className="font-medium text-symptom">symptoms</span> (rare ones count more) and shared <span className="font-medium text-machinery">molecular machinery</span> (proteins that work together). Computed by the atlas from open data: leads to check, not findings.
          </>
        }
        aside={<TierLegend />}
      >
        {c.neighbors.length === 0 ? (
          <p className="text-ink-soft">No connections computed: this condition has too little recorded data for comparison.</p>
        ) : (
          <>
            <div className="mb-5 flex max-w-full gap-1 overflow-x-auto rounded-lg bg-ink-wash p-1 text-sm sm:inline-flex" role="tablist">
              {(
                [
                  ["overall", "Strongest overall"],
                  ["symptoms", "Similar symptoms"],
                  ["machinery", "Same machinery"],
                ] as const
              ).map(([t, label]) => (
                <button
                  key={t}
                  role="tab"
                  aria-selected={tab === t}
                  onClick={() => {
                    setTab(t);
                    setSelectedId(null);
                  }}
                  className={`flex-1 whitespace-nowrap rounded-md px-3 py-1.5 font-medium transition ${tab === t ? "bg-white shadow-sm" : "text-ink-soft hover:text-ink"}`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {(showAll ? ranked : ranked.slice(0, 6)).map((n) => (
                <ConnectionCard key={n.id} c={c} n={n} selected={selected?.id === n.id} onSelect={() => setSelectedId(n.id)} />
              ))}
            </div>
            {ranked.length > 6 && (
              <button onClick={() => setShowAll(!showAll)} className="mt-4 text-sm font-medium text-machinery hover:underline">
                {showAll ? "Show fewer" : `Show all ${ranked.length} connections`}
              </button>
            )}
          </>
        )}

        {c.other_conditions_of_gene.length > 0 && (
          <div className="mt-10">
            <h3 className="font-semibold">Other conditions caused by {c.gene.symbol}</h3>
            <p className="mt-1 max-w-2xl text-sm text-ink-soft">Same gene, but not necessarily the same mechanism: different changes in one gene can act in opposite ways and need different strategies.</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {c.other_conditions_of_gene.map((o) => (
                <Chip key={o.id} to={routes.condition(o.id)}>
                  {o.name}
                </Chip>
              ))}
            </div>
          </div>
        )}

        {c.lookalikes.length > 0 && (
          <div className="mt-10 rounded-xl border border-caution/20 bg-caution-soft/30 p-5">
            <h3 className="font-semibold">Look-alikes: related names, different diseases</h3>
            <p className="mt-1 max-w-2xl text-sm text-ink-soft">
              These genes belong to the same protein family as {c.gene.symbol}, but their conditions share almost no symptoms. A shared family name is not a shared mechanism, so these are not good partners for joint research.
            </p>
            <ul className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {c.lookalikes.map((l) => (
                <li key={l.id} className="flex items-center gap-3 text-sm">
                  <GeneChip symbol={l.gene} />
                  <Link to={routes.condition(l.id)} className="min-w-0 truncate hover:text-machinery">
                    {l.name}
                  </Link>
                  <span className="ml-auto shrink-0 text-xs text-ink-faint">{l.same_category ? "same body system" : categoryLabel(l.category)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-ink-faint">Protein family: {[...new Set(c.lookalikes.map((l) => l.family))].join(", ")} (HGNC)</p>
          </div>
        )}
      </Section>

      {/* ---------- 2. why are you connected ---------- */}
      {selected && (
        <Section
          id="why"
          eyebrow="2 · Why are you connected?"
          title={`${c.gene.symbol} and ${selected.gene}`}
          intro={
            <>
              How <b className="text-ink">{c.name}</b> connects to <Link className="link" to={routes.condition(selected.id)}>{selected.name}</Link>. Click any line to see its sources.
            </>
          }
        >
          <PathDiagram c={c} n={selected} />
          <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <h3 className="eyebrow mb-3 text-machinery">Shared molecular machinery</h3>
              {selected.same_gene ? (
                <p className="text-sm text-ink-soft">Both are caused by {c.gene.symbol}.</p>
              ) : selected.mechanisms.length ? (
                <ul className="space-y-2">
                  {selected.mechanisms.map((m, i) => {
                    const r = mechanismReason(m, c.gene.symbol, selected.gene, c.dict.mechanisms);
                    return (
                      <li key={i} className="text-sm">
                        <div>{r.text}</div>
                        <div className="text-xs text-ink-faint">{r.url ? <ExternalLink href={r.url}>{r.source}</ExternalLink> : r.source}</div>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="text-sm text-ink-soft">No specific shared complex, pathway or partner.</p>
              )}
            </div>
            <div>
              <h3 className="eyebrow mb-3 text-symptom">Shared symptoms</h3>
              {selected.symptoms.length ? (
                <ul className="space-y-2">
                  {selected.symptoms.map((s) => (
                    <li key={s} className="text-sm">
                      <Link to={routes.symptom(s)} className="hover:text-symptom">
                        {symptomName(s, c.dict.symptoms, true)}
                      </Link>
                      <div className="text-xs text-ink-faint">
                        {c.dict.symptoms[s]?.[1] ? `${c.dict.symptoms[s][0]} · ` : ""}
                        {symptomRarity(c.dict.symptoms[s]?.[2] ?? 0)}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-ink-soft">No specific shared symptoms recorded.</p>
              )}
            </div>
          </div>
          <p className="mt-6 max-w-3xl rounded-lg bg-ink-wash p-4 text-sm leading-relaxed text-ink-soft">
            <b className="text-ink">Variant effect:</b> {c.gene.symbol}: {effectLabel[c.variant_effect.value].toLowerCase()}.{" "}
            {selected.effect === "different" && "The two are curated with different effects, so a therapy approach may not transfer directly."}
            {selected.effect === "same" && "Both are curated with the same effect, which makes sharing therapy approaches more plausible."}
            {selected.effect === "unknown" && "For at least one of them the effect is not curated yet, a key question before planning shared therapy work."}
          </p>
        </Section>
      )}

      {/* ---------- 3. existing work ---------- */}
      <Section id="existing" eyebrow="3 · What already exists?" title="Look up existing work" intro="Trusted public sources for trials, studies and expert information on this condition.">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <ResourceLink href={external.trialsSearch(c.gene.symbol)} title="Clinical trials and studies" detail={`ClinicalTrials.gov search for ${c.gene.symbol}`} />
          <ResourceLink href={external.pubmedSearch(`${c.gene.symbol}[tiab]`)} title="Research papers" detail={`PubMed search for ${c.gene.symbol}`} />
          {c.xrefs.Orphanet?.[0] && <ResourceLink href={external.orphanet(c.xrefs.Orphanet[0])} title="Orphanet" detail="Expert summary, centres, patient organizations" />}
          {c.xrefs.GARD?.[0] && <ResourceLink href={external.gard(c.xrefs.GARD[0])} title="GARD (NIH)" detail="Plain-language information and support" />}
          {c.xrefs.OMIM?.[0] && <ResourceLink href={external.omim(c.xrefs.OMIM[0])} title="OMIM" detail="Clinical and genetic detail" />}
          <ResourceLink href={external.monarch(c.disease)} title="Monarch Initiative" detail="Genes, phenotypes and models" />
        </div>
      </Section>

      {/* ---------- what we don't know ---------- */}
      <Section id="unknowns" eyebrow="Honest gaps" title="What we don't know">
        <ul className="grid max-w-4xl grid-cols-1 gap-3 sm:grid-cols-2">
          {gaps(c).map((g, i) => (
            <li key={i} className="rounded-lg border border-dashed border-ink-line p-4 text-sm leading-relaxed text-ink-soft">
              {g}
            </li>
          ))}
        </ul>
      </Section>

      {/* ---------- symptoms ---------- */}
      <SymptomsSection c={c} />

      {/* ---------- machinery ---------- */}
      <MachinerySection c={c} />
    </div>
  );
}

function rank(neighbors: Neighbor[], tab: Tab): Neighbor[] {
  const list = [...neighbors];
  if (tab === "symptoms") return list.filter((n) => n.sym > 0).sort((a, b) => b.sym - a.sym);
  if (tab === "machinery") return list.filter((n) => !n.same_gene && n.mech > 0).sort((a, b) => b.mech - a.mech);
  return list.sort((a, b) => b.score - a.score);
}

function gaps(c: ConditionBundle): string[] {
  const out: string[] = [];
  if (c.variant_effect.value === "unknown") out.push(effectExplainer.unknown);
  if (!c.prevalence) out.push("No prevalence estimate or case count is recorded in Orphanet.");
  if (c.phenotype_count < 5) out.push(`Only ${c.phenotype_count} symptom${c.phenotype_count === 1 ? " is" : "s are"} recorded, so symptom-based connections are less reliable.`);
  if (c.gene.strength !== "strong") out.push("The gene–disease link is rated moderate, not definitive.");
  if (c.synthetic) out.push(`This gene-specific entry comes from the broader disease “${c.disease_name}”, so some recorded symptoms may belong to other genetic forms.`);
  out.push("Every connection on this page is a computed hypothesis. None has been reviewed by an expert yet.");
  out.push("Registries, natural history studies, models and patient groups for this condition are not yet mapped in the atlas.");
  return out;
}

function AlsoKnownAs({ names }: { names: string[] }) {
  const [all, setAll] = useState(false);
  const shown = all ? names : names.slice(0, 3);
  return (
    <p className="mt-2 text-sm text-ink-soft">
      Also known as: {shown.join(" · ")}
      {names.length > 3 && (
        <button onClick={() => setAll(!all)} className="ml-2 text-machinery hover:underline">
          {all ? "less" : `+${names.length - 3} more`}
        </button>
      )}
    </p>
  );
}

function Fact({ label, value, detail, onClick, href, warn }: { label: string; value: string; detail: string; onClick?: () => void; href?: string; warn?: boolean }) {
  const body = (
    <>
      <div className="eyebrow">{label}</div>
      <div className={`mt-1.5 text-lg font-semibold ${warn ? "text-caution" : ""}`}>{value}</div>
      <div className="mt-0.5 text-xs text-ink-faint">{detail}</div>
    </>
  );
  if (onClick)
    return (
      <button onClick={onClick} className="card p-4 text-left transition hover:border-ink-faint">
        {body}
      </button>
    );
  if (href)
    return (
      <a href={href} target="_blank" rel="noreferrer" className="card p-4 transition hover:border-ink-faint">
        {body}
      </a>
    );
  return <div className="card p-4">{body}</div>;
}

function ResourceLink({ href, title, detail }: { href: string; title: string; detail: string }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="card group p-4 transition hover:border-ink-faint">
      <div className="font-medium group-hover:text-machinery">
        {title} <span aria-hidden>↗</span>
      </div>
      <div className="mt-0.5 text-sm text-ink-soft">{detail}</div>
    </a>
  );
}

function SymptomsSection({ c }: { c: ConditionBundle }) {
  const open = useEvidence();
  const [all, setAll] = useState(false);
  const list = all ? c.phenotypes : c.phenotypes.slice(0, 12);
  if (!c.phenotypes.length) return null;
  return (
    <Section id="symptoms" eyebrow="Clinical picture" title="Recorded symptoms" intro="From the Human Phenotype Ontology annotations, rarest first. Rare symptoms are the most useful for finding related conditions.">
      <ul className="grid grid-cols-1 gap-x-8 gap-y-1 md:grid-cols-2">
        {list.map((p) => {
          const [name, plain, count] = c.dict.symptoms[p.id] ?? [p.id, null, 0];
          const f = frequency(p.frequency);
          return (
            <li key={p.id}>
              <button onClick={() => open(symptomPanel(p, c.dict.symptoms))} className="flex w-full items-baseline gap-3 rounded-md px-2 py-1.5 text-left hover:bg-ink-wash">
                <span className="min-w-0 flex-1">
                  <span className="text-sm font-medium">{plain ?? name}</span>
                  {plain && plain.toLowerCase() !== name.toLowerCase() && <span className="ml-2 text-xs text-ink-faint">{name}</span>}
                </span>
                {f && <span className="shrink-0 text-xs text-ink-soft">{f}</span>}
                <span className={`shrink-0 text-[11px] ${count <= 50 ? "font-medium text-symptom" : "text-ink-faint"}`} title={`Recorded in ${count.toLocaleString("en-US")} conditions`}>{count <= 50 ? "rare" : `${count.toLocaleString("en-US")}×`}</span>
              </button>
            </li>
          );
        })}
      </ul>
      {c.phenotypes.length > 12 && (
        <button onClick={() => setAll(!all)} className="mt-3 text-sm font-medium text-machinery hover:underline">
          {all ? "Show fewer" : `Show all ${c.phenotypes.length}${c.phenotype_count > c.phenotypes.length ? ` of ${c.phenotype_count}` : ""}`}
        </button>
      )}
    </Section>
  );
}

function MachinerySection({ c }: { c: ConditionBundle }) {
  const m = c.machinery;
  const name = (id: string) => c.dict.mechanisms[id]?.[0] ?? id;
  if (!m.complexes.length && !m.pathways.length && !m.go.length && !m.partners.length) return null;
  return (
    <Section id="machinery" eyebrow="Biology" title={`What ${c.gene.symbol} does`} intro="The molecular machinery behind this condition, from curated databases. Conditions that share it may share research.">
      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        {m.complexes.length > 0 && (
          <MachineryList title="Protein complexes" items={m.complexes.map((id) => ({ id, label: name(id), source: mechanismSource(id) }))} />
        )}
        {m.pathways.length > 0 && (
          <MachineryList title="Pathways (most specific first)" items={m.pathways.map((id) => ({ id, label: name(id), source: mechanismSource(id) }))} />
        )}
        {m.go.length > 0 && <MachineryList title="Processes and locations" items={m.go.map((id) => ({ id, label: name(id), source: mechanismSource(id) }))} />}
        {m.partners.length > 0 && (
          <div>
            <h3 className="eyebrow mb-3">Binds to (STRING, high confidence)</h3>
            <div className="flex flex-wrap gap-2">
              {m.partners.map((p) =>
                p.has_condition ? (
                  <GeneChip key={p.hgnc_id} symbol={p.symbol} />
                ) : (
                  <span key={p.hgnc_id} className="rounded-md border border-ink-line px-1.5 py-0.5 font-mono text-[11px] text-ink-soft" title="No condition in the atlas">
                    {p.symbol}
                  </span>
                ),
              )}
            </div>
            <p className="mt-2 text-xs text-ink-faint">Dark chips: genes with their own conditions in the atlas.</p>
          </div>
        )}
      </div>
      {m.dosage && (
        <p className="mt-6 text-sm text-ink-soft">
          <b className="text-ink">Dosage sensitivity (ClinGen):</b> {m.dosage.haploinsufficiency}.{" "}
          <ExternalLink href={m.dosage.url}>Source</ExternalLink>
        </p>
      )}
    </Section>
  );
}

function MachineryList({ title, items }: { title: string; items: { id: string; label: string; source: { source: string; url: string } }[] }) {
  return (
    <div>
      <h3 className="eyebrow mb-3">{title}</h3>
      <ul className="space-y-1.5">
        {items.map((it) => (
          <li key={it.id} className="flex items-baseline justify-between gap-3 text-sm">
            <Link to={routes.mechanism(it.id)} className="hover:text-machinery">
              {it.label}
            </Link>
            <a href={it.source.url} target="_blank" rel="noreferrer" className="shrink-0 text-xs text-ink-faint hover:text-ink">
              {it.source.source} ↗
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
