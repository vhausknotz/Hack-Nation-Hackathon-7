import { useEffect, useState } from "react";
import { ExternalLink, Section, TierLegend } from "../components/ui";
import { getMeta } from "../lib/data";
import type { Meta } from "../lib/types";

export default function About() {
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => {
    getMeta().then(setMeta, () => setMeta(null));
  }, []);
  return (
    <div className="max-w-3xl pb-10">
      <header className="pt-12">
        <div className="eyebrow">How it works</div>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">A map of rare-disease biology, with its evidence attached</h1>
        <p className="mt-4 text-lg leading-relaxed text-ink-soft">
          Most rare diseases are organized by name. But different genes can break the same machinery, and one gene can break things in opposite ways. The atlas organizes the world's genetic conditions by what they share underneath, so that families and researchers can find each other.
        </p>
      </header>

      <Section title="What a connection means">
        <div className="space-y-4 text-[15px] leading-relaxed text-ink-soft">
          <p>
            <b className="text-ink">Shared symptoms.</b> Each condition's symptoms come from the Human Phenotype Ontology. Two conditions score higher when they share symptoms that are rare across all conditions: sharing "seizures" (thousands of conditions) means little, sharing "atonic seizures" (about ninety) means a lot. Conditions with very few recorded symptoms are scored more cautiously.
          </p>
          <p>
            <b className="text-ink">Shared machinery.</b> For each gene we collect the protein complexes (Complex Portal), pathways (Reactome), biological processes and cell locations (Gene Ontology) and high-confidence physical partners (STRING) it takes part in. Two conditions score higher when their genes share specific machinery, or when their proteins bind each other directly.
          </p>
          <p>
            <b className="text-ink">Look-alikes.</b> Genes from the same protein family whose conditions share almost no symptoms are shown separately: a family resemblance is not a shared mechanism.
          </p>
          <p>
            <b className="text-ink">Variant effect.</b> Whether a gene change removes the protein's function or makes it overactive or toxic decides which therapy approaches could transfer. It comes from Gene2Phenotype, Orphanet and ClinGen, and many conditions don't have it curated yet.
          </p>
        </div>
      </Section>

      <Section title="Data, hypotheses and proof">
        <TierLegend />
        <p className="mt-4 text-[15px] leading-relaxed text-ink-soft">
          Everything recorded in a curated source is shown as data, with a link to it. Connections the atlas computes are always hypotheses: leads for experts to check, never findings. Clinical proof is reserved for trial results and approvals.
        </p>
      </Section>

      <Section title="Where this is going">
        <p className="text-[15px] leading-relaxed text-ink-soft">
          The atlas is becoming a living evidence network. AI agents, ours and anyone's, will read papers, trials and patient-group pages and propose new claims. A small trusted kernel checks what can be checked mechanically (the source exists, the quote is really in it, the identifiers are valid, computations reproduce), and independent reviewers judge the meaning. Nothing becomes knowledge without passing both, and every claim keeps its full history.
        </p>
      </Section>

      <Section title="Sources">
        {meta ? (
          <ul className="space-y-3 text-sm">
            {Object.values(meta.sources).map((s) => (
              <li key={s.file} className="flex flex-col gap-0.5 border-b border-ink-line/60 pb-3">
                <span className="font-medium text-ink">{s.description}</span>
                <span className="text-ink-faint">
                  {s.license} · retrieved {s.retrieved.slice(0, 10)} · <ExternalLink href={s.url}>download</ExternalLink>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-ink-soft">Loading sources…</p>
        )}
        <p className="mt-6 text-sm text-ink-soft">
          Built {meta?.built ?? "…"}. A research-coordination tool, not medical advice. Source code and the pipeline that rebuilds this dataset:{" "}
          <ExternalLink href="https://github.com/vhausknotz/Hack-Nation-Hackathon-7">GitHub</ExternalLink>.
        </p>
      </Section>
    </div>
  );
}
