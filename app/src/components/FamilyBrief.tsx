// The research-question brief: what the atlas found for one diagnosis, as listings to verify, with exact
// source URLs, read dates, restrictions, gaps and questions. Printable and copyable as plain text.
// The on-screen brief and the copied text are rendered from the same model.
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { getMeta } from "../lib/data";
import { external, routes } from "../lib/links";
import { plainReason } from "../lib/plain";
import { collaborationQuestions } from "./SharedResearch";
import { checks } from "./Contrast";
import { teamAddress } from "./StudyTeam";
import { disputeLines } from "./Dispute";
import { recordedReview } from "./EvidenceHistory";
import { copyText } from "../lib/clipboard";
import type { ConditionBundle, Neighbor } from "../lib/types";
import { ASSET_TYPE, gaps, groupStudies, orgKindLabel, orgNotes, orgScope, questions, researchQuestions, reviewLabel, statusLabel, studyFit, studyNotes } from "./familyJourney";

export interface BriefItem { title: string; subtitle?: string; url?: string; facts: string[]; cautions: string[] }
export interface BriefBlock { heading?: string; items?: BriefItem[]; bullets?: string[] }
export interface BriefSection { id: string; title: string; intro?: string; blocks: BriefBlock[] }
export interface Brief { title: string; condition: string; prepared: string; atlasUrl: string; notice: string; sections: BriefSection[]; footer: string[] }

const NOTICE = "This brief lists what the Rare Disease Atlas found, so you can check it. It is not a recommendation: nothing here means you are eligible for a study, that a treatment works, or that a group or study suits you. Research coordination, not medical advice.";

export function buildBrief(c: ConditionBundle, neighbors: Neighbor[], built: string | null, origin: string, today: string): Brief {
  const atlasUrl = origin + routes.condition(c.id);
  const orgs = c.communities ?? [];
  const people = orgs.filter((o) => o.kind === "patient_organization");
  const programs = orgs.filter((o) => o.kind === "research_program");
  const assets = c.assets ?? [];
  const lower = (xs: string[], suffix: string) => xs.map((x) => x.replace(suffix, "").toLowerCase()).join(", ");

  const diagnosis: BriefItem = {
    title: c.name, subtitle: c.disease, url: c.url,
    facts: [
      ...(c.also_known_as.length ? [`Also known as: ${c.also_known_as.slice(0, 3).join("; ")}`] : []),
      ...(c.inheritance.length ? [`Inheritance: ${lower(c.inheritance, " inheritance")}`] : []),
      ...(c.onset.length ? [`Onset: ${lower(c.onset, " onset")}`] : []),
      ...(c.plain?.summary ? [`Plain summary, written by AI from MONDO and HPO data: ${c.plain.summary}`] : []),
    ],
    cautions: [],
  };
  const gene: BriefItem = { title: `Gene: ${c.gene.symbol}`, subtitle: `${c.gene.name} (${c.gene.hgnc_id})`, url: external.hgnc(c.gene.hgnc_id), facts: [], cautions: [] };

  const orgItem = (o: (typeof orgs)[number]): BriefItem => ({
    title: o.name, subtitle: `${orgKindLabel(o)} · ${orgScope(o, c)}`, url: o.homepage,
    facts: [
      `${o.page_read === "archived_snapshot" ? "Archived source read" : "Source read"} ${o.page_date}: ${o.page || o.homepage}`,
      `Why listed: ${o.review.reason}`,
      `${reviewLabel(o.review)}. Listed, not recommended.`,
      ...recordedReview(o.history),
    ],
    cautions: [...disputeLines(o.dispute), ...orgNotes(o, c)],
  });

  const studyBlocks: BriefBlock[] = [];
  if (programs.length) studyBlocks.push({ heading: "Research programs", items: programs.map(orgItem) });
  for (const g of groupStudies(assets))
    studyBlocks.push({
      heading: g.heading,
      items: g.assets.map((a) => ({
        title: a.title, subtitle: `${ASSET_TYPE[a.type] || "Research study"} · ${statusLabel(a)} as recorded on ${a.source_date || "the source date"}`, url: a.url,
        facts: [
          `How it relates to your diagnosis: ${studyFit(a).label}`,
          ...(a.restriction ? [`Restriction, as recorded: ${a.restriction}`] : []),
          `Why listed: ${a.review.reason}`,
          `${reviewLabel(a.review)}. Listed, not recommended.`,
          ...recordedReview(a.history),
        ],
        cautions: [...disputeLines(a.dispute), ...studyNotes(a)],
      })),
    });
  if (!studyBlocks.length) studyBlocks.push({ bullets: [
    "No reviewed studies for this condition have been found in the atlas yet. Our coverage is incomplete; this does not mean no research exists.",
    `To search the registry yourself: ${external.trialsSearch(c.gene.symbol)}`,
  ] });

  const asks = questions(c);
  const open = researchQuestions(c);

  return {
    title: "Research question brief", condition: c.name,
    prepared: `Prepared ${today} from the Rare Disease Atlas${built ? ` (data built ${built})` : ""}.`,
    atlasUrl, notice: NOTICE,
    sections: [
      { id: "diagnosis", title: "Diagnosis", blocks: [{ items: [diagnosis, gene] }] },
      {
        id: "groups", title: "Patient groups found",
        intro: people.length ? "Listings to check, not recommendations. Visit each group's current page to see whom it serves." : undefined,
        blocks: people.length ? [{ items: people.map(orgItem) }] : [{ bullets: ["No patient group for this diagnosis has been found in the atlas yet. That does not mean none exists."] }],
      },
      {
        id: "studies", title: "Studies and research programs found",
        intro: studyBlocks[0].items ? "Status is as the registry reported it on the date shown. Recruiting does not mean you are eligible. Check the current record with the study team." : undefined,
        blocks: studyBlocks,
      },
      {
        id: "collaboration", title: "Partnership proposal draft: shared research",
        intro: "A sourced starting point for contacting a study team that already includes another community. It rests on reviewed listings of the same research record for both diagnoses. This draft is not an independently reviewed partnership proposal, evidence of matching biology, or permission to combine cohorts.",
        blocks: collaborationQuestions(c).length ? collaborationQuestions(c).map(({ route, asset, question }) => {
          const team = asset.team;
          const address = teamAddress(team);
          const neighbor = neighbors.find((n) => n.id === route.partner.id) ?? c.neighbors.find((n) => n.id === route.partner.id);
          const sym = (ids: string[]) => ids.map((h) => c.dict.symptoms[h]?.[1] || c.dict.symptoms[h]?.[0] || h).slice(0, 5).join(", ");
          return {
            heading: `${asset.id}: ${asset.title}`,
            items: [
              { title: "1. Who to approach", url: asset.url,
                facts: team ? [
                  ...(team.officials[0] ? [`${team.officials[0].name}${team.officials[0].affiliation ? `, ${team.officials[0].affiliation}` : ""} (${team.officials[0].role || "investigator"})`] : []),
                  ...(team.sponsor ? [`Sponsor: ${team.sponsor}${team.collaborators.length ? `; collaborators: ${team.collaborators.join(", ")}` : ""}`] : []),
                  ...team.contacts.filter((x) => x.email).slice(0, 2).map((x) => `Public study contact: ${x.name ? x.name + ", " : ""}${x.email}`),
                  ...(team.sites ? [`${team.sites} site(s)${team.countries.length ? ` in ${team.countries.join(", ")}` : ""}`] : []),
                  `From the official ClinicalTrials.gov record${team.updated ? `, updated ${team.updated}` : ""}.`,
                ] : ["The registry record lists no named team; use the contact route on the study record."],
                cautions: ["Use the study's public contact route. Do not share any person's medical details in a first message."] },
              { title: "2. What we propose",
                facts: [
                  address ? `${address.greeting}, ${question}` : question,
                  "Concretely: (a) confirm whether people with our diagnosis are, or could be, included under the current protocol; (b) share the questionnaires, outcome measures and data definitions used, so our community can align its registry; (c) tell us what an amendment, consent or data-sharing agreement would require; (d) suggest who else should be involved.",
                ], cautions: [] },
              { title: `3. Why our communities connect: ${route.partner.name}`, url: origin + routes.condition(route.partner.id),
                facts: [
                  `The same study record is a reviewed listing for both diagnoses (${asset.id}).`,
                  ...(neighbor ? [
                    `The two conditions are also computed neighbors on the map: ${plainReason(c, neighbor)}`,
                    ...(neighbor.symptoms.length ? [`Shared recorded signs: ${sym(neighbor.symptoms)}.`] : []),
                    ...(neighbor.contrast?.only_here.length ? [`Only recorded for ours: ${sym(neighbor.contrast.only_here)}.`] : []),
                    ...(neighbor.contrast?.only_there.length ? [`Only recorded for ${route.partner.gene}: ${sym(neighbor.contrast.only_there)}.`] : []),
                  ] : ["The shared study is the documented link; biological similarity has not been established here."]),
                  ...(route.partner_community ? [`Community listed for ${route.partner.gene}: ${route.partner_community.name} (${route.partner_community.homepage}). Its involvement in this study has not been established.`,
                    `${route.partner_community.page_read === "archived_snapshot" ? "Archived source read" : "Source read"} ${route.partner_community.page_date}: “${route.partner_community.quote}”`] : []),
                ], cautions: [] },
              { title: "4. What must be checked first",
                facts: [
                  ...(neighbor ? checks(c, neighbor) : ["Whether the two conditions share mechanism or presentation has not been assessed here; ask the study team."]),
                  `Restriction for our diagnosis, as recorded: ${asset.restriction || "No restriction was extracted; this does not mean eligibility is unrestricted."}`,
                  `For ${route.partner.name}: Restriction, as recorded: ${route.partner_asset.restriction || "No restriction was extracted; this does not mean eligibility is unrestricted."}`,
                ], cautions: [...studyNotes(asset), ...studyNotes(route.partner_asset)] },
              { title: "5. Evidence", url: asset.url,
                facts: [
                  `Our diagnosis: ${reviewLabel(asset.review)}. ${statusLabel(asset)} as recorded on ${asset.source_date}. Why listed: ${asset.review.reason} Evidence ID ${asset.claim_id}.`,
                  `${route.partner.name}: ${reviewLabel(route.partner_asset.review)}. ${statusLabel(route.partner_asset)} as recorded on ${route.partner_asset.source_date}. Why listed: ${route.partner_asset.review.reason} Evidence ID ${route.partner_asset.claim_id}.`,
                  ...route.partner_asset.quotes.map((q) => `Source quote: “${q}”`),
                ], cautions: ["Recruitment and protocols change; the study team's current record is authoritative."] },
            ],
          };
        }) : [{ bullets: ["No shared research record has been found for this diagnosis in the reviewed atlas listings yet. A nearby condition on the map alone does not establish a shared research opportunity."] }],
      },
      {
        id: "questions", title: "Questions to take with you",
        intro: "Questions to check what the atlas found. Asking them does not imply that a group or study suits you.",
        blocks: [
          { items: asks.map((q) => ({ title: `Ask ${q.to}`, subtitle: q.about, url: q.url, facts: [`“${q.text}”`, ...(q.review ? [`${q.review}. Listed, not recommended.`] : [])], cautions: q.note ? [q.note] : [] })) },
          ...(open.length ? [{ heading: "Open questions for a group or researcher", bullets: open }] : []),
        ],
      },
      {
        id: "related", title: "Related conditions (computed leads)",
        intro: "Computed from shared symptoms and biology. A lead to discuss with a researcher, not evidence of shared treatment or study eligibility.",
        blocks: neighbors.length
          ? [{ items: neighbors.slice(0, 3).map((n) => ({ title: n.name, subtitle: `Gene: ${n.gene}`, url: origin + routes.condition(n.id), facts: [plainReason(c, n)], cautions: [] })) }]
          : [{ bullets: ["There is too little recorded information to compute connections to other conditions."] }],
      },
      { id: "gaps", title: "What we don't know yet", blocks: [{ bullets: gaps(c, neighbors).map((g) => (g.help ? `${g.text} ${g.help}` : g.text)) }] },
    ],
    footer: [
      `Atlas page: ${atlasUrl}`,
      "Every listing shows who checked it and when its source was read. Websites and recruitment change; check the current page before acting.",
    ],
  };
}

export function briefText(b: Brief): string {
  const out = [b.title.toUpperCase(), b.condition, b.prepared, "", b.notice];
  for (const s of b.sections) {
    out.push("", `== ${s.title.toUpperCase()} ==`);
    if (s.intro) out.push(s.intro);
    for (const block of s.blocks) {
      if (block.heading) out.push("", `-- ${block.heading} --`);
      for (const it of block.items ?? []) {
        out.push("", `* ${it.title}`);
        if (it.subtitle) out.push(`  ${it.subtitle}`);
        if (it.url) out.push(`  ${it.url}`);
        for (const f of it.facts) out.push(`  ${f}`);
        for (const c of it.cautions) out.push(`  ! ${c}`);
      }
      if (block.bullets) out.push("", ...block.bullets.map((x) => `- ${x}`));
    }
  }
  out.push("", "--", ...b.footer);
  return out.join("\n");
}

export function FamilyBrief({ c, neighbors, onClose }: { c: ConditionBundle; neighbors: Neighbor[]; onClose: () => void }) {
  const [built, setBuilt] = useState<string | null>(null);
  const [copied, setCopied] = useState<"" | "done" | "failed">("");
  const heading = useRef<HTMLHeadingElement>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const root = document.getElementById("root");
    const wasInert = root?.inert ?? false;
    if (root) root.inert = true;
    getMeta().then((m) => setBuilt(m.built)).catch(() => {});
    heading.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); close.current(); }
      if (e.key !== "Tab") return;
      const items = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], [tabindex="0"]') ?? []);
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === heading.current)) {
        e.preventDefault(); last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      if (root) root.inert = wasInert;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);
  const brief = buildBrief(c, neighbors, built, window.location.origin, new Date().toLocaleDateString("en-CA"));
  const copy = async () => setCopied((await copyText(briefText(brief))) ? "done" : "failed");

  return createPortal(<div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="family-brief-title" data-family-brief className="fixed inset-0 z-50 overflow-y-auto bg-white text-ink print:static print:overflow-visible">
    <style>{"@media print { #root { display: none !important; } @page { margin: 14mm; } }"}</style>
    <div className="sticky top-0 z-10 border-b border-ink-line bg-white/95 backdrop-blur print:hidden">
      <div className="mx-auto flex max-w-3xl items-center gap-2 px-4 py-3">
        <button onClick={onClose} className="rounded-full px-2 py-1 text-sm text-ink-soft hover:bg-ink-wash" aria-label="Close the brief">← Back to Directions</button>
        <span className="flex-1" />
        <button onClick={copy} className="rounded-full border border-ink-line px-3 py-1.5 text-xs font-medium hover:border-machinery/40 hover:text-machinery">{copied === "done" ? "Copied" : copied === "failed" ? "Copy failed" : "Copy text"}</button>
        <button onClick={() => window.print()} className="rounded-full bg-machinery px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90">Print</button>
      </div>
      <p className="sr-only" aria-live="polite">{copied === "done" ? "Brief copied as text." : copied === "failed" ? "Copy failed. Select the text and copy it manually." : ""}</p>
    </div>
    <article className="mx-auto max-w-3xl px-4 pb-16 pt-6 text-sm leading-relaxed [overflow-wrap:anywhere] print:max-w-none print:px-0 print:pt-0">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-machinery">{brief.title}</p>
      <h1 id="family-brief-title" ref={heading} tabIndex={-1} className="mt-2 text-2xl font-semibold leading-tight tracking-tight outline-none">{brief.condition}</h1>
      <p className="mt-1 text-xs text-ink-faint">{brief.prepared}</p>
      <p className="mt-4 rounded-xl border border-caution/30 bg-caution-soft/50 p-3 text-xs text-ink">{brief.notice}</p>
      {brief.sections.map((s) => <section key={s.id} data-brief-section={s.id} className="mt-8 break-inside-avoid-page">
        <h2 className="border-b border-ink-line pb-1 text-base font-semibold">{s.title}</h2>
        {s.intro && <p className="mt-2 text-xs text-ink-soft">{s.intro}</p>}
        {s.blocks.map((b, k) => <div key={k} className="mt-3">
          {b.heading && <h3 className="mb-2 mt-4 text-[11px] font-semibold uppercase tracking-wide text-ink-faint">{b.heading}</h3>}
          {b.items?.map((it, j) => <div key={j} data-brief-item className="mb-3 break-inside-avoid rounded-xl border border-ink-line p-3 print:rounded-none print:border-x-0 print:border-t-0 print:px-0">
            <h4 className="font-semibold leading-snug">{it.title}</h4>
            {it.subtitle && <p className="text-xs text-ink-faint">{it.subtitle}</p>}
            {it.url && <a href={it.url} target="_blank" rel="noreferrer" className="mt-1 block font-mono text-[11px] text-machinery underline">{it.url}</a>}
            {it.facts.map((f, i) => <p key={i} className="mt-1.5 whitespace-pre-wrap text-xs text-ink-soft">{f}</p>)}
            {it.cautions.map((x, i) => <p key={i} className="mt-1.5 text-xs text-caution">{x}</p>)}
          </div>)}
          {b.bullets && <ul className="list-disc space-y-1.5 pl-5 text-xs text-ink-soft">{b.bullets.map((x, i) => <li key={i}>{x}</li>)}</ul>}
        </div>)}
      </section>)}
      <footer className="mt-10 border-t border-ink-line pt-3 text-[11px] text-ink-faint">{brief.footer.map((f, i) => <p key={i} className="mt-1">{f}</p>)}</footer>
    </article>
  </div>, document.body);
}
