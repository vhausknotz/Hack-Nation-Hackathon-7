import { useState } from "react";
import { Link } from "react-router-dom";
import { copyText } from "../lib/clipboard";
import type { ConditionBundle, ResearchAsset, SharedResearch } from "../lib/types";
import { routes } from "../lib/links";
import { ASSET_TYPE, reviewLabel, statusLabel, studyNotes } from "./familyJourney";
import { StudyTeamCard, teamAddress } from "./StudyTeam";

export function collaborationQuestions(c: ConditionBundle) {
  return (c.shared_research ?? []).flatMap(route => {
    const asset = c.assets?.find(a => a.id === route.asset_id);
    if (!asset) return [];
    return [{ route, asset, condition: c, question: `We are exploring research for ${c.name}. Your record ${asset.id} is listed for our diagnosis and ${route.partner.name}. Are both groups included in the current protocol? Could you share the questionnaires or data definitions used for each group, and explain what scientific review, consent and permissions would be needed to compare or reuse them?` }];
  });
}

export function SharedResearchPanel({ c }: { c: ConditionBundle }) {
  const leads = collaborationQuestions(c);
  if (!leads.length) return <div className="mb-4 rounded-xl bg-ink-wash p-3 text-xs">
    <h3 className="font-semibold text-ink">For patient-group organizers</h3>
    <p className="mt-2">We have not yet connected this diagnosis to another community through the same reviewed research record. A nearby condition on the map alone is not enough to establish a shared research opportunity.</p>
  </div>;
  return <section aria-label="Shared research for patient-group organizers" className="mb-5">
    <p className="text-[10px] font-semibold uppercase tracking-wide text-machinery">For patient-group organizers</p>
    <h3 className="mt-1 font-semibold text-ink">Research already connecting communities</h3>
    <p className="mt-2 text-xs">The same research record appears in both diagnoses' reviewed listings. This is a starting point for questions about existing infrastructure; it does not establish that cohorts can be combined.</p>
    <ResearchBridge key={`${c.id}:${leads[0].route.partner.id}`} {...leads[0]} />
    {leads.length > 1 && <details className="mt-3"><summary className="cursor-pointer text-xs font-medium text-machinery">Explore {leads.length - 1} more shared research connection{leads.length > 2 ? "s" : ""}</summary>
      {leads.slice(1).map(lead => <ResearchBridge key={`${c.id}:${lead.route.partner.id}`} {...lead} />)}
    </details>}
  </section>;
}

export function collaborationText(condition: ConditionBundle, route: SharedResearch, asset: ResearchAsset, question: string, origin: string) {
  const notes = (label: string, a: ResearchAsset) => [label, `${a.title} (${a.id})`, a.url,
    `${reviewLabel(a.review)}. ${statusLabel(a)} as recorded on ${a.source_date || "the source date"}.`,
    `Review qualification: ${a.review.reason}`,
    `Restriction, as recorded: ${a.restriction || "No restriction was extracted; this does not mean eligibility is unrestricted."}`,
    ...studyNotes(a), `Evidence ID: ${a.claim_id}`].join("\n");
  const address = teamAddress(asset.team);
  return [...(address ? ["To", address.to, `${address.greeting},`] : ["Question for the study team"]), question,
    "Context from the Rare Disease Atlas — listings to verify, not recommendations or an independently reviewed partnership proposal.",
    notes(condition.name, asset), notes(route.partner.name, route.partner_asset),
    `Full question brief: ${origin}${routes.condition(condition.id)}?brief=1`,
    "Please confirm current study inclusion, scientific suitability, consent and permissions. Source dates do not establish current recruitment or eligibility."].join("\n\n");
}

function ResearchBridge({ route, asset, question, condition }: { route: SharedResearch; asset: ResearchAsset; question: string; condition: ConditionBundle }) {
  const other = route.partner_asset;
  const [copied, setCopied] = useState<"" | "done" | "failed">("");
  const text = collaborationText(condition, route, asset, question, window.location.origin);
  return <article data-research-bridge className="mt-3 rounded-xl border border-machinery/25 bg-machinery-soft/20 p-3">
    <span className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{ASSET_TYPE[asset.type] || "Research asset"} · {asset.id}</span>
    <h4 className="mt-1 font-semibold text-ink">{asset.title}</h4>
    <p className="mt-2 text-xs">Also listed for <Link className="font-medium text-machinery underline" to={routes.condition(route.partner.id)}>{route.partner.name}</Link>.</p>
    <p className="mt-2 text-xs">{route.is_computed_neighbor ? "This condition is also a computed neighbor on the map. The shared research record is a separate, documented connection." : "Connected by this research record; this does not imply matching biology."}</p>
    <div className="mt-3 border-t border-machinery/15 pt-3">
      {asset.team && <StudyTeamCard team={asset.team} />}
      <h5 className="mt-3 text-xs font-semibold text-ink">{teamAddress(asset.team) ? `A question for ${asset.team!.officials[0]?.name.split(",")[0] ?? "the study team"}` : "A question for the study team"}</h5>
      <p className="mt-1 text-xs">“{question}”</p>
      <button onClick={async () => setCopied(await copyText(text) ? "done" : "failed")} className="mt-3 block rounded-lg border border-machinery/30 bg-white px-3 py-2 text-xs font-semibold text-machinery">{copied === "done" ? "Question copied" : "Copy question + sources"}</button>
      <p className="mt-1 text-[10px] text-ink-faint" aria-live="polite">{copied === "done" ? "Copied with both diagnoses' restrictions and review labels. Nothing was sent." : copied === "failed" ? "Copy is unavailable. Select the prepared text below to copy it manually." : "Includes both diagnoses' restrictions and review labels. Review the text before sharing."}</p>
      {copied === "failed" && <textarea readOnly aria-label="Question and sources to copy manually" value={text} className="mt-2 h-40 w-full rounded-lg border border-ink-line bg-white p-2 text-xs" />}
      <a className="mt-2 inline-block text-xs font-semibold text-machinery underline" href={asset.url} target="_blank" rel="noreferrer">Study record and team details ↗</a>
    </div>
    {route.partner_community && <p className="mt-3 text-xs">A community listed for {route.partner.gene}: <a className="font-medium text-machinery underline" href={route.partner_community.homepage} target="_blank" rel="noreferrer">{route.partner_community.name} ↗</a>. Its involvement in this study has not been established here.</p>}
    <details className="mt-3 text-xs"><summary className="cursor-pointer font-medium text-machinery">Check both diagnoses' evidence and restrictions</summary>
      <BridgeEvidence label="Your diagnosis" asset={asset} />
      <BridgeEvidence label={route.partner.name} asset={other} />
      {route.partner_community && <div className="mt-3"><p>{route.partner_community.name}: {reviewLabel(route.partner_community.review)}.</p><blockquote className="mt-1 border-l-2 border-ink-line pl-2">“{route.partner_community.quote}”</blockquote><a href={route.partner_community.page || route.partner_community.homepage} target="_blank" rel="noreferrer" className="underline">{route.partner_community.page_read === "archived_snapshot" ? "Archived source" : "Source"} · {route.partner_community.page_date}</a></div>}
      <p className="mt-3">This is a descriptive overlap, not an independently reviewed partnership proposal. Study inclusion, suitability for comparison and permission to reuse materials must be checked with the team.</p>
    </details>
  </article>;
}

function BridgeEvidence({ label, asset }: { label: string; asset: ResearchAsset }) {
  return <div className="mt-3 border-t border-ink-line pt-2">
    <h5 className="font-semibold text-ink">{label}</h5>
    <p className="mt-1">{reviewLabel(asset.review)} · {statusLabel(asset)} as recorded on {asset.source_date || "the source date"}.</p>
    <p className="mt-1">{asset.review.reason}</p>
    <p className="mt-2 whitespace-pre-wrap"><b>Restriction, as recorded:</b> {asset.restriction || "No restriction was extracted; this does not mean eligibility is unrestricted."}</p>
    {studyNotes(asset).map((note, i) => <p key={i} className="mt-2 text-caution">{note}</p>)}
    {asset.quotes.map((quote, i) => <blockquote key={i} className="mt-2 whitespace-pre-wrap border-l-2 border-ink-line pl-2">“{quote}”</blockquote>)}
    <p className="mt-2 break-all text-[10px] text-ink-faint">Evidence ID: {asset.claim_id}</p>
  </div>;
}
