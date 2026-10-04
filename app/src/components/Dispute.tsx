// A listing someone has objected to: show the objection, and both sides when counter-evidence was reviewed.
// The atlas never decides which side is right.
import type { Dispute } from "../lib/types";

export function DisputeNote({ dispute, quote, review }: { dispute?: Dispute; quote?: string; review?: string }) {
  if (!dispute) return null;
  const contested = dispute.status === "contested";
  return (
    <div className={`mt-2 rounded-lg border p-2.5 text-xs ${contested ? "border-rose-200 bg-rose-50/70 text-rose-950" : "border-amber-200 bg-amber-50/70 text-amber-950"}`}>
      <p className="font-semibold">{contested ? "Contested: see both sides" : "An objection is under review"}</p>
      {!contested && <p className="mt-1">Someone questioned this listing. It stays visible while the objection is checked.</p>}
      {dispute.objections.map((o, i) => (
        <div key={i} className="mt-2">
          <p><b className="font-semibold">Objection{o.at ? ` (${o.at})` : ""}:</b> “{o.reason}”</p>
          {contested && o.counter && (
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <div className="rounded-md bg-white/70 p-2">
                <div className="text-[10px] font-semibold uppercase tracking-wide opacity-70">This listing's evidence</div>
                {quote && <p className="mt-1">“{quote}”</p>}
                {review && <p className="mt-1 opacity-80">{review}</p>}
              </div>
              <div className="rounded-md bg-white/70 p-2">
                <div className="text-[10px] font-semibold uppercase tracking-wide opacity-70">Counter-evidence</div>
                <p className="mt-1">“{o.counter.quote}”</p>
                {o.counter.review_reason && <p className="mt-1 opacity-80">Reviewer: {o.counter.review_reason}</p>}
                {o.counter.source && <a className="mt-1 block underline" href={o.counter.source} target="_blank" rel="noreferrer">Source ↗</a>}
              </div>
            </div>
          )}
        </div>
      ))}
      {contested && <p className="mt-2 opacity-80">Both sides passed checks and review. The atlas does not decide which is right, so this listing is left out of suggested questions and proposals. Ask the organization or study team directly.</p>}
    </div>
  );
}

export const isContested = (x: { dispute?: Dispute }) => x.dispute?.status === "contested";

/** Plain-text lines for the printable brief. */
export function disputeLines(d?: Dispute): string[] {
  if (!d) return [];
  return [d.status === "contested" ? "Contested: reviewed counter-evidence exists. The atlas does not decide which side is right; ask directly." : "An objection to this listing is under review.",
    ...d.objections.map((o) => `Objection${o.at ? ` (${o.at})` : ""}: “${o.reason}”${d.status === "contested" && o.counter ? ` Counter-evidence: “${o.counter.quote}”${o.counter.source ? ` (${o.counter.source})` : ""}` : ""}`)];
}
