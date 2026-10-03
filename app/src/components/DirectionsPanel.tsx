import { useState } from "react";
import { Link } from "react-router-dom";
import { useEvidence } from "./EvidenceDrawer";
import { external, routes } from "../lib/links";
import { plainReason } from "../lib/plain";
import { connectionPanel } from "../lib/reasons";
import type { ActionReview, Community, ConditionBundle, Neighbor, ResearchAsset } from "../lib/types";

export const STOPS = ["You are here", "Find your people", "You're not alone", "What already exists", "Your next step this week", "What we don't know yet"];
const TYPE: Record<string, string> = { registry: "Patient registry", natural_history_study: "How the condition changes over time", biomarker: "Finding ways to track the condition", outcome_measure: "Measuring change", biorepository: "A bank of research samples", trial: "Clinical trial", therapy_program: "Treatment research", model: "Laboratory model" };
const STATUS: Record<string, string> = { RECRUITING: "Recruiting", NOT_YET_RECRUITING: "Not yet recruiting", ENROLLING_BY_INVITATION: "By invitation", ACTIVE_NOT_RECRUITING: "Not taking new participants", COMPLETED: "Completed", TERMINATED: "Stopped early", WITHDRAWN: "Withdrawn", SUSPENDED: "Paused", UNKNOWN: "Current status unknown" };
const solid = (review: ActionReview) => ["independently_reviewed", "human_reviewed"].includes(review.status);
const reviewLabel = (review: ActionReview) => review.status === "human_reviewed" ? "Reviewed by a person" : review.status === "independently_reviewed" ? "Checked by independent reviewers" : "Checked against its source by one AI reviewer";

export function DirectionsPanel({ c, neighbors, step, onStep, emphasized, onEmphasize, onClose }: {
  c: ConditionBundle; neighbors: Neighbor[]; step: number; onStep: (step: number) => void;
  emphasized: string | null; onEmphasize: (id: string | null) => void; onClose: () => void;
}) {
  const [moreStudies, setMoreStudies] = useState(false);
  const people = (c.communities ?? []).filter(o => o.kind === "patient_organization");
  const programs = (c.communities ?? []).filter(o => o.kind === "research_program");
  const nearby = neighbors.filter(n => n.community).slice(0, 2);
  const assets = c.assets ?? [];
  const nextOrg = people.find(o => solid(o.review) && o.page_read === "live" && o.scope !== "broader_group");
  const nextStudy = assets.find(a => solid(a.review) && a.status === "RECRUITING");
  const previews = [c.gene.symbol, people.length ? `${people.length} patient-group listing${people.length === 1 ? "" : "s"}` : nearby.length ? "Explore related communities" : "A community still to find", "Explore three connections", assets.length || programs.length ? `${assets.length + programs.length} studies and programs` : "Research still to map", "One question to take forward", "The gaps in this map"];
  return <div className="p-5 sm:p-6">
    <div className="flex items-center justify-between gap-3">
      <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-machinery">Directions · your research path</span>
      <button onClick={onClose} aria-label="Close directions" className="rounded-full px-2 py-1 text-ink-faint hover:bg-ink-wash">✕</button>
    </div>
    <h1 className="mt-3 text-[23px] font-semibold leading-tight tracking-tight">{c.name}</h1>
    <p className="mt-2 text-sm leading-relaxed text-ink-soft">Start with your diagnosis. Find people, explore research, and leave with a question to ask.</p>
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
            {people.length ? <><p className="mb-3">Start by visiting a group's website. Check whom it serves and how to get in touch.</p>{people.slice(0, 3).map(o => <Organization key={o.id} org={o} />)}</> : <>
              <p>We haven't confirmed a patient group for this diagnosis yet. That does not mean none exists.</p>
              {nearby.length > 0 && <><p className="mt-3">These related conditions have patient groups. They may be useful contacts, but we have not checked whether they serve your condition.</p>{nearby.map(n => <Link onMouseEnter={() => onEmphasize(n.id)} key={n.id} to={routes.condition(n.id)} className="mt-3 block rounded-xl border border-ink-line p-3 text-ink"><b className="block">{n.community}</b><span className="text-xs text-ink-soft">For {n.name} · explore this connection →</span></Link>)}</>}
              <details className="mt-4"><summary className="cursor-pointer font-medium text-machinery">Help build the missing community</summary><p className="mt-2">Ask your clinical team whether they know an existing group or can introduce you through an appropriate consent process. If you start a group, a public contact page can help other families find it.</p></details>
            </>}
          </>}
          {i === 2 && <>
            <p className="mb-3">These connections could help you find people asking similar research questions. Tap one to see why it appears here.</p>
            {neighbors.slice(0, 3).map(n => <Relative key={n.id} c={c} n={n} open={emphasized === n.id} onToggle={() => onEmphasize(emphasized === n.id ? null : n.id)} />)}
            {!neighbors.length && <p>There is too little recorded information to compare this condition reliably.</p>}
            {c.other_conditions_of_gene.length > 0 && <details className="mt-4"><summary className="cursor-pointer text-xs">Other conditions linked to {c.gene.symbol}</summary><p className="mt-2 text-xs">The same gene can act differently in different conditions. These are not automatically close connections.</p>{c.other_conditions_of_gene.slice(0, 4).map(n => <Link className="mt-2 block text-xs underline" key={n.id} to={routes.condition(n.id)}>{n.name}</Link>)}</details>}
          </>}
          {i === 3 && <>
            {assets.length + programs.length > 0 ? <p className="mb-3">Research you can explore. A listing does not mean you qualify or that a treatment works. Check the current record with the study team.</p> : <p>No reviewed studies are mapped here yet. Our coverage is incomplete; this is not evidence that no research exists.</p>}
            {programs.map(o => <Organization key={o.id} org={o} />)}
            {(moreStudies ? assets : assets.slice(0, 3)).map(a => <Study key={a.id} asset={a} />)}
            {assets.length > 3 && <button onClick={() => setMoreStudies(!moreStudies)} className="mb-3 font-medium text-machinery">{moreStudies ? "Show fewer studies" : `See all ${assets.length} studies`}</button>}
            <a href={external.trialsSearch(c.gene.symbol)} target="_blank" rel="noreferrer" className="mt-2 block text-xs underline">Search ClinicalTrials.gov for {c.gene.symbol} ↗</a>
          </>}
          {i === 4 && <div className="rounded-xl border border-machinery/20 bg-machinery-soft/40 p-4">
            {nextOrg ? <><h3 className="font-semibold text-ink">Contact {nextOrg.name}</h3><p className="mt-2">Ask: “Does your group support families with {c.name}, and where should we start?”</p><a className="mt-3 block font-medium text-machinery underline" href={nextOrg.homepage} target="_blank" rel="noreferrer">Visit their website ↗</a><p className="mt-2 text-xs">{reviewLabel(nextOrg.review)}</p></> : nextStudy ? <><h3 className="font-semibold text-ink">Ask about this study</h3><p className="mt-2">Take {nextStudy.title} to your clinical team and ask whether its eligibility criteria fit your diagnosis.</p>{nextStudy.restriction && <p className="mt-2 text-xs">Restriction: {nextStudy.restriction}</p>}<a className="mt-3 block underline" href={nextStudy.url} target="_blank" rel="noreferrer">Study and eligibility ↗</a><p className="mt-2 text-xs">{reviewLabel(nextStudy.review)}</p></> : <>
              <h3 className="font-semibold text-ink">Prepare one question for your care team</h3>
              <p className="mt-2">“My diagnosis is {c.name}, linked to {c.gene.symbol}. Which patient group or research registry should I ask about?”</p>
              <Link className="mt-3 block text-xs underline" to={routes.conditionDetails(c.id)}>Take the diagnosis sources with you →</Link>
              <p className="mt-3 text-xs">We don't yet have enough independent review to recommend a particular group or study as your next step.</p>
            </>}
          </div>}
          {i === 5 && <>
            <ul className="list-disc space-y-2 pl-4">
              {!people.length && <li>A patient group for this diagnosis is still unconfirmed. A current page naming whom it serves would help.</li>}
              {!assets.length && <li>Study coverage is incomplete. An eligible population named in a study record would help fill this gap.</li>}
              {c.variant_effect.value === "unknown" && <li>We don't have a clear recorded account of how these gene changes work. Expert review could change which connections are useful.</li>}
              <li>A connection on the map does not establish that two conditions can share a treatment or join the same study. That requires further evidence and expert assessment.</li>
              <li>Websites and recruitment status can change. Source dates tell you when a record was read, not that it is current today.</li>
            </ul>
          </>}
          {i < 5 && <button onClick={() => onStep(i + 1)} className="mt-4 flex w-full items-center justify-between rounded-xl bg-machinery px-4 py-2.5 text-xs font-semibold text-white hover:opacity-90">{STOPS[i + 1]} <span aria-hidden>→</span></button>}
        </div>}
      </section>)}
    </div>
    <Link to={routes.conditionDetails(c.id)} className="mt-4 flex items-center justify-between rounded-xl bg-ink-wash px-4 py-3 text-sm font-medium">Show the science <span aria-hidden>→</span></Link>
    <p className="mt-3 text-[11px] leading-relaxed text-ink-faint">Research coordination, not treatment advice. Connections are computed leads for experts to check.</p>
  </div>;
}

function Organization({ org }: { org: Community }) {
  return <article className="mb-3 rounded-xl border border-ink-line bg-white p-3">
    <span className="text-[10px] font-semibold uppercase tracking-wide text-machinery">{org.kind === "patient_organization" ? "Patient group" : "Research program"} · {org.scope === "this_condition" ? "This diagnosis" : org.scope === "this_gene" ? "This gene" : "A broader community"}</span>
    <h3 className="mt-1 font-semibold text-ink">{org.name}</h3>
    {org.page_read === "archived_snapshot" && <p className="mt-2 text-xs text-caution">Archived copy from {org.page_date}; check their site for current activity.</p>}
    <a className="mt-2 inline-block text-xs font-semibold text-machinery underline" href={org.homepage} target="_blank" rel="noreferrer">Visit website ↗</a>
    <details className="mt-2 text-xs"><summary className="cursor-pointer text-ink-faint">Why it is listed · source and review</summary><p className="mt-2">{org.review.reason}</p><blockquote className="mt-2 border-l-2 border-ink-line pl-2">“{org.quote}”</blockquote><a href={org.page || org.homepage} target="_blank" rel="noreferrer" className="mt-2 block underline">{org.page_read === "archived_snapshot" ? "Read archived source" : `Source read ${org.page_date}`} ↗</a><p className="mt-2">{reviewLabel(org.review)}</p>{org.kind_source && <div className="mt-3 border-t border-ink-line pt-2"><p>How the organization describes its work:</p><blockquote className="mt-1">“{org.kind_source.quote}”</blockquote><a className="mt-2 block underline" href={org.kind_source.url} target="_blank" rel="noreferrer">Organization profile · read {org.kind_source.page_date} ↗</a></div>}</details>
  </article>;
}

function Study({ asset: a }: { asset: ResearchAsset }) {
  const limited = !!a.restriction || a.review.verdict === "supports_with_qualification";
  return <article className="mb-3 rounded-xl border border-ink-line bg-white p-3">
    <span className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{TYPE[a.type] || "Research study"}</span>
    <h3 className="mt-1 font-semibold leading-snug text-ink">{a.title}</h3>
    <div className="mt-2 flex flex-wrap gap-1.5 text-[10px]"><span className="rounded-full bg-ink-wash px-2 py-0.5">{STATUS[a.status] || "Check recruitment status"}</span><span className={`rounded-full px-2 py-0.5 ${limited ? "bg-caution-soft text-caution" : "bg-machinery-soft text-machinery"}`}>{a.restriction ? "Only some patients" : limited ? "Ask an expert" : "Includes your condition"}</span></div>
    {a.restriction && <p className="mt-2 text-xs">{a.restriction}</p>}
    <p className="mt-2 text-xs">{a.review.reason}</p>
    <a className="mt-3 inline-block text-xs font-semibold text-machinery underline" href={a.url} target="_blank" rel="noreferrer">Check study and eligibility ↗</a>
    <details className="mt-2 text-xs"><summary className="cursor-pointer text-ink-faint">Source and review</summary>{a.quotes.map((q, i) => <blockquote className="mt-2 border-l-2 border-ink-line pl-2" key={i}>“{q}”</blockquote>)}<p className="mt-2">{reviewLabel(a.review)} · record read {a.source_date || "on the archived source date"}. Recruitment may have changed.</p></details>
  </article>;
}

function Relative({ c, n, open, onToggle }: { c: ConditionBundle; n: Neighbor; open: boolean; onToggle: () => void }) {
  const evidence = useEvidence();
  return <article className={`mb-2 rounded-xl border ${open ? "border-machinery/40 bg-machinery-soft/30" : "border-ink-line"}`}>
    <button aria-expanded={open} onClick={onToggle} className="w-full p-3 text-left"><span className="block font-semibold text-ink">{n.name}</span><span className="mt-1 block text-xs">{plainReason(c, n)}</span><span className="mt-2 block text-[11px] font-medium text-machinery">{n.community ? `A community to explore: ${n.community}` : n.asset_count ? `${n.asset_count} research listings to explore` : "A lead for comparing research questions"}</span></button>
    {open && <div className="border-t border-ink-line p-3 text-xs"><p>Shared features make this a lead to investigate. They do not establish shared treatment or study eligibility.</p><div className="mt-3 flex flex-wrap gap-3"><button onClick={() => evidence(connectionPanel(c, n))} className="font-medium text-machinery underline">Why connected?</button><Link to={routes.condition(n.id)} className="font-medium text-machinery underline">Explore on the map →</Link></div></div>}
  </article>;
}
