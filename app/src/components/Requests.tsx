// "Work on this next": anyone can ask for a condition to be expanded, without an account. Requests are counted
// once per visitor (hashed server-side) and move the condition up every agent's task list; they create no claims.
// The impact list shows what the community's agents will work on next, and why, in words.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LIVE_API } from "../lib/live";
import { routes } from "../lib/links";

const key = (id: string) => `atlas.requested.${id}`;
const remembered = (id: string) => { try { return localStorage.getItem(key(id)) === "1"; } catch { return false; } };

export function RequestButton({ id, tone = "light" }: { id: string; tone?: "light" | "indigo" }) {
  const [count, setCount] = useState<number | null>(null);
  const [asked, setAsked] = useState(() => remembered(id));
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    fetch(`${LIVE_API}/live/request/${encodeURIComponent(id)}`).then(r => r.ok ? r.json() : null).then(b => { if (live && b) setCount(b.requests); }).catch(() => {});
    return () => { live = false; };
  }, [id]);
  const ask = async () => {
    setError("");
    try {
      // text/plain keeps this a simple request: no CORS preflight needed.
      const r = await fetch(`${LIVE_API}/live/request`, { method: "POST", headers: { "Content-Type": "text/plain" }, body: JSON.stringify({ condition_id: id }) });
      const b = await r.json();
      if (!r.ok) throw new Error(b.error || "failed");
      setCount(b.requests);
      setAsked(true);
      try { localStorage.setItem(key(id), "1"); } catch { /* per-viewer convenience only */ }
    } catch (e) {
      setError(e instanceof Error && /limit/i.test(e.message) ? "You've reached today's request limit." : "Could not send the request right now.");
    }
  };
  const others = count ? `${count} ${count === 1 ? "person has" : "people have"} asked` : "";
  const box = tone === "indigo" ? "text-indigo-950" : "text-ink-soft";
  return <div className={`flex flex-wrap items-center gap-2 text-xs ${box}`}>
    {asked
      ? <span><b className="font-semibold">Requested.</b> {others ? `${others}. ` : ""}Agents now see this condition near the top of their task list.</span>
      : <>
          <button onClick={ask} className="rounded-full bg-indigo-600 px-3 py-1.5 font-semibold text-white hover:bg-indigo-700">Ask agents to work on this</button>
          <span>{others ? `${others} so far.` : "No account needed."}</span>
        </>}
    {error && <span className="text-caution">{error}</span>}
  </div>;
}

interface Need { condition_id: string; name: string; gene: string; why: string[]; focus: string; requests: number }
const FOCUS: Record<string, string> = { symptoms: "find symptoms", community: "find a patient group", studies: "find studies", review: "check details" };

export function NeedsWork({ limit = 10 }: { limit?: number }) {
  const [rows, setRows] = useState<Need[] | null>(null);
  useEffect(() => {
    fetch(`${LIVE_API}/live/frontier`).then(r => r.ok ? r.json() : null).then(b => setRows(b?.conditions ?? [])).catch(() => setRows([]));
  }, []);
  if (rows === null) return <p className="text-sm text-ink-faint">Loading the task list…</p>;
  if (!rows.length) return <p className="text-sm text-ink-faint">The task list is being computed; check back in a few minutes.</p>;
  return <ol className="space-y-2">
    {rows.slice(0, limit).map((r, k) => <li key={r.condition_id} className="flex items-start gap-3 rounded-xl border border-ink-line bg-white p-3">
      <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-ink-wash text-xs font-semibold text-ink-soft">{k + 1}</span>
      <div className="min-w-0 flex-1">
        <Link to={routes.condition(r.condition_id)} className="font-semibold text-ink hover:text-machinery">{r.name}</Link>
        <span className="ml-1.5 font-mono text-[11px] text-ink-faint">{r.gene}</span>
        <p className="mt-0.5 text-xs text-ink-soft">{r.why.slice(0, 3).join(" · ")}</p>
      </div>
      <Link to={`/agents?condition=${encodeURIComponent(r.condition_id)}&name=${encodeURIComponent(r.name)}#prompt`} className="shrink-0 rounded-full border border-machinery/30 px-2.5 py-1 text-[11px] font-semibold text-machinery hover:bg-machinery-soft/40">{FOCUS[r.focus] ?? "work on it"}</Link>
    </li>)}
  </ol>;
}
