// Everyday-language explanations of connections, for people with no science background.
// Each sentence is built only from the recorded evidence behind the connection.
import type { ConditionBundle, Neighbor } from "./types";

function symptomPlain(id: string, dict: ConditionBundle["dict"]["symptoms"]): string {
  const [name, plain] = dict[id] ?? [id, null];
  const text = plain && plain.length <= name.length + 6 ? plain : name;
  return text.charAt(0).toLowerCase() + text.slice(1);
}

/** The single clearest reason two conditions are connected, in one sentence. */
export function plainReason(c: ConditionBundle, n: Neighbor): string {
  if (n.same_gene) return `Both are caused by changes in the same gene, ${c.gene.symbol}.`;
  const kinds = new Set(n.mechanisms.map((m) => m.k));
  const rare = n.symptoms.filter((s) => (c.dict.symptoms[s]?.[2] ?? 9999) <= 400);
  let machinery = "";
  if (kinds.has("interaction") && kinds.has("complex")) machinery = "Their proteins work together as parts of the same tiny machine inside cells.";
  else if (kinds.has("interaction")) machinery = "Their proteins work together directly.";
  else if (kinds.has("complex")) machinery = "Their proteins are parts of the same tiny machine inside cells.";
  else if (kinds.has("partner")) {
    const p = n.mechanisms.find((m) => m.k === "partner");
    machinery = `Their proteins both work with the same partner protein${p && "symbol" in p ? ` (${p.symbol})` : ""}.`;
  } else if (kinds.has("pathway") || kinds.has("go")) machinery = "Their genes do related jobs in the body.";
  const symptoms = rare.length && n.sym >= 0.08 ? `People with either condition can have ${symptomPlain(rare[0], c.dict.symptoms)}${rare.length > 1 ? " and other uncommon symptoms" : ""}.` : "";
  if (machinery && symptoms && n.mech >= 0.15) return `${machinery} ${symptoms}`;
  if (machinery && n.mech >= 0.15) return machinery;
  if (symptoms) return symptoms;
  return "They share some symptoms and biology.";
}

/** How close a connection is, in words. */
export function closeness(n: Neighbor): "Very close" | "Close" | "Related" {
  if (n.same_gene || n.score >= 0.45) return "Very close";
  if (n.score >= 0.3) return "Close";
  return "Related";
}

export function plainRarity(c: ConditionBundle): string | null {
  const p = c.prevalence;
  if (p?.cases) return `About ${p.cases.toLocaleString("en-US")} people reported`;
  if (p?.class) {
    const m = p.class.match(/^([<>]?)\s*([\d-]+)\s*\/\s*([\d\s]+)$/);
    if (m) {
      const per = Number(m[3].replace(/\s/g, "")).toLocaleString("en-US");
      return `${m[1] === "<" ? "Fewer than " : ""}${m[2].replace("-", "–")} in ${per} people`;
    }
  }
  return null;
}
