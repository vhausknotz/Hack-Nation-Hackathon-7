import { useState } from "react";
import type { Community, ConditionBundle, ListingHistory, ResearchAsset } from "../lib/types";
import { reviewLabel } from "./familyJourney";

type Listing = Community | ResearchAsset;
const verdicts: Record<string, string> = {
  supports: "Source supports the listing",
  supports_with_qualification: "Supported with restrictions or qualifications",
  does_not_support: "Source did not support the claim",
  out_of_scope: "Outside the reviewer's scope",
};

function dateLabel(at: string) {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? at : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

function reviewer(r: ListingHistory["reviews"][number]) {
  return r.kind === "human" ? "Human reviewer" : `AI reviewer · ${r.model || "model not recorded"}${r.family ? ` · ${r.family}` : ""}`;
}

export function recordedReview(history?: ListingHistory): string[] {
  const r = history?.reviews.at(-1);
  return r ? [`Latest recorded review: ${r.at} · ${reviewer(r)}. This is not a new check of current availability.`] : [];
}

const RECHECK: Record<string, string> = { reaffirmed: "Rechecked: still on the page", quote_missing: "Rechecked: quote no longer on the page",
  unreachable: "Rechecked: page could not be reached", retracted: "Rechecked: the cited paper was retracted" };

function Trail({ listing }: { listing: Listing }) {
  const h = listing.history;
  if (!h) return null;
  const latest = h.reviews.at(-1);
  const name = "title" in listing ? listing.title : listing.name;
  const url = "url" in listing ? listing.url : listing.page || listing.homepage;
  return <article className="mt-3 rounded-xl border border-ink-line p-3 text-xs" data-claim-id={listing.claim_id}>
    <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">{latest ? `Reviewed ${dateLabel(latest.at)}` : "Recorded source checks"}</p>
    <h4 className="mt-1 font-semibold text-ink">{name}</h4>
    <p className="mt-1">{reviewLabel(listing.review)}</p>
    <details className="mt-2">
      <summary className="cursor-pointer font-medium text-machinery">See the check history</summary>
      <ol className="ml-1 mt-3 space-y-3 border-l border-ink-line pl-3">
        {h.sources.map(s => <li key={s.id}><b className="block text-ink">Source archived{s.archived_at ? ` · ${dateLabel(s.archived_at)}` : ""}</b><span>The atlas stored the source used for this claim.</span></li>)}
        {h.submitted_at && <li><b className="block text-ink">Claim submitted · {dateLabel(h.submitted_at)}</b><span>A proposed listing entered the evidence log.</span></li>}
        {h.kernel_checked_at && <li><b className="block text-ink">Source checks passed · {dateLabel(h.kernel_checked_at)}</b><span>Quoted text, source hashes, identifiers and signatures passed automated checks. These checks do not decide whether the claim is true.</span></li>}
        {h.reviews.map((r, i) => <li key={i}><b className="block text-ink">{verdicts[r.verdict] || r.verdict} · {dateLabel(r.at)}</b><span className="block">{reviewer(r)}</span><p className="mt-1">{r.reason}</p></li>)}
        {(h.rechecks ?? []).map((r, i) => <li key={`r${i}`}><b className="block text-ink">{RECHECK[r.result] ?? r.result} · {dateLabel(r.checked)}</b><span>{r.check === "retraction" ? "The atlas checks cited papers against PubMed's retraction notices." : "The atlas rereads the organization's page about monthly."}{r.detail ? ` ${r.detail.charAt(0).toUpperCase()}${r.detail.slice(1)}.` : ""}</span></li>)}
      </ol>
      <a href={url} target="_blank" rel="noreferrer" className="mt-3 inline-block font-medium text-machinery underline">Read the listing's source ↗</a>
      {"page_read" in listing && listing.page_read === "archived_snapshot" && <p className="mt-2 text-caution">Historical page from {listing.page_date}; the archive date above does not confirm today's activity.</p>}
      {"via" in listing && listing.via && <p className="mt-2">This gene-wide listing was recorded on another diagnosis linked to the same gene.</p>}
      <p className="mt-2 break-all text-[10px] text-ink-faint">Evidence ID: {listing.claim_id}</p>
    </details>
  </article>;
}

export function EvidenceHistory({ c }: { c: ConditionBundle }) {
  const [all, setAll] = useState(false);
  const listings: Listing[] = [...(c.assets ?? []), ...(c.communities ?? [])];
  const seen = new Set<string>();
  const records = listings.filter(l => {
    if (!l.history?.reviews.length || seen.has(l.claim_id)) return false;
    seen.add(l.claim_id);
    return true;
  }).sort((a, b) => b.history!.reviews.at(-1)!.at.localeCompare(a.history!.reviews.at(-1)!.at));
  return <section className="mt-5 border-t border-ink-line pt-4" aria-label="Recent evidence checks">
    <h3 className="font-semibold text-ink">How this part of the atlas was checked</h3>
    {records.length ? <>
      <p className="mt-2 text-xs">Recorded checks for the listings shown here. Review dates are not confirmations that a study is still recruiting or a group is active today.</p>
      {(all ? records : records.slice(0, 3)).map(l => <Trail key={l.claim_id} listing={l} />)}
      {records.length > 3 && <button className="mt-3 text-xs font-medium text-machinery" onClick={() => setAll(!all)}>{all ? "Show fewer checks" : `See all ${records.length} checked listings`}</button>}
    </> : <p className="mt-2 text-xs">No reviewed group or study listing has been recorded here yet. The map's computed connections are separate research leads.</p>}
  </section>;
}
