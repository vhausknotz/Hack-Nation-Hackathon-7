import type { Effect, Prevalence } from "./types";

export const effectLabel: Record<Effect, string> = {
  loss_of_function: "Loss of function",
  gain_of_function: "Gain of function",
  dominant_negative: "Dominant negative",
  non_loss_of_function: "Not loss of function",
  unknown: "Not yet curated",
};

export const effectExplainer: Record<Effect, string> = {
  loss_of_function: "The gene change reduces or removes the protein's normal work. Approaches that restore or boost the protein may apply.",
  gain_of_function: "The gene change makes the protein overactive or toxic. Approaches that silence or block it may apply.",
  dominant_negative: "The altered protein interferes with the normal copy. Simply adding more protein may not be enough.",
  non_loss_of_function: "Curators judge the mechanism is not simple loss of function, but the exact effect is undetermined.",
  unknown: "How the gene change causes disease has not been curated. This matters for which therapy approaches could transfer.",
};

const CATEGORY_LABELS: Record<string, string> = {
  "nervous system disorder": "Brain & nerves",
  "inborn errors of metabolism": "Metabolism",
  "cardiovascular disorder": "Heart & vessels",
  "immune system disorder": "Immune system",
  "hematologic disorder": "Blood",
  "musculoskeletal system disorder": "Muscles & bones",
  "integumentary system disorder": "Skin",
  "disorder of visual system": "Eyes",
  "auditory system disorder": "Hearing",
  "kidney disorder": "Kidneys",
  "urinary system disorder": "Urinary system",
  "endocrine system disorder": "Hormones",
  "respiratory system disorder": "Lungs",
  "digestive system disorder": "Digestion",
  "reproductive system disorder": "Reproductive system",
  "cancer or benign tumor": "Tumors",
  other: "Other",
};

export const categoryLabel = (c: string) => CATEGORY_LABELS[c] ?? c;

/** "1-9 / 1 000 000" -> "1–9 in 1,000,000 people" */
function prevalenceClass(klass: string): string {
  const m = klass.match(/^([<>]?)\s*([\d-]+)\s*\/\s*([\d\s]+)$/);
  if (!m) return klass;
  const [, op, range, denom] = m;
  const per = Number(denom.replace(/\s/g, "")).toLocaleString("en-US");
  const prefix = op === "<" ? "Fewer than " : op === ">" ? "More than " : "";
  return `${prefix}${range.replace("-", "–")} in ${per} people`;
}

export function rarity(p: Prevalence | null): { headline: string; detail: string } | null {
  if (!p) return null;
  if (p.cases) {
    return {
      headline: `${p.cases.toLocaleString("en-US")} cases reported`,
      detail: p.class ? `Estimated ${prevalenceClass(p.class).toLowerCase()} (${p.class_geography ?? "Orphanet"})` : "Orphanet case count",
    };
  }
  if (p.class) return { headline: prevalenceClass(p.class), detail: `${p.class_kind ?? "Prevalence"}, ${p.class_geography ?? ""}`.trim() };
  return null;
}

export const frequencyLabel: Record<string, string> = {
  "HP:0040280": "Always",
  "HP:0040281": "Very frequent",
  "HP:0040282": "Frequent",
  "HP:0040283": "Occasional",
  "HP:0040284": "Very rare",
  "HP:0040285": "Excluded",
};

export function frequency(f: string): string | null {
  if (!f) return null;
  if (frequencyLabel[f]) return frequencyLabel[f];
  const frac = f.match(/^(\d+)\/(\d+)$/);
  if (frac) return `${frac[1]} of ${frac[2]} patients`;
  return f;
}

/** How rare a symptom is across all conditions, as a short phrase. */
export function symptomRarity(count: number): string {
  if (count <= 50) return `rare: ${count} conditions`;
  if (count <= 400) return `uncommon: ${count} conditions`;
  return `common: ${count.toLocaleString("en-US")} conditions`;
}

export const strengthWord = (x: number) => (x >= 0.6 ? "strong" : x >= 0.35 ? "moderate" : x >= 0.15 ? "some" : "weak");

export function capitalize(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}
