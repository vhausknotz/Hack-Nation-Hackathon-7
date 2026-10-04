// The live layer: what agents are doing right now, and newly published data on top of the static release.
// Activity and presence are operational status, never evidence. Only reviewed claims change the data overlay.
import { useSyncExternalStore } from "react";

export const LIVE_API = "https://rare-atlas-mcp-1180fc.azurewebsites.net";
export const MCP_URL = `${LIVE_API}/mcp`;

export interface LiveEvent {
  seq: number;
  at: number;
  agent: string;
  family: string | null;
  stage: string;
  condition_id: string | null;
  detail?: Record<string, any> | null;
}

export interface Presence {
  name: string;
  family: string | null;
  model: string | null;
  doing: string;
  condition_id: string | null;
  at: number;
}

export interface OverlayChange {
  condition_id: string;
  name: string;
  version: string;
  at: number;
  new_symptoms: number;
  symptoms: number;
  new_connections: { id: string; name: string; score: number }[];
  connections: number;
}

export interface Overlay {
  base: string;
  version: string;
  published_at: number;
  files: Record<string, string>;
  changes: OverlayChange[];
}

export interface LiveState {
  connected: boolean;
  events: LiveEvent[];
  presence: Presence[];
  overlay: Overlay | null;
  engine: { online: boolean; at: number | null; host: string | null } | null;
  serverOffset: number; // server clock minus local clock, seconds
}

let state: LiveState = { connected: false, events: [], presence: [], overlay: null, engine: null, serverOffset: 0 };
const listeners = new Set<() => void>();
let cursor = 0;
let timer: number | undefined;
let failures = 0;
let started = false;

function emit(next: LiveState) {
  state = next;
  listeners.forEach((l) => l());
}

async function poll() {
  timer = undefined;
  if (typeof document !== "undefined" && document.visibilityState === "hidden") {
    schedule(15000);
    return;
  }
  try {
    const r = await fetch(`${LIVE_API}/live/feed?after=${cursor}`, { cache: "no-store" });
    if (!r.ok) throw new Error(String(r.status));
    const body = (await r.json()) as { now: number; events: LiveEvent[]; presence: Presence[]; overlay: Overlay | null; engine?: LiveState["engine"] };
    const fresh = body.events.filter((e) => e.seq > cursor);
    if (fresh.length) cursor = fresh[fresh.length - 1].seq;
    failures = 0;
    emit({
      connected: true,
      events: [...state.events, ...fresh].slice(-120),
      presence: body.presence,
      overlay: body.overlay,
      engine: body.engine ?? null,
      serverOffset: body.now - Date.now() / 1000,
    });
    schedule(4000);
  } catch {
    failures += 1;
    if (state.connected) emit({ ...state, connected: false });
    schedule(Math.min(60000, 5000 * 2 ** Math.min(failures, 4)));
  }
}

function schedule(ms: number) {
  if (timer === undefined) timer = window.setTimeout(poll, ms);
}

export function startLive() {
  if (started || typeof window === "undefined") return;
  started = true;
  poll();
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && timer !== undefined) {
      window.clearTimeout(timer);
      timer = undefined;
      poll();
    }
  });
}

function subscribe(listener: () => void) {
  startLive();
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function useLive(): LiveState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

export function getLiveState() {
  return state;
}

export function onLive(listener: () => void) {
  return subscribe(listener);
}

/** Seconds since a server timestamp, corrected for clock skew. */
export function ageSeconds(at: number, s: LiveState = state) {
  return Math.max(0, Date.now() / 1000 + s.serverOffset - at);
}

export function familyColor(family: string | null | undefined): string {
  const f = (family ?? "").toLowerCase();
  if (f.includes("gemini") || f.includes("google")) return "#60a5fa";
  if (f.includes("claude") || f.includes("anthropic")) return "#f59e8b";
  if (f.includes("openai") || f.includes("gpt")) return "#5eead4";
  return "#c4b5fd";
}

export function familyName(family: string | null | undefined): string {
  const f = (family ?? "").toLowerCase();
  if (f.includes("gemini") || f.includes("google")) return "Gemini";
  if (f.includes("claude") || f.includes("anthropic")) return "Claude";
  if (f.includes("openai") || f.includes("gpt")) return "GPT";
  return family || "agent";
}

export type Role = "scout" | "writer" | "reviewer" | "atlas";

export function roleOf(doing: string): Role {
  if (/review/.test(doing)) return "reviewer";
  if (/submit|challeng/.test(doing)) return "writer";
  return "scout";
}

const PREDICATE: Record<string, string> = {
  has_symptom: "a symptom",
  has_asset: "a study or registry",
  represented_by: "a patient organization",
  studied_by: "a researcher",
  has_name: "a name",
  has_variant_effect: "a gene effect",
  has_prevalence: "how common it is",
};

/** One plain sentence per workflow event, for the activity ticker. */
export function describe(e: LiveEvent, conditionName?: string): string {
  const d = e.detail ?? {};
  const what = d.label ? `“${d.label}”` : PREDICATE[d.predicate] ?? "a finding";
  const where = conditionName ? ` for ${conditionName}` : "";
  switch (e.stage) {
    case "task_claimed":
      return `${e.agent} started working${where}`;
    case "source_fetch_started":
    case "source_fetched":
      return `${e.agent} archived a source${where}`;
    case "queued":
      return d.kind === "review" ? `${e.agent} submitted a review` : `${e.agent} submitted ${what}${where}`;
    case "kernel_accepted":
      return `Quote check passed: ${what}${where}`;
    case "kernel_rejected":
      return `Quote check rejected ${what}${where}${d.failed_checks?.[0] ? ` (${d.failed_checks[0].check})` : ""}`;
    case "rejected":
      return `Submission rejected${where}`;
    case "review_recorded": {
      const v = d.verdict === "supports" ? "supported" : d.verdict === "supports_with_qualification" ? "supported with a caveat" : d.verdict === "does_not_support" ? "not supported" : d.verdict ? "out of scope" : "recorded";
      return d.reviewer === "peer" ? `${e.agent} reviewed a finding: ${v}${where}` : `Review: ${what} ${v}${where}`;
    }
    case "reviewer_qualified":
      return `${e.agent} qualified as a reviewer (${d.score ?? "calibration passed"})`;
    case "challenge_recorded":
      return `A claim was challenged${where}`;
    case "rebuilding":
      return "Recomputing connections from reviewed evidence…";
    case "published": {
      const n = (d.new_connections ?? []).length;
      const s = d.new_symptoms ?? 0;
      const parts = [s > 0 ? `${s} new symptom${s === 1 ? "" : "s"}` : "", n > 0 ? `${n} new connection${n === 1 ? "" : "s"}` : ""].filter(Boolean);
      return `Published${where}: ${parts.join(", ") || "updated evidence"}`;
    }
    case "requested":
      return `Someone asked agents to work on ${conditionName ?? "a condition"}${d.count > 1 ? ` (${d.count} requests)` : ""}`;
    case "budget_reached":
      return "Today's review budget is used up; findings wait for peer reviewers";
    default:
      return `${e.agent}: ${e.stage.replace(/_/g, " ")}${where}`;
  }
}
