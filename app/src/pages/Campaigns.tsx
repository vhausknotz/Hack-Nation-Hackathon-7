// Campaigns: focused efforts on a condition or a small neighborhood, with public goals, sponsors and receipts.
// Money buys attention (agents' task order, funded scout time), never acceptance: every finding still passes the
// quote check and review. Created by the atlas operator (tools/campaigns.py); progress from the engine.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Section } from "../components/ui";
import { LIVE_API } from "../lib/live";
import { routes } from "../lib/links";

interface Campaign {
  id: string; title: string; goal: string; sponsor: { name: string; url: string | null } | null; budget_usd: number; spent_usd: number;
  status: "open" | "closed"; created: number; rounds: number | null;
  conditions: { condition_id: string; name: string; gene: string | null; symptoms: number; findings_since_start: number; requests: number }[];
}

const RULES = [
  ["Money buys attention, never acceptance.", "A campaign moves its conditions up the agents' task list and can pay for the atlas's scouts to read papers. Every finding still has to pass the word-for-word quote check and review."],
  ["No pay-to-rank.", "Sponsors cannot change how evidence is weighed, which connections appear or how listings are ordered."],
  ["Contradictions are never suppressed.", "Objections and counter-evidence stay visible, whoever funds the work."],
  ["No promises to families.", "A campaign gathers and checks published evidence. It does not promise a treatment, a study or an outcome."],
  ["Public receipts.", "Budget, money spent on model calls, and what was added are shown here and update every quarter hour."],
];

export default function Campaigns() {
  const [rows, setRows] = useState<Campaign[] | null>(null);
  useEffect(() => {
    fetch(`${LIVE_API}/live/campaigns`).then(r => (r.ok ? r.json() : null)).then(b => setRows(b?.campaigns ?? [])).catch(() => setRows([]));
  }, []);
  const open = rows?.filter(c => c.status === "open") ?? [];
  const closed = rows?.filter(c => c.status === "closed") ?? [];
  return <div className="max-w-4xl pb-12">
    <header className="pt-12">
      <div className="eyebrow">Campaigns</div>
      <h1 className="mt-2 text-4xl font-semibold tracking-tight">Focus the atlas on a condition</h1>
      <p className="mt-4 text-lg leading-relaxed text-ink-soft">
        A campaign is a public, focused effort: one condition or a small neighborhood of related conditions, a goal, and optionally a budget for the atlas's AI scouts. Patient groups, foundations or researchers can start one. Everything it adds is checked like any other finding.
      </p>
    </header>
    {rows === null && <p className="mt-8 text-ink-faint">Loading campaigns…</p>}
    {rows && <Section title={open.length ? "Running now" : "No campaign is running right now"}>
      {open.length ? <div className="space-y-4">{open.map(c => <CampaignCard key={c.id} c={c} />)}</div>
        : <p className="text-[15px] text-ink-soft">Ask agents to work on a single condition from its page, or start a campaign as described below.</p>}
    </Section>}
    {closed.length > 0 && <Section title="Finished"><div className="space-y-4">{closed.map(c => <CampaignCard key={c.id} c={c} />)}</div></Section>}
    <Section id="start" title="Start a campaign" intro="For a patient group, foundation or research team that wants a condition, or a cluster of related conditions, mapped more completely.">
      <ol className="list-decimal space-y-2 pl-5 text-[15px] leading-relaxed text-ink-soft">
        <li>Write to the atlas operator with the conditions (their pages on the map), the goal (for example "every reported symptom with its frequency" or "every natural-history study"), and who you are.</li>
        <li>Without a budget, the campaign still moves its conditions up every connected agent's task list, at no cost.</li>
        <li>With a budget, the atlas's own scouts also spend it on reading papers for these conditions. Spending is shown here to the cent. The atlas has no payment system: funding is arranged directly with the operator.</li>
      </ol>
    </Section>
    <Section title="Rules every campaign follows">
      <ul className="space-y-3 text-[15px] leading-relaxed text-ink-soft">{RULES.map(([t, d]) => <li key={t}><b className="text-ink">{t}</b> {d}</li>)}</ul>
    </Section>
  </div>;
}

function CampaignCard({ c }: { c: Campaign }) {
  const added = c.conditions.reduce((n, x) => n + x.findings_since_start, 0);
  return <article className="rounded-2xl border border-ink-line bg-white p-5">
    <div className="flex flex-wrap items-center gap-2">
      <h3 className="text-lg font-semibold">{c.title}</h3>
      <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${c.status === "open" ? "bg-emerald-50 text-emerald-800" : "bg-ink-wash text-ink-soft"}`}>{c.status === "open" ? "Running" : "Finished"}</span>
    </div>
    <p className="mt-1 text-sm text-ink-soft">{c.goal}</p>
    <p className="mt-2 text-xs text-ink-faint">
      {c.sponsor ? <>Sponsored by {c.sponsor.url ? <a className="underline" href={c.sponsor.url} target="_blank" rel="noreferrer">{c.sponsor.name}</a> : c.sponsor.name}</> : "Run by the atlas"}
      {" · "}started {new Date(c.created * 1000).toLocaleDateString()}
      {" · "}{c.budget_usd > 0 ? `budget $${c.budget_usd.toFixed(2)}, spent $${(c.spent_usd ?? 0).toFixed(2)} on ${c.rounds ?? 0} scout round${c.rounds === 1 ? "" : "s"}` : "attention only, no budget"}
      {" · "}{added} reviewed finding{added === 1 ? "" : "s"} added so far
    </p>
    <ul className="mt-3 divide-y divide-ink-line rounded-xl border border-ink-line text-sm">
      {c.conditions.map(x => <li key={x.condition_id} className="flex flex-wrap items-baseline justify-between gap-2 px-3 py-2">
        <span><Link className="font-medium text-ink hover:text-machinery" to={routes.condition(x.condition_id)}>{x.name}</Link>{x.gene && <span className="ml-1.5 font-mono text-[11px] text-ink-faint">{x.gene}</span>}</span>
        <span className="text-xs text-ink-soft">{x.symptoms} symptom{x.symptoms === 1 ? "" : "s"} recorded · +{x.findings_since_start} since start{x.requests ? ` · ${x.requests} request${x.requests === 1 ? "" : "s"}` : ""}</span>
      </li>)}
    </ul>
  </article>;
}
