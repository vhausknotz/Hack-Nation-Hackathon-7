// Loads entity bundles from the sharded static data (see pipeline/export_app.py).
// Shards republished by the live engine since this release are read from the live overlay instead.
import type { ConditionBundle, GeneBundle, GroupBundle, MechanismBundle, Meta, SymptomBundle } from "./types";
import { dataUrl } from "./dataVersion";
import { getLiveState, LIVE_API, onLive } from "./live";

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
    const request = fetch(url.startsWith("http") ? url : dataUrl(url)).then((r) => {
      if (!r.ok) throw new Error(`${r.status} ${url}`);
      return r.json();
    });
    request.catch(() => cache.delete(url));
    cache.set(url, request);
  }
  return cache.get(url) as Promise<T>;
}

export const getMeta = () => fetchJson<Meta>(`${BASE}/meta.json`);

let baseId: string | null | undefined;
getMeta().then((m) => (baseId = m.data_id ?? null), () => (baseId = null));

/** The overlay version holding a newer copy of this shard, if the live engine republished it. */
function overlayVersion(path: string): string | null {
  const overlay = getLiveState().overlay;
  if (!overlay || !baseId || overlay.base !== baseId) return null;
  return overlay.files[path] ?? null;
}

export function shardPath(kind: Kind, key: string) {
  return `${kind}/${fnv1a(key) % SHARDS[kind]}.json`;
}

async function entity<T>(kind: Kind, key: string): Promise<T | null> {
  if (baseId === undefined) await getMeta().catch(() => null);
  const path = shardPath(kind, key);
  const version = overlayVersion(path);
  const shard = version
    ? await fetchJson<Record<string, T>>(`${LIVE_API}/live/data/${version}/${path}`).catch(() => fetchJson<Record<string, T>>(`${BASE}/${path}`))
    : await fetchJson<Record<string, T>>(`${BASE}/${path}`);
  return shard[key] ?? null;
}

/** Version of the data behind one condition: changes when the live engine republishes its shard. */
export function conditionRevision(id: string): string {
  return overlayVersion(shardPath("c", id)) ?? "base";
}

export function onDataChange(listener: () => void) {
  let last = getLiveState().overlay?.version;
  return onLive(() => {
    const now = getLiveState().overlay?.version;
    if (now !== last) {
      last = now;
      listener();
    }
  });
}

export const getCondition = (id: string) => entity<ConditionBundle>("c", id);
export const getGene = (symbol: string) => entity<GeneBundle>("g", symbol);
export const getSymptom = (id: string) => entity<SymptomBundle>("s", id);
export const getGroup = (id: string) => entity<GroupBundle>("grp", id);
export const getMechanism = (id: string) => entity<MechanismBundle>("m", id);
