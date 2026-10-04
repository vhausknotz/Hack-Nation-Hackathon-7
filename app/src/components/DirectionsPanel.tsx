import { useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useEvidence } from "./EvidenceDrawer";
import { FamilyBrief } from "./FamilyBrief";
import { SharedResearchPanel } from "./SharedResearch";
import { EvidenceHistory } from "./EvidenceHistory";
import { ASSET_TYPE, gaps, groupStudies, isSolid, orgKindLabel, orgNotes, orgScope, questions, reviewLabel, statusLabel, studyFit, studyNotes, type Question } from "./familyJourney";
import { external, routes } from "../lib/links";
import { plainReason } from "../lib/plain";
import { connectionPanel } from "../lib/reasons";
import type { Community, ConditionBundle, Neighbor, ResearchAsset } from "../lib/types";

export const STOPS = ["You are here", "Find your people", "You're not alone", "What already exists", "Prepare your questions", "What we don't know yet"];
const SHOWN_QUESTIONS = 3;

export function DirectionsPanel({ c, neighbors, step, onStep, emphasized, onEmphasize, onClose }: {
  c: ConditionBundle; neighbors: Neighbor[]; step: number; onStep: (step: number) => void;
  emphasized: string | null; onEmphasize: (id: string | null) => void; onClose: () => void;
}) {
  const brief = useBriefParam();
  const people = (c.communities ?? []).filter(o => o.kind === "patient_organization");
  const programs = (c.communities ?? []).filter(o => o.kind === "research_program");
  const focused = people.some(o => o.scope === "this_condition" && !o.via);
  const nearby = neighbors.filter(n => n.community).slice(0, 2);
  const assets = c.assets ?? [];
  const recruiting = assets.filter(a => a.status === "RECRUITING").length;
  const asks = questions(c);
  const singleReview = [...people, ...programs, ...assets].some(l => !isSolid(l.review));
  const previews = [
    c.gene.symbol,
    people.length ? `${people.length} patient-group listing${people.length === 1 ? "" : "s"}${focused ? "" : `, for ${c.gene.symbol} or broader`}` : nearby.length ? "Explore related communities" : "Not yet found in the atlas",
    neighbors.length ? "Explore three connections" : "Too little data to compare",
    assets.length || programs.length ? `${assets.length + programs.length} studies and programs${recruiting ? ` · ${recruiting} reported recruiting` : ""}` : "Not yet found in the atlas",
    `${asks.length} question${asks.length === 1 ? "" : "s"} to take with you`,
    "The gaps in this map",
  ];
  return <div className="p-5 sm:p-6">
    <div className="flex items-center justify-between gap-3">
      <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-machinery">Directions · your research path</span>
      <span className="flex shrink-0 items-center gap-1">
        <button onClick={brief.open} className="rounded-full border border-ink-line px-2.5 py-1 text-[11px] font-medium text-ink-soft hover:border-machinery/40 hover:text-machinery">Question brief</button>
        <button onClick={onClose} aria-label="Close directions" className="rounded-full px-2 py-1 text-ink-faint hover:bg-ink-wash">✕</button>
      </span>
    </div>
    <h1 className="mt-3 text-[23px] font-semibold leading-tight tracking-tight">{c.name}</h1>
    <p className="mt-2 text-sm leading-relaxed text-ink-soft">Start with your diagnosis. Find people, explore research, and leave with questions to ask.</p>
    <div className="mt-5" aria-label="Your six-step directions">
      {STOPS.map((title, i) => <section key={title} className={`relative border-l-2 pb-2 pl-5 ml-3 ${i === 5 ? "border-transparent" : "border-ink-line"}`}>
        <button onClick={() => onStep(i)} aria-expanded={step === i} aria-controls={`stop-${i}`} className="group flex w-full items-start justify-between gap-2 py-2 text-left">
          <span className={`absolute -left-[13px] mt-0.5 grid h-6 w-6 place-items-center rounded-full text-xs font-semibold ring-4 ring-white ${step === i ? "bg-machinery text-white" : "bg-ink-wash text-ink-soft"}`}>{i + 1}</span>
          <span><span className={`block text-sm font-semibold ${step === i ? "text-machinery" : "text-ink"}`}>{title}</span>{step !== i && <span className="mt-0.5 block text-xs text-ink-faint">{previews[i]}</span>}</span>
          <span className="text-ink-faint" aria-hidden>{step === i ? "−" : "+"}</span>
        </button>
        {step === i && <div id={`stop-${i}`} className="pb-4 pt-2 text-sm leading-relaxed text-ink-soft">
          {i === 0 && <>
            <p>{c.plain?.summary || `This genetic condition is linked to changes in the ${c.gene.symbol} gene. Its name is a starting point for finding relevant people and research.`}</p>
            <Link to={routes.conditionDetails(c.id)} className="mt-3 block text-xs underline underline-offset-2">{c.plain ? "AI summary from MONDO and HPO data · see sources" : "See the diagnosis sources"}</Link>
            <p className="mt-3 rounded-lg bg-ink-wash p-3 text-xs">The lights nearby are other conditions with shared features. Their position is a research lead, not a medical conclusion.</p>
          </>}
          {i === 1 && <>
            {people.length ? <>
              <p className="mb-3">{focused ? "A group focused on this diagnosis is listed. Visit its website to check whom it serves and how to get in touch." : `No group focused on this exact diagnosis has been found in the atlas yet. These groups serve people with ${c.gene.symbol} changes or a broader community. Check whether they include your diagnosis.`}</p>
              {people.map(o => <Organization key={o.id} org={o} c={c} />)}
              {singleReview && <p className="text-xs">These are listings, not recommendations. Each was checked against its own page by one AI reviewer.</p>}
            </> : <>
              <p>No patient group for this diagnosis has been found in the atlas yet. That does not mean none exists.</p>
              {nearby.length > 0 && <><p className="mt-3">These related conditions have patient groups. They may be useful contacts, but we have not checked whether they serve your condition.</p>{nearby.map(n => <Link onMouseEnter={() => onEmphasize(n.id)} key={n.id} to={routes.condition(n.id)} className="mt-3 block rounded-xl border border-ink-line p-3 text-ink"><b className="block">{n.community}</b><span className="text-xs text-ink-soft">For {n.name} · explore this connection →</span></Link>)}</>}
              <details className="mt-4"><summary className="cursor-pointer font-medium text-machinery">Help build the missing community</summary><p className="mt-2">Ask your clinical team whether they know an existing group or can introduce you through an appropriate consent process. If you start a group, a public contact page can help other families find it.</p></details>
            </>}
          </>}
          {i === 2 && <>
            {neighbors.length > 0 && <p className="mb-3">These connections could help you find people asking similar research questions. Tap one to see why it appears here.</p>}
            {neighbors.slice(0, 3).map(n => <Relative key={n.id} c={c} n={n} open={emphasized === n.id} onToggle={() => onEmphasize(emphasized === n.id ? null : n.id)} />)}
            {!neighbors.length && <p>There is too little recorded information to compare this condition reliably.</p>}
            {c.other_conditions_of_gene.length > 0 && <details className="mt-4"><summary className="cursor-pointer text-xs">Other conditions linked to {c.gene.symbol}</summary><p className="mt-2 text-xs">The same gene can act differently in different conditions. These are not automatically close connections.</p>{c.other_conditions_of_gene.slice(0, 4).map(n => <Link className="mt-2 block text-xs underline" key={n.id} to={routes.condition(n.id)}>{n.name}</Link>)}</details>}
          </>}
          {i === 3 && <Studies c={c} programs={programs} assets={assets} />}
          {i === 4 && <>
            <SharedResearchPanel c={c} />
            <p className="mb-3">Nothing here is a recommendation. These questions help you check what the atlas found: whether a group or study includes your diagnosis, and whether it is open now.</p>
            {asks.slice(0, SHOWN_QUESTIONS).map((q, k) => <QuestionCard key={k} q={q} first={k === 0} />)}
            <button onClick={brief.open} className="mt-1 flex w-full items-center justify-between rounded-xl border border-machinery/30 px-4 py-2.5 text-left text-xs font-semibold text-machinery hover:bg-machinery-soft/40">
              <span>{asks.length > SHOWN_QUESTIONS ? `See all ${asks.length} questions in your brief` : "Open your question brief"}<span className="mt-0.5 block font-normal text-ink-soft">Print or copy it, with sources, dates and restrictions</span></span><span aria-hidden>→</span>
            </button>
          </>}
          {i === 5 && <><ul className="list-disc space-y-2 pl-4">
            {gaps(c, neighbors).map((g, k) => <li key={k}>{g.text}{g.help && <span className="block text-xs text-ink-faint">{g.help}</span>}</li>)}
          </ul><EvidenceHistory key={c.id} c={c} /></>}
          {i < 5 && <button onClick={() => onStep(i + 1)} className="mt-4 flex w-full items-center justify-between rounded-xl bg-machinery px-4 py-2.5 text-xs font-semibold text-white hover:opacity-90">{STOPS[i + 1]} <span aria-hidden>→</span></button>}
        </div>}
      </section>)}
    </div>
    <Link to={routes.conditionDetails(c.id)} className="mt-4 flex items-center justify-between rounded-xl bg-ink-wash px-4 py-3 text-sm font-medium">Show the science <span aria-hidden>→</span></Link>
    <p className="mt-3 text-[11px] leading-relaxed text-ink-faint">Research coordination, not treatment advice. Connections are computed leads for experts to check.</p>
    {brief.isOpen && <FamilyBrief c={c} neighbors={neighbors} onClose={brief.close} />}
  </div>;
}

/** The brief lives at ?brief=1 on the condition's URL: shareable, other parameters kept, Back closes it. */
function useBriefParam() {
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const isOpen = params.get("brief") === "1";
  const open = () => {
    const next = new URLSearchParams(params);
    next.set("brief", "1");
    setParams(next, { state: { briefOpenedHere: true } });
  };
  const close = () => {
    if ((location.state as { briefOpenedHere?: boolean } | null)?.briefOpenedHere) return navigate(-1);
    const next = new URLSearchParams(params);
    next.delete("brief");
    setParams(next, { replace: true });
  };
  return { isOpen, open, close };
}

function Organization({ org, c }: { org: Community; c: ConditionBundle }) {
  return <article className="mb-3 rounded-xl border border-ink-line bg-white p-3">
    <span className="text-[10px] font-semibold uppercase tracking-wide text-machinery">{orgKindLabel(org)} · {orgScope(org, c)}</span>
    <h3 className="mt-1 font-semibold text-ink">{org.name}</h3>
    {orgNotes(org, c).map((n, k) => <p key={k} className={`mt-2 text-xs ${org.page_read === "archived_snapshot" && k === 0 ? "text-caution" : ""}`}>{n}</p>)}
    <a className="mt-2 inline-block text-xs font-semibold text-machinery underline" href={org.homepage} target="_blank" rel="noreferrer">Visit website ↗</a>
    <details className="mt-2 text-xs"><summary className="cursor-pointer text-ink-faint">Why it is listed · source and review</summary><p className="mt-2">{org.review.reason}</p><blockquote className="mt-2 border-l-2 border-ink-line pl-2">“{org.quote}”</blockquote><a href={org.page || org.homepage} target="_blank" rel="noreferrer" className="mt-2 block underline">{org.page_read === "archived_snapshot" ? `Read archived source from ${org.page_date}` : `Source read ${org.page_date}`} ↗</a><p className="mt-2">{reviewLabel(org.review)}</p>{org.kind_source && <div className="mt-3 border-t border-ink-line pt-2"><p>How the organization describes its work:</p><blockquote className="mt-1">“{org.kind_source.quote}”</blockquote><a className="mt-2 block underline" href={org.kind_source.url} target="_blank" rel="noreferrer">Organization profile · read {org.kind_source.page_date} ↗</a></div>}</details>
  </article>;
}

function Studies({ c, programs, assets }: { c: ConditionBundle; programs: Community[]; assets: ResearchAsset[] }) {
  const [all, setAll] = useState(false);
  const groups = groupStudies(assets);
  if (!assets.length && !programs.length) return <>
    <p>No reviewed studies for this condition have been found in the atlas yet. Our coverage is incomplete; this does not mean no research exists.</p>
    <a href={external.trialsSearch(c.gene.symbol)} target="_blank" rel="noreferrer" className="mt-3 block text-xs underline">Search ClinicalTrials.gov for {c.gene.symbol} ↗</a>
  </>;
  return <>
    <p className="mb-3">Research we found. A listing does not mean you qualify, that enrollment is open, or that a treatment works. Check the current record with the study team.</p>
    {programs.length > 0 && <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Research programs</h3>}
    {programs.map(o => <Organization key={o.id} org={o} c={c} />)}
    {groups.map((g, k) => {
      const shown = all || k === 0 ? g.assets : [];
      return <div key={g.key} className="mt-4">
        <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">{g.heading} · {g.assets.length}</h3>
        {(all ? shown : shown.slice(0, 3)).map(a => <Study key={a.id} asset={a} />)}
      </div>;
    })}
    {(groups.length > 1 || (groups[0]?.assets.length ?? 0) > 3) && <button onClick={() => setAll(!all)} className="mb-3 mt-1 font-medium text-machinery">{all ? "Show fewer studies" : `See all ${assets.length} studies`}</button>}
    <a href={external.trialsSearch(c.gene.symbol)} target="_blank" rel="noreferrer" className="mt-2 block text-xs underline">Search ClinicalTrials.gov for {c.gene.symbol} ↗</a>
  </>;
}

function Study({ asset: a }: { asset: ResearchAsset }) {
  const fit = studyFit(a);
  return <article className="mb-3 rounded-xl border border-ink-line bg-white p-3">
    <span className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{ASSET_TYPE[a.type] || "Research study"}</span>
    <h3 className="mt-1 font-semibold leading-snug text-ink">{a.title}</h3>
    <div className="mt-2 flex flex-wrap gap-1.5 text-[10px]"><span className="rounded-full bg-ink-wash px-2 py-0.5">{statusLabel(a)} · as recorded</span><span className={`rounded-full px-2 py-0.5 ${fit.limited ? "bg-caution-soft text-caution" : "bg-machinery-soft text-machinery"}`}>{fit.label}</span></div>
    {a.restriction && <p className="mt-2 whitespace-pre-wrap text-xs"><b className="font-semibold text-ink">Restriction:</b> {a.restriction}</p>}
    <p className="mt-2 text-xs">{a.review.reason}</p>
    {studyNotes(a).slice(0, -1).map((n, k) => <p key={k} className="mt-2 text-xs text-caution">{n}</p>)}
    <a className="mt-3 inline-block text-xs font-semibold text-machinery underline" href={a.url} target="_blank" rel="noreferrer">Check study and eligibility ↗</a>
    <details className="mt-2 text-xs"><summary className="cursor-pointer text-ink-faint">Source and review</summary>{a.quotes.map((q, i) => <blockquote className="mt-2 border-l-2 border-ink-line pl-2" key={i}>“{q}”</blockquote>)}<p className="mt-2">{reviewLabel(a.review)} · record read {a.source_date || "on the archived source date"}. Recruitment may have changed.</p></details>
  </article>;
}

function QuestionCard({ q, first }: { q: Question; first: boolean }) {
  return <article className={`mb-3 rounded-xl border p-3 ${first ? "border-machinery/20 bg-machinery-soft/40" : "border-ink-line bg-white"}`}>
    <h3 className="font-semibold text-ink">{first ? "Prepare one question for your care team" : `Ask ${q.to}`}</h3>
    {q.about && <p className="mt-0.5 text-xs text-ink-faint">{q.about}</p>}
    <p className="mt-2">“{q.text}”</p>
    {q.note && <p className="mt-2 text-xs">{q.note}</p>}
    {q.url && <a className="mt-2 inline-block text-xs font-semibold text-machinery underline" href={q.url} target="_blank" rel="noreferrer">Their page ↗</a>}
    {q.review && <p className="mt-1 text-[11px] text-ink-faint">Listed, not recommended · {q.review}</p>}
  </article>;
}

function Relative({ c, n, open, onToggle }: { c: ConditionBundle; n: Neighbor; open: boolean; onToggle: () => void }) {
  const evidence = useEvidence();
  return <article className={`mb-2 rounded-xl border ${open ? "border-machinery/40 bg-machinery-soft/30" : "border-ink-line"}`}>
    <button aria-expanded={open} onClick={onToggle} className="w-full p-3 text-left"><span className="block font-semibold text-ink">{n.name}</span><span className="mt-1 block text-xs">{plainReason(c, n)}</span><span className="mt-2 block text-[11px] font-medium text-machinery">{n.community ? `A community to explore: ${n.community}` : n.asset_count ? `${n.asset_count} research listings to explore` : "A lead for comparing research questions"}</span></button>
    {open && <div className="border-t border-ink-line p-3 text-xs"><p>Shared features make this a lead to investigate. They do not establish shared treatment or study eligibility.</p><div className="mt-3 flex flex-wrap gap-3"><button onClick={() => evidence(connectionPanel(c, n))} className="font-medium text-machinery underline">Why connected?</button><Link to={routes.condition(n.id)} className="font-medium text-machinery underline">Explore on the map →</Link></div></div>}
  </article>;
}
