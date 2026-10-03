// Loads entity bundles from the sharded static data (see pipeline/export_app.py).
import type { ConditionBundle, GeneBundle, GroupBundle, MechanismBundle, Meta, SymptomBundle } from "./types";

const BASE = "/data";
const SHARDS: Record<Kind, number> = { c: 256, g: 128, s: 128, grp: 64, m: 128 };
type Kind = "c" | "g" | "s" | "grp" | "m";

/** FNV-1a over UTF-8 bytes; must match fnv1a() in pipeline/export_app.py. */
function fnv1a(text: string): number {
  let h = 0x811c9dc5;
  for (const byte of new TextEncoder().encode(text)) {
    h ^= byte;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

const cache = new Map<string, Promise<unknown>>();

function fetchJson<T>(url: string): Promise<T> {
  if (!cache.has(url)) {
    cache.set(
      url,
      fetch(url).then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${url}`);
        return r.json();
      }),
    );
  }
  return cache.get(url) as Promise<T>;
}

async function entity<T>(kind: Kind, key: string): Promise<T | null> {
  const shard = await fetchJson<Record<string, T>>(`${BASE}/${kind}/${fnv1a(key) % SHARDS[kind]}.json`);
  return shard[key] ?? null;
}

export const getCondition = (id: string) => entity<ConditionBundle>("c", id);
export const getGene = (symbol: string) => entity<GeneBundle>("g", symbol);
export const getSymptom = (id: string) => entity<SymptomBundle>("s", id);
export const getGroup = (id: string) => entity<GroupBundle>("grp", id);
export const getMechanism = (id: string) => entity<MechanismBundle>("m", id);
export const getMeta = () => fetchJson<Meta>(`${BASE}/meta.json`);
