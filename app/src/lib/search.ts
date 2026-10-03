// Client-side search over every name, synonym and symbol in the atlas (data/search.json).

export type SearchKind = "c" | "g" | "s" | "grp" | "m";
/** [matched text, kind, id, label (if different from text), extra info, prominence 0..1] */
type Entry = [string, SearchKind, string, string, string, number];

export interface SearchResult {
  kind: SearchKind;
  id: string;
  label: string;
  matched: string | null; // the synonym that matched, when it differs from the label
  extra: string;
  score: number;
}

const KIND_WEIGHT: Record<SearchKind, number> = { g: 1.15, c: 1.0, s: 0.85, grp: 0.62, m: 0.6 };

let index: Promise<{ entries: Entry[]; norm: string[] }> | null = null;

export const normalize = (s: string) =>
  s
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();

export function loadIndex() {
  if (!index) {
    index = fetch("/data/search.json")
      .then((r) => r.json() as Promise<Entry[]>)
      .then((entries) => ({ entries, norm: entries.map((e) => normalize(e[0])) }));
  }
  return index;
}

export async function search(query: string, limit = 12): Promise<SearchResult[]> {
  const q = normalize(query);
  if (!q) return [];
  const tokens = q.split(" ");
  const { entries, norm } = await loadIndex();
  const best = new Map<string, SearchResult>();
  const hits = new Map<string, number>(); // how many of an entity's names match: the query is central to it
  for (let i = 0; i < entries.length; i++) {
    const text = norm[i];
    let score: number;
    if (text === q) score = 100;
    else if (text.startsWith(q + " ") || text === q) score = 82 - Math.min(20, (text.length - q.length) / 3);
    else if (text.startsWith(q)) score = 75 - Math.min(20, (text.length - q.length) / 3);
    else if ((" " + text + " ").includes(" " + q + " ")) score = 70 - Math.min(20, (text.length - q.length) / 4);
    else {
      const words = text.split(" ");
      if (!tokens.every((t) => words.some((w) => w.startsWith(t)))) continue;
      score = 55 - Math.min(25, (text.length - q.length) / 4);
    }
    const [raw, kind, id, label, extra, prominence] = entries[i];
    score *= KIND_WEIGHT[kind];
    if (kind === "c") score += 20 * (prominence || 0);
    if (kind === "g" && text === q) score += 30; // a typed gene symbol should win
    const key = `${kind}:${id}`;
    hits.set(key, (hits.get(key) ?? 0) + 1);
    const prev = best.get(key);
    if (!prev || prev.score < score) {
      best.set(key, { kind, id, label: label || raw, matched: label ? raw : null, extra, score });
    }
  }
  for (const [key, r] of best) r.score += 3 * Math.min(3, (hits.get(key) ?? 1) - 1);
  return [...best.values()].sort((a, b) => b.score - a.score).slice(0, limit);
}
