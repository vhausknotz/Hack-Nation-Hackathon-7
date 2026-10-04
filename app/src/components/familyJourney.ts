// Deterministic wording for the family journey: listing labels, study status groups, gaps and the
// questions a family can take to a group, study team or care team. Shared by DirectionsPanel and the
// research-question brief so the panel, the printed brief and the copied text never disagree.
// Nothing here recommends a group or study: every listing is phrased as something to verify.
import type { ActionReview, Community, ConditionBundle, Neighbor, ResearchAsset } from "../lib/types";

export const ASSET_TYPE: Record<string, string> = {
  registry: "Patient registry",
  natural_history_study: "How the condition changes over time",
  biomarker: "Finding ways to track the condition",
  outcome_measure: "Measuring change",
  biorepository: "A bank of research samples",
  trial: "Clinical trial",
  therapy_program: "Treatment research",
  model: "Laboratory model",
};

export const STATUS_LABEL: Record<string, string> = {
  RECRUITING: "Recruiting",
  NOT_YET_RECRUITING: "Not yet recruiting",
  ENROLLING_BY_INVITATION: "Enrolling by invitation",
  ACTIVE_NOT_RECRUITING: "Active, not recruiting",
  COMPLETED: "Completed",
  TERMINATED: "Stopped early",
  WITHDRAWN: "Withdrawn",
  SUSPENDED: "Paused",
};

export const isSolid = (review: ActionReview) => review.status === "independently_reviewed" || review.status === "human_reviewed";
export const reviewLabel = (review: ActionReview) =>
  review.status === "human_reviewed" ? "Reviewed by a person" : review.status === "independently_reviewed" ? "Checked by independent reviewers" : "Checked against its source by one AI reviewer";

export function statusLabel(a: ResearchAsset) {
  return STATUS_LABEL[a.status] ?? "Status not recorded";
}

// ---- organizations ---------------------------------------------------------------------------------------------

export function orgKindLabel(o: Community) {
  return o.kind === "patient_organization" ? "Patient group" : o.kind === "research_program" ? "Research program" : "Organization";
}

/** Whom the listing serves, as the reviewer classified it from the organization's own page. */
export function orgScope(o: Community, c: ConditionBundle) {
  if (o.scope === "this_condition") return "Focuses on this diagnosis";
  if (o.scope === "this_gene") return `Serves people with ${c.gene.symbol} changes`;
  return "A broader community";
}

/** Caveats that must travel with the listing wherever it appears. */
export function orgNotes(o: Community, c: ConditionBundle): string[] {
  const notes: string[] = [];
  if (o.page_read === "archived_snapshot") notes.push(`Only an archived copy of its page from ${o.page_date} was read; check their site for current activity.`);
  if (o.via) notes.push(`Recorded for another ${c.gene.symbol}-linked diagnosis; whether it serves ${c.name} specifically has not been checked.`);
  else if (o.scope === "broader_group") notes.push(`Serves a wider group; whether it includes ${c.name} specifically has not been checked.`);
  return notes;
}

// ---- studies ---------------------------------------------------------------------------------------------------

export type StudyGroupKey = "recruiting" | "soon" | "unknown" | "closed";
export const STUDY_GROUPS: { key: StudyGroupKey; heading: string }[] = [
  { key: "recruiting", heading: "Registry reports recruiting" },
  { key: "soon", heading: "Registry reports not yet recruiting or by invitation" },
  { key: "unknown", heading: "Recruitment status not recorded" },
  { key: "closed", heading: "Registry reports not enrolling" },
];

export function studyGroup(a: ResearchAsset): StudyGroupKey {
  if (a.status === "RECRUITING") return "recruiting";
  if (a.status === "NOT_YET_RECRUITING" || a.status === "ENROLLING_BY_INVITATION") return "soon";
  if (["ACTIVE_NOT_RECRUITING", "COMPLETED", "TERMINATED", "WITHDRAWN", "SUSPENDED"].includes(a.status)) return "closed";
  return "unknown";
}

export function groupStudies(assets: ResearchAsset[]) {
  return STUDY_GROUPS.map((g) => ({ ...g, assets: assets.filter((a) => studyGroup(a) === g.key) })).filter((g) => g.assets.length);
}

/** "Includes your condition" | "Only some patients" | "Ask an expert", from the reviewer's verdict and the recorded restriction. */
export function studyFit(a: ResearchAsset) {
  if (a.restriction) return { label: "Only some patients", limited: true };
  if (a.review.verdict === "supports_with_qualification") return { label: "Ask an expert", limited: true };
  return { label: "Record includes your condition", limited: false };
}

export const eligibilityIncomplete = (a: ResearchAsset) => /eligibility excerpt incomplete/i.test(a.restriction ?? "");
export const testsTreatment = (a: ResearchAsset) => a.type === "trial" || a.type === "therapy_program";

export function studyNotes(a: ResearchAsset): string[] {
  const notes: string[] = [];
  if (eligibilityIncomplete(a)) notes.push("Only part of the eligibility criteria was read. Check the full record.");
  if (testsTreatment(a)) notes.push("This study tests a treatment. Being listed here is not evidence that the treatment works or is suitable.");
  notes.push(`Status as recorded on ${a.source_date || "the source date"}. Recruitment can change, and recruiting does not mean you are eligible.`);
  return notes;
}

// ---- questions -------------------------------------------------------------------------------------------------

export interface Question {
  to: string;
  about?: string;
  url?: string;
  text: string;
  review?: string;
  note?: string;
}

const isRegistry = (a: ResearchAsset) => a.type === "registry" || a.type === "biorepository";
const OPEN: StudyGroupKey[] = ["recruiting", "soon", "unknown"];

/**
 * Questions to verify what was found. Every listed organization and every study whose record does not
 * report it closed gets one. The care-team question always comes first and needs no listing.
 */
export function questions(c: ConditionBundle): Question[] {
  // Contested listings are shown with both sides, but never turned into a suggested question.
  const orgs = (c.communities ?? []).filter((o) => o.dispute?.status !== "contested");
  const people = orgs.filter((o) => o.kind === "patient_organization");
  const programs = orgs.filter((o) => o.kind === "research_program");
  const assets = (c.assets ?? []).filter((a) => OPEN.includes(studyGroup(a)) && a.dispute?.status !== "contested");
  const out: Question[] = [{
    to: "your care team",
    text: `My diagnosis is ${c.name}, linked to ${c.gene.symbol}. Which patient group or research registry should I ask about?`,
  }];
  for (const o of people)
    out.push({
      to: o.name, about: orgKindLabel(o), url: o.homepage, review: reviewLabel(o.review), note: orgNotes(o, c)[0],
      text: o.scope === "this_condition"
        ? `Do you currently support families with ${c.name}, and how do new families get in touch?`
        : `Do you support families with ${c.name} specifically, and how do new families get in touch?`,
    });
  for (const o of programs)
    out.push({ to: o.name, about: orgKindLabel(o), url: o.homepage, review: reviewLabel(o.review), note: orgNotes(o, c)[0], text: `Does your program include ${c.name}, and is enrollment currently open?` });
  for (const a of assets) {
    const kind = isRegistry(a) ? "registry" : "study";
    out.push({
      to: "the study team or your care team", about: a.title, url: a.url, review: reviewLabel(a.review),
      note: a.restriction ? `The record lists a restriction: ${a.restriction}` : undefined,
      text: `Does this ${kind} include ${c.name}, and is enrollment currently open?${a.restriction ? " Does the restriction in its record apply to us?" : ""}`,
    });
  }
  return out;
}

/** Open research questions the family could raise with a group or researcher. Only where the atlas found nothing. */
export function researchQuestions(c: ConditionBundle): string[] {
  const out: string[] = [];
  if (!(c.assets ?? []).length) out.push(`Is anyone collecting information on how ${c.name} changes over time, for example in a registry or natural history study?`);
  if (c.variant_effect.value === "unknown") out.push(`Is it known how ${c.gene.symbol} changes like ours affect the protein?`);
  if (!(c.communities ?? []).some((o) => o.kind === "patient_organization")) out.push(`Do you know other families with ${c.name}, or a group they have formed?`);
  return out;
}

// ---- gaps ------------------------------------------------------------------------------------------------------

export interface Gap { text: string; help?: string }

export function gaps(c: ConditionBundle, neighbors: Neighbor[]): Gap[] {
  const orgs = c.communities ?? [];
  const people = orgs.filter((o) => o.kind === "patient_organization");
  const assets = c.assets ?? [];
  const listings = [...orgs.filter((o) => o.kind !== "information_service" && o.kind !== "company"), ...assets];
  const out: Gap[] = [];
  if (!people.length) out.push({ text: "No patient group for this diagnosis has been found in the atlas yet.", help: "A current public page from a group naming whom it serves would fill this gap." });
  else if (!people.some((o) => o.scope === "this_condition" && !o.via)) out.push({ text: `No group focused on this exact diagnosis has been found in the atlas yet. The groups listed serve people with ${c.gene.symbol} changes or a broader community.` });
  for (const o of people.filter((o) => o.page_read === "archived_snapshot")) out.push({ text: `${o.name}: only an archived copy from ${o.page_date} was read, so current activity is unconfirmed.`, help: "A current page from the group would confirm it." });
  if (!assets.length) out.push({ text: "No studies for this condition have been found in the atlas yet. Our study coverage is incomplete.", help: "A study record naming this condition among those eligible would fill this gap." });
  const partial = assets.filter(eligibilityIncomplete).length;
  if (partial) out.push({ text: `For ${partial} of ${assets.length} studies, only part of the eligibility criteria was read.`, help: "The full study record says who can take part." });
  if (listings.length && !listings.some((l) => isSolid(l.review))) out.push({ text: "Every group and study here was checked against its source by one AI reviewer only. None has had independent or human review yet, so none is presented as a recommendation." });
  if (c.phenotype_count === 0) out.push({ text: "No symptoms are recorded for this condition in the Human Phenotype Ontology, so its connections rest on gene biology alone.", help: "Curated symptom records would allow comparison by symptoms too." });
  if (!neighbors.length) out.push({ text: "There is too little recorded information to compute connections to other conditions." });
  if (c.variant_effect.value === "unknown") out.push({ text: "How these gene changes cause the condition has not been curated.", help: "Expert curation could change which connections are useful." });
  out.push({ text: "A connection on the map does not establish that two conditions can share a treatment or join the same study. That requires further evidence and expert assessment." });
  out.push({ text: "Websites and recruitment status change. Source dates tell you when a record was read, not that it is current today." });
  return out;
}
