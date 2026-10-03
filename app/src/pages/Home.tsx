import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { SearchBox } from "../components/SearchBox";
import { getMeta } from "../lib/data";
import { routes } from "../lib/links";
import type { Meta } from "../lib/types";

const EXAMPLES: [string, string][] = [
  ["SNAP25", routes.gene("SNAP25")],
  ["STXBP1", routes.gene("STXBP1")],
  ["Dravet syndrome", routes.condition("MONDO:0100135")],
  ["Atonic seizure", routes.symptom("HP:0010819")],
  ["Lysosomal storage disease", routes.group("MONDO:0002561")],
  ["SNARE complex", routes.mechanism("GO:0031201")],
];

export default function Home() {
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => {
    getMeta().then(setMeta, () => setMeta(null));
  }, []);
  const n = (x?: number) => (x ? x.toLocaleString("en-US") : "…");

  return (
    <div>
      <section className="mx-auto max-w-3xl pb-16 pt-20 text-center sm:pt-28">
        <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
          Find who shares your rare disease's <span className="text-machinery">biology</span>.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg leading-relaxed text-ink-soft">
          Search a diagnosis, gene or symptom. See which conditions are connected to yours, why, and where every piece of evidence comes from.
        </p>
        <div className="mx-auto mt-10 max-w-2xl text-left">
          <SearchBox autoFocus />
        </div>
        <div className="mt-5 flex flex-wrap justify-center gap-2 text-sm">
          <span className="text-ink-faint">Try</span>
          {EXAMPLES.map(([label, to]) => (
            <Link key={label} to={to} className="rounded-full border border-ink-line px-3 py-1 text-ink-soft transition hover:border-ink-faint hover:text-ink">
              {label}
            </Link>
          ))}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-px overflow-hidden rounded-2xl border border-ink-line bg-ink-line sm:grid-cols-3">
        {[
          ["1", "Who shares your biology?", "Conditions with the same rare symptoms or the same molecular machinery, even when their names have nothing in common."],
          ["2", "Why are you connected?", "Every link shows its evidence: curated databases, protein interactions, shared symptoms. Computed connections are labeled as hypotheses."],
          ["3", "What could you do next?", "Existing work to build on, honest gaps, and the questions worth checking with experts."],
        ].map(([num, title, text]) => (
          <div key={num} className="bg-white p-6">
            <div className="font-mono text-sm text-machinery">{num}</div>
            <h2 className="mt-2 font-semibold">{title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-ink-soft">{text}</p>
          </div>
        ))}
      </section>

      <section className="mt-16 grid grid-cols-1 items-center gap-10 md:grid-cols-2">
        <div>
          <div className="eyebrow">Names hide mechanisms</div>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">A muscle disease on paper, a brain disease in reality</h2>
          <p className="mt-3 leading-relaxed text-ink-soft">
            The disease ontology still lists SNAP25's condition as a congenital myasthenic syndrome. Curators and recent papers describe an epileptic encephalopathy. Searching by name or symptoms alone, you would never find its closest relatives. Through shared molecular machinery, the atlas does.
          </p>
          <Link to={routes.condition("MONDO:0014590")} className="link mt-4 inline-block font-medium">
            See SNAP25's connections
          </Link>
        </div>
        <div className="card p-6">
          <div className="flex items-center gap-3">
            <span className="rounded-md bg-ink px-2 py-1 font-mono text-xs font-semibold text-white">SNAP25</span>
            <span className="text-ink-faint">connects to</span>
          </div>
          <ul className="mt-4 space-y-3 text-sm">
            {[
              ["VAMP2", "proteins bind each other, parts of one SNARE complex"],
              ["CPLX1", "proteins bind each other, both bind STXBP1"],
              ["STX1B", "proteins bind each other, same variant effect"],
              ["SYT1", "proteins bind each other, same toxin pathway"],
            ].map(([g, why]) => (
              <li key={g} className="flex items-baseline gap-3">
                <span className="w-14 shrink-0 font-mono text-xs font-semibold">{g}</span>
                <span className="text-ink-soft">{why}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mt-16 grid grid-cols-1 gap-6 border-t border-ink-line pt-10 sm:grid-cols-4">
        {[
          [n(meta?.counts.conditions), "genetic conditions"],
          [n(meta?.counts.genes), "genes"],
          [n(meta?.counts.groups), "disease groups"],
          [meta ? String(Object.keys(meta.sources).length) : "…", "open datasets"],
        ].map(([value, label]) => (
          <div key={label}>
            <div className="text-3xl font-semibold tracking-tight">{value}</div>
            <div className="text-sm text-ink-soft">{label}</div>
          </div>
        ))}
      </section>
    </div>
  );
}
