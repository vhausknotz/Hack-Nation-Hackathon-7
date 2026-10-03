import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ExternalLink, GeneChip, Loading, NotFoundBox, Section } from "../components/ui";
import { getGene } from "../lib/data";
import { categoryLabel, effectLabel } from "../lib/format";
import { external, mechanismSource, routes } from "../lib/links";
import type { GeneBundle } from "../lib/types";

export default function GenePage() {
  const { symbol = "" } = useParams();
  const [g, setG] = useState<GeneBundle | null | undefined>(undefined);
  useEffect(() => {
    setG(undefined);
    window.scrollTo(0, 0);
    getGene(decodeURIComponent(symbol).toUpperCase()).then(setG, () => setG(null));
  }, [symbol]);
  if (g === undefined) return <Loading what="Loading gene" />;
  if (g === null) return <NotFoundBox what={`a gene called ${symbol} with a condition in the atlas`} />;

  const effects = new Set(g.conditions.map((c) => c.effect).filter((e) => e !== "unknown"));
  const name = (id: string) => g.dict.mechanisms[id]?.[0] ?? id;

  return (
    <div className="pb-10">
      <header className="pt-10">
        <div className="eyebrow">Gene</div>
        <h1 className="mt-2 font-mono text-4xl font-semibold tracking-tight">{g.symbol}</h1>
        <p className="mt-2 text-lg text-ink-soft">{g.name}</p>
        {(g.aliases.length > 0 || g.previous_symbols.length > 0) && (
          <p className="mt-2 text-sm text-ink-faint">Also written as: {[...g.previous_symbols, ...g.aliases].join(" · ")}</p>
        )}
        <div className="mt-4 flex flex-wrap gap-4 text-sm">
          <ExternalLink href={g.url}>HGNC</ExternalLink>
          {g.uniprot[0] && <ExternalLink href={`https://www.uniprot.org/uniprotkb/${g.uniprot[0]}`}>UniProt</ExternalLink>}
          <ExternalLink href={external.string(g.symbol)}>STRING</ExternalLink>
          <ExternalLink href={external.pubmedSearch(`${g.symbol}[tiab]`)}>PubMed</ExternalLink>
        </div>
      </header>

      <Section eyebrow="Conditions" title={`${g.conditions.length === 1 ? "Condition" : `${g.conditions.length} conditions`} caused by ${g.symbol}`}>
        {g.conditions.length > 1 && (
          <p className="-mt-3 mb-5 max-w-2xl text-sm text-ink-soft">
            One gene, several conditions. {effects.size > 1 ? "They are curated with different variant effects, so they may need opposite strategies." : "Different changes in a gene can act differently, so check each condition's mechanism."}
          </p>
        )}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {g.conditions.map((c) => (
            <Link key={c.id} to={routes.condition(c.id)} className="card p-4 transition hover:border-ink-faint">
              <div className="font-medium">{c.name}</div>
              <div className="mt-1 text-sm text-ink-soft">
                {categoryLabel(c.category)} · {effectLabel[c.effect].toLowerCase()} · {c.phenotype_count} symptoms
              </div>
            </Link>
          ))}
        </div>
      </Section>

      <Section eyebrow="Biology" title={`What ${g.symbol} does`}>
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          {[
            ["Protein complexes", g.complexes],
            ["Pathways", g.pathways],
            ["Processes and locations", g.go],
          ].map(([title, ids]) =>
            (ids as string[]).length ? (
              <div key={title as string}>
                <h3 className="eyebrow mb-3">{title as string}</h3>
                <ul className="space-y-1.5">
                  {(ids as string[]).map((id) => (
                    <li key={id} className="flex items-baseline justify-between gap-3 text-sm">
                      <Link to={routes.mechanism(id)} className="hover:text-machinery">
                        {name(id)}
                      </Link>
                      <a href={mechanismSource(id).url} target="_blank" rel="noreferrer" className="shrink-0 text-xs text-ink-faint hover:text-ink">
                        {mechanismSource(id).source} ↗
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null,
          )}
          {g.partners.length > 0 && (
            <div>
              <h3 className="eyebrow mb-3">Binds to (STRING)</h3>
              <div className="flex flex-wrap gap-2">
                {g.partners.map((p) =>
                  p.has_condition ? (
                    <GeneChip key={p.hgnc_id} symbol={p.symbol} />
                  ) : (
                    <span key={p.hgnc_id} className="rounded-md border border-ink-line px-1.5 py-0.5 font-mono text-[11px] text-ink-soft">
                      {p.symbol}
                    </span>
                  ),
                )}
              </div>
            </div>
          )}
        </div>
        {g.dosage && (
          <p className="mt-6 text-sm text-ink-soft">
            <b className="text-ink">Dosage sensitivity (ClinGen):</b> {g.dosage.haploinsufficiency}. <ExternalLink href={g.dosage.url}>Source</ExternalLink>
          </p>
        )}
      </Section>

      {g.mechanism_neighbors.length > 0 && (
        <Section eyebrow="Similar machinery" title={`Genes that work like ${g.symbol}`} intro="Disease genes whose proteins share complexes, pathways, processes or binding partners with this one.">
          <div className="flex flex-wrap gap-2">
            {g.mechanism_neighbors.map((n) => (
              <GeneChip key={n.hgnc_id} symbol={n.symbol} />
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
