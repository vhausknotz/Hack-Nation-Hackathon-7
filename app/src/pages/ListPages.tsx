// Symptom, group and mechanism pages: an entity plus the conditions it touches.
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ExternalLink, GeneChip, Loading, NotFoundBox, Section } from "../components/ui";
import { getGroup, getMechanism, getSymptom } from "../lib/data";
import { capitalize, categoryLabel, frequency, symptomRarity } from "../lib/format";
import { mechanismSource, routes } from "../lib/links";
import type { Brief, GroupBundle, MechanismBundle, SymptomBundle } from "../lib/types";

function useEntity<T>(load: (id: string) => Promise<T | null>) {
  const { id = "" } = useParams();
  const [value, setValue] = useState<T | null | undefined>(undefined);
  useEffect(() => {
    setValue(undefined);
    window.scrollTo(0, 0);
    load(decodeURIComponent(id)).then(setValue, () => setValue(null));
  }, [id, load]);
  return [value, id] as const;
}

function ConditionList({ items, total, extra }: { items: (Brief & { frequency?: string })[]; total: number; extra?: (b: Brief & { frequency?: string }) => string | null }) {
  const [filter, setFilter] = useState("");
  const shown = items.filter((b) => !filter || `${b.name} ${b.gene}`.toLowerCase().includes(filter.toLowerCase()));
  return (
    <>
      {items.length > 12 && (
        <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter by name or gene" className="mb-4 w-full max-w-sm rounded-lg border border-ink-line px-3 py-2 text-sm outline-none focus:border-machinery/50" />
      )}
      <ul className="grid grid-cols-1 gap-x-8 md:grid-cols-2">
        {shown.map((b) => (
          <li key={b.id} className="flex items-center gap-3 border-b border-ink-line/60 py-2 text-sm">
            <GeneChip symbol={b.gene} />
            <Link to={routes.condition(b.id)} className="min-w-0 flex-1 truncate hover:text-machinery">
              {b.name}
            </Link>
            <span className="shrink-0 text-xs text-ink-faint">{extra?.(b) ?? categoryLabel(b.category)}</span>
          </li>
        ))}
      </ul>
      {total > items.length && <p className="mt-4 text-sm text-ink-faint">Showing {items.length} of {total.toLocaleString("en-US")}.</p>}
    </>
  );
}

export function SymptomPage() {
  const [s, id] = useEntity<SymptomBundle>(getSymptom);
  if (s === undefined) return <Loading what="Loading symptom" />;
  if (s === null) return <NotFoundBox what={`symptom ${id}`} />;
  const plain = s.plain[0];
  return (
    <div className="pb-10">
      <header className="pt-10">
        <div className="eyebrow">Symptom · HPO {s.id}</div>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">{capitalize(plain ?? s.name)}</h1>
        {plain && <p className="mt-2 text-ink-soft">Clinical term: {s.name}</p>}
        {s.definition && <p className="mt-5 max-w-3xl leading-relaxed text-ink-soft">{s.definition}</p>}
        <p className="mt-4 text-sm text-ink-soft">
          Across the atlas this symptom is <b className="text-ink">{symptomRarity(s.conditions_with_it)}</b>. Rare symptoms are strong clues when looking for related conditions. <ExternalLink href={s.url}>HPO</ExternalLink>
        </p>
      </header>
      <Section eyebrow="Conditions" title={`Recorded in ${s.direct_count.toLocaleString("en-US")} conditions`} intro="Conditions whose annotations name this exact symptom; more conditions record a more specific form of it.">
        <ConditionList items={s.conditions} total={s.direct_count} extra={(b) => frequency(b.frequency ?? "")} />
      </Section>
    </div>
  );
}

export function GroupPage() {
  const [g, id] = useEntity<GroupBundle>(getGroup);
  if (g === undefined) return <Loading what="Loading group" />;
  if (g === null) return <NotFoundBox what={`disease group ${id}`} />;
  return (
    <div className="pb-10">
      <header className="pt-10">
        <div className="eyebrow">Disease group · {g.id}</div>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">{capitalize(g.name)}</h1>
        {g.synonyms.length > 0 && <p className="mt-2 text-sm text-ink-faint">Also known as: {g.synonyms.join(" · ")}</p>}
        {g.definition && <p className="mt-5 max-w-3xl leading-relaxed text-ink-soft">{g.definition}</p>}
        <p className="mt-4 text-sm">
          <ExternalLink href={g.url}>Monarch Initiative</ExternalLink>
        </p>
      </header>
      <Section eyebrow="Members" title={`${g.member_count.toLocaleString("en-US")} genetic conditions in this group`} intro="A grouping by name or category. Conditions in one group may still work through different mechanisms; check each condition's connections.">
        <ConditionList items={g.conditions} total={g.member_count} />
      </Section>
    </div>
  );
}

export function MechanismPage() {
  const [m, id] = useEntity<MechanismBundle>(getMechanism);
  if (m === undefined) return <Loading what="Loading mechanism" />;
  if (m === null) return <NotFoundBox what={`mechanism ${id}`} />;
  const src = mechanismSource(m.id);
  return (
    <div className="pb-10">
      <header className="pt-10">
        <div className="eyebrow">
          {src.source} · {m.id}
        </div>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">{capitalize(m.name)}</h1>
        <p className="mt-3 text-sm text-ink-soft">
          {m.genes_with_it.toLocaleString("en-US")} human genes are annotated to this, {m.condition_genes.length} of them with conditions in the atlas. <ExternalLink href={src.url}>{src.source}</ExternalLink>
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          {m.condition_genes.slice(0, 60).map((g) => (
            <GeneChip key={g} symbol={g} />
          ))}
        </div>
      </header>
      <Section eyebrow="Conditions" title="Conditions caused by these genes" intro="Sharing machinery is a reason to look closer, not proof of a shared mechanism.">
        <ConditionList items={m.conditions} total={m.condition_count} />
      </Section>
    </div>
  );
}
