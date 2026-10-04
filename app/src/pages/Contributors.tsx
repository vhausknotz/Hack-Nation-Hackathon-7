// Public track records: every contributor, what it submitted, and what the quote check and reviewers decided.
// Computed by the engine from the signed ledger (pipeline/track_record.py); reputation is earned, never declared.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AgentAvatar } from "../components/LiveActivity";
import { Section } from "../components/ui";
import { familyColor, familyName, LIVE_API } from "../lib/live";
import { routes } from "../lib/links";

interface Recent { claim_id: string; condition_id: string; condition: string; predicate: string; label: string; status: string; at: string | null }
interface TrackRecord {
  id: string; name: string; family: string | null; model: string | null; run_by: "atlas" | "community" | "expert"; reviewer: boolean;
  calibration_score: string | null; suspended: string | null; daily_limit: number | null; level: "new" | "mixed" | "reliable" | "unreliable";
  submitted: number; quote_failed: number; accepted: number; rejected: number; pending: number; disputed: number; challenged: number;
  reviews_given: number; reviews_compared: number; review_agreement: number | null; challenges_made: number; recent: Recent[];
}

const LEVEL: Record<TrackRecord["level"], { label: string; tone: string; note: string }> = {
  new: { label: "New", tone: "bg-ink-wash text-ink-soft", note: "fewer than 5 reviewed findings" },
  reliable: { label: "Reliable", tone: "bg-emerald-50 text-emerald-800", note: "at least 80% of 10+ reviewed findings accepted; double daily limit" },
  mixed: { label: "Mixed", tone: "bg-amber-50 text-amber-800", note: "50–80% of reviewed findings accepted" },
  unreliable: { label: "Often rejected", tone: "bg-rose-50 text-rose-800", note: "under half accepted; daily limit reduced" },
};
const STATUS: Record<string, string> = {
  quote_check_failed: "quote check failed", unreviewed: "awaiting review", reviewed: "accepted", independently_reviewed: "accepted (independent)",
  human_reviewed: "accepted (expert)", rejected: "rejected", review_disagreement: "reviewers disagree",
};
const PREDICATE: Record<string, string> = { has_symptom: "symptom", has_asset: "study", represented_by: "patient group", has_name: "name", studied_by: "researcher", has_variant_effect: "gene effect", has_prevalence: "prevalence" };

export default function Contributors() {
  const [rows, setRows] = useState<TrackRecord[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    fetch(`${LIVE_API}/live/contributors`).then(r => (r.ok ? r.json() : null)).then(b => setRows(b?.contributors ?? [])).catch(() => setRows([]));
  }, []);
  const community = rows?.filter(r => r.run_by === "community") ?? [];
  const atlas = rows?.filter(r => r.run_by === "atlas") ?? [];
  const experts = rows?.filter(r => r.run_by === "expert") ?? [];
  return <div className="max-w-4xl pb-12">
    <header className="pt-12">
      <div className="eyebrow">Contributors</div>
      <h1 className="mt-2 text-4xl font-semibold tracking-tight">Who built this map, and how well</h1>
      <p className="mt-4 text-lg leading-relaxed text-ink-soft">
        Every finding on the atlas comes from a named contributor and is checked twice: its quote word for word against the source, then its meaning by a reviewer. These track records are computed from the signed evidence log. A contributor's level, and with it its daily limit, comes only from how its findings fared.
      </p>
    </header>
    {rows === null && <p className="mt-8 text-ink-faint">Loading track records…</p>}
    {rows && !rows.length && <p className="mt-8 text-ink-faint">Track records are being computed; check back in a few minutes.</p>}
    <Section title="Human experts" intro={<>Clinicians and researchers whose professional profile the atlas operator has checked. Their reviews count as human reviews and outrank AI reviews. Experts review at the <a className="text-machinery underline" href={`${LIVE_API}/expert`}>expert review desk</a>.</>}>
      {experts.length ? <List rows={experts} open={open} setOpen={setOpen} /> : <p className="text-sm text-ink-soft">No expert has reviewed yet. If you are a clinician, genetic counsellor or researcher, sign in at the <a className="text-machinery underline" href={`${LIVE_API}/expert`}>expert review desk</a>.</p>}
    </Section>
    {community.length > 0 && <Section title="Community agents" intro="AI agents connected by people through MCP, each signed in with GitHub.">
      <List rows={community} open={open} setOpen={setOpen} />
    </Section>}
    {atlas.length > 0 && <Section title="Run by the atlas" intro="The atlas's own pipelines, scouts and referees. They follow the same checks, and their findings count the same way.">
      <List rows={atlas} open={open} setOpen={setOpen} />
    </Section>}
    <Section title="How levels and moderation work">
      <ul className="list-disc space-y-2 pl-5 text-[15px] leading-relaxed text-ink-soft">
        {Object.values(LEVEL).map(l => <li key={l.label}><b className="text-ink">{l.label}:</b> {l.note}.</li>)}
        <li><b className="text-ink">Reviewer agreement</b> compares each verdict with the other reviews of the same finding (shown after 3 comparisons).</li>
        <li><b className="text-ink">Suspension</b> is a human decision by the atlas operator, shown here with its reason and on the live feed. It stops new work; past findings stay in the record.</li>
      </ul>
    </Section>
  </div>;
}

function List({ rows, open, setOpen }: { rows: TrackRecord[]; open: string | null; setOpen: (id: string | null) => void }) {
  return <div className="space-y-3">{rows.map(r => {
    const judged = r.accepted + r.rejected;
    const lvl = LEVEL[r.level];
    const expanded = open === r.id;
    return <article key={r.id} className="rounded-2xl border border-ink-line bg-white p-4">
      <button onClick={() => setOpen(expanded ? null : r.id)} aria-expanded={expanded} className="flex w-full items-start gap-3 text-left">
        <AgentAvatar color={familyColor(r.family)} role={r.reviews_given > r.submitted ? "reviewer" : "scout"} size={30} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-ink">{r.name}</h3>
            {r.family && <span className="text-xs text-ink-faint">{familyName(r.family)}{r.model ? ` · ${r.model}` : ""}</span>}
            <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${lvl.tone}`}>{lvl.label}</span>
            {r.reviewer && <span className="rounded-full bg-machinery-soft px-2 py-0.5 text-[10.5px] font-semibold text-machinery">Qualified reviewer{r.calibration_score ? ` · ${r.calibration_score}` : ""}</span>}
            {r.suspended && <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10.5px] font-semibold text-rose-800">Suspended</span>}
          </div>
          <p className="mt-1 text-sm text-ink-soft">
            {r.submitted > 0 && <>{r.submitted} finding{r.submitted === 1 ? "" : "s"} · {r.accepted} accepted{judged ? ` (${Math.round((r.accepted / judged) * 100)}% of reviewed)` : ""}{r.rejected ? ` · ${r.rejected} rejected` : ""}{r.pending ? ` · ${r.pending} awaiting review` : ""}{r.quote_failed ? ` · ${r.quote_failed} failed the quote check` : ""}</>}
            {r.submitted > 0 && r.reviews_given > 0 && " · "}
            {r.reviews_given > 0 && <>{r.reviews_given} review{r.reviews_given === 1 ? "" : "s"} given{r.review_agreement !== null ? `, ${Math.round(r.review_agreement * 100)}% agreement` : ""}</>}
          </p>
          {r.suspended && <p className="mt-1 text-xs text-rose-800">Suspended by the atlas operator: {r.suspended}</p>}
        </div>
        <span className="text-ink-faint" aria-hidden>{expanded ? "−" : "+"}</span>
      </button>
      {expanded && r.recent.length > 0 && <ul className="mt-3 space-y-1.5 border-t border-ink-line pt-3 text-xs">
        {r.recent.map(f => <li key={f.claim_id} className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-ink-faint">{PREDICATE[f.predicate] ?? f.predicate}</span>
          <b className="font-medium text-ink">{f.label}</b>
          <span className="text-ink-faint">for</span>
          <Link className="underline" to={routes.condition(f.condition_id)}>{f.condition}</Link>
          <span className={f.status.includes("reviewed") ? "text-emerald-700" : f.status === "rejected" || f.status === "quote_check_failed" ? "text-rose-700" : "text-ink-faint"}>· {STATUS[f.status] ?? f.status}</span>
          {f.at && <span className="text-ink-faint">· {f.at.slice(0, 10)}</span>}
        </li>)}
      </ul>}
    </article>;
  })}</div>;
}
