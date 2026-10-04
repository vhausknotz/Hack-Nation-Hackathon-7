// For one connection: what the two conditions share, what differs, and what an expert must check before
// two communities join forces. Built only from recorded data; nothing here is generated text.
import type { ConditionBundle, Neighbor } from "../lib/types";

const EFFECT: Record<string, string> = {
  loss_of_function: "loss of function", gain_of_function: "gain of function", dominant_negative: "dominant negative",
  non_loss_of_function: "not loss of function", unknown: "not recorded",
};

function names(c: ConditionBundle, ids: string[]) {
  return [...new Set(ids.map((h) => { const e = c.dict.symptoms[h]; const n = e?.[1] || e?.[0] || h; return n.charAt(0).toUpperCase() + n.slice(1); }))];
}

export function checks(c: ConditionBundle, n: Neighbor): string[] {
  const k = n.contrast;
  const out: string[] = [];
  const mine = c.variant_effect?.value ?? "unknown";
  const theirs = k?.their_effect ?? "unknown";
  if (n.same_gene) out.push("Same gene, different condition: check whether the variants act the same way before comparing.");
  else if (n.effect === "different") out.push(`The gene changes act differently (${EFFECT[mine] ?? mine} vs ${EFFECT[theirs] ?? theirs}): an approach that replaces a missing protein may not suit an overactive one.`);
  else if (mine === "unknown" || theirs === "unknown") out.push("How the gene change acts is not recorded for at least one of them. Ask an expert whether both lose function before assuming a shared approach.");
  else out.push(`Both are recorded as ${EFFECT[mine] ?? mine}. Confirm this holds for the variants in your community.`);
  if (c.phenotype_count < 5 || (k && k.their_symptom_count < 5)) out.push("Few symptoms are recorded for one of them, so the similarity is tentative.");
  if (n.mech_known === false && !n.same_gene) out.push("Molecular overlap is not measured for these genes; the link rests on symptoms.");
  const inh = (a: string[]) => a.map((s) => s.replace(/ inheritance$/i, "")).join(", ");
  if (k && c.inheritance.length && k.their_inheritance.length && inh(c.inheritance) !== inh(k.their_inheritance))
    out.push(`Different inheritance (${inh(c.inheritance)} vs ${inh(k.their_inheritance)}): registries and family questions may differ.`);
  if (k && c.onset.length && k.their_onset.length && c.onset[0] !== k.their_onset[0])
    out.push(`Different typical onset (${c.onset[0]} vs ${k.their_onset[0]}): natural-history measures may not line up.`);
  out.push("Shared features suggest comparing research questions, never a shared treatment.");
  return out;
}

export function Contrast({ c, n }: { c: ConditionBundle; n: Neighbor }) {
  const shared = names(c, n.symptoms).slice(0, 5);
  const k = n.contrast;
  const here = k ? names(c, k.only_here).slice(0, 3) : [];
  const there = k ? names(c, k.only_there).slice(0, 3) : [];
  return (
    <div className="mt-3 grid gap-2 text-xs">
      <div className="rounded-lg bg-machinery-soft/40 p-2.5">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-machinery">Shared</div>
        <p className="mt-1">{shared.length ? shared.join(" · ") : "No specific symptoms in common"}{n.mechanisms.length ? ` · ${n.mechanisms.length} piece${n.mechanisms.length === 1 ? "" : "s"} of shared machinery` : ""}</p>
        {k?.shared_people?.length ? <p className="mt-1"><b className="font-semibold text-ink">Researchers publishing on both genes:</b> {k.shared_people.join(", ")}. A natural first contact for a joint question.</p> : null}
      </div>
      {(here.length > 0 || there.length > 0) && (
        <div className="rounded-lg bg-ink-wash p-2.5">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">Different</div>
          {here.length > 0 && <p className="mt-1"><b className="font-semibold text-ink">Only in yours:</b> {here.join(" · ")}</p>}
          {there.length > 0 && <p className="mt-1"><b className="font-semibold text-ink">Only in {n.gene}:</b> {there.join(" · ")}</p>}
        </div>
      )}
      <div className="rounded-lg border border-caution/30 bg-caution-soft/40 p-2.5">
        <div className="text-[10px] font-semibold uppercase tracking-wide text-caution">Check with an expert before joining forces</div>
        <ul className="mt-1 list-disc space-y-1 pl-4">{checks(c, n).map((t) => <li key={t}>{t}</li>)}</ul>
      </div>
    </div>
  );
}
