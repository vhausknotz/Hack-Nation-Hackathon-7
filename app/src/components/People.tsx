// People working on a gene: investigators on recent patient research (PubMed) and NIH-funded projects.
// Public, professional information as printed on publications and grants; no private contact details.
import type { ConditionBundle } from "../lib/types";

const pubmedFor = (name: string, gene: string) =>
  `https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(`${name}[au] AND ${gene}[tiab]`)}`;

export function PeopleSection({ c }: { c: ConditionBundle }) {
  const p = c.people;
  const gene = c.gene.symbol;
  if (!p) return null; // not searched yet
  if (!p.researchers.length && !p.projects.length) {
    return <p className="mt-4 text-xs text-ink-faint">No researchers publishing patient research on {gene} were found in our PubMed and NIH searches yet.</p>;
  }
  return (
    <div className="mt-5">
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">People working on {gene}</h3>
      {p.researchers.length > 0 && (
        <ul className="space-y-1.5">
          {p.researchers.map((r) => (
            <li key={r.name} className="rounded-lg border border-ink-line bg-white p-2.5 text-xs">
              <a className="font-semibold text-ink underline decoration-ink-line underline-offset-2 hover:text-machinery" href={pubmedFor(r.name, gene)} target="_blank" rel="noreferrer">{r.name}</a>
              {r.affiliation && <span className="text-ink-soft">, {r.affiliation}</span>}
              <span className="block text-ink-faint">{r.papers} recent paper{r.papers === 1 ? "" : "s"} on {gene} patients{r.latest ? ` · latest ${r.latest}` : ""}</span>
            </li>
          ))}
        </ul>
      )}
      {p.projects.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-[11px] font-medium text-ink-soft">NIH-funded projects mentioning {gene}</div>
          {p.projects.map((pr) => (
            <a key={pr.url || pr.title} href={pr.url} target="_blank" rel="noreferrer" className="mb-1.5 block rounded-lg bg-ink-wash/70 p-2.5 text-xs hover:bg-machinery-soft/40">
              <span className="block font-medium text-ink">{pr.title}</span>
              <span className="text-ink-soft">{pr.pis.join(", ")} · {pr.organization} · {pr.years.join(", ")}</span>
            </a>
          ))}
        </div>
      )}
      <p className="mt-2 text-[10.5px] leading-relaxed text-ink-faint">
        As listed on publications since 2015 and NIH RePORTER (searched {p.retrieved}). A name here means they published on or were funded for work mentioning {gene}, not that they treat patients or take enquiries. To reach someone, use the corresponding-author address in a paper or their institution's page.
      </p>
    </div>
  );
}
