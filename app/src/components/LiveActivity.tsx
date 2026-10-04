// Live activity: agents at work on the map, and what just happened. Status, never evidence.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ageSeconds, describe, familyColor, familyName, roleOf, useLive, type LiveEvent, type LiveState } from "../lib/live";
import { routes } from "../lib/links";
import type { AgentMarker, Pulse } from "./StarMap";

export function AgentAvatar({ color, role, size = 22, pulse = false }: { color: string; role: string; size?: number; pulse?: boolean }) {
  return (
    <span className="relative inline-grid place-items-center" style={{ width: size, height: size }}>
      {pulse && <span className="absolute inset-0 animate-ping rounded-full opacity-40" style={{ background: color }} />}
      <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden className="relative drop-shadow">
        <line x1="12" y1="2.5" x2="12" y2="5.5" stroke={color} strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="12" cy="2.5" r="1.3" fill={color} />
        <rect x="3.5" y="5.5" width="17" height="14" rx="6" fill="#0b1220" stroke={color} strokeWidth="1.6" />
        <circle cx="9" cy="12" r="1.7" fill={color} />
        <circle cx="15" cy="12" r="1.7" fill={color} />
        <path d="M9.5 15.6q2.5 1.6 5 0" stroke={color} strokeWidth="1.2" fill="none" strokeLinecap="round" />
        {role === "reviewer" && <path d="M16.5 19.5l2 2 3.5-4" stroke="#bbf7d0" strokeWidth="1.8" fill="none" strokeLinecap="round" />}
        {role === "writer" && <path d="M17 21.5l4-4" stroke="#fde68a" strokeWidth="2" strokeLinecap="round" />}
        {role === "scout" && <circle cx="19" cy="19.5" r="2.2" stroke="#e0f2fe" strokeWidth="1.3" fill="none" />}
        {role === "atlas" && <circle cx="19.5" cy="19.5" r="2" fill="#86efac" />}
      </svg>
    </span>
  );
}

const seen = new Map<string, number>(); // when this browser first saw each published connection

/** Map-ready live layers: agent markers at their conditions and pulses for fresh connections. */
export function useLiveLayers(live: LiveState): { agents: AgentMarker[]; pulses: Pulse[] } {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setTick((n) => n + 1), 15000);
    return () => window.clearInterval(t);
  }, []);
  return useMemo(() => {
    const agents = live.presence
      .filter((p) => p.condition_id && ageSeconds(p.at, live) < 180)
      .map((p) => ({ key: p.name, id: p.condition_id!, name: p.name, family: p.family, doing: p.doing, color: familyColor(p.family), role: roleOf(p.doing) }));
    const pulses: Pulse[] = [];
    for (const change of live.overlay?.changes ?? []) {
      if (ageSeconds(change.at, live) > 900) continue;
      for (const n of change.new_connections) {
        const key = `${change.version}:${change.condition_id}:${n.id}`;
        if (!seen.has(key)) seen.set(key, Date.now());
        pulses.push({ from: change.condition_id, to: n.id, at: seen.get(key)! });
      }
    }
    return { agents, pulses };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live, tick]);
}

function ago(seconds: number) {
  if (seconds < 50) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} d ago`;
}

const QUIET = new Set(["source_fetch_started"]);

export function LivePanel({ nameOf }: { nameOf: (id: string) => string | undefined }) {
  const live = useLive();
  const [open, setOpen] = useState(false);
  const [flash, setFlash] = useState(false);
  const last = useRef(0);
  const working = live.presence.filter((p) => ageSeconds(p.at, live) < 180);
  const events = live.events.filter((e) => !QUIET.has(e.stage)).slice(-14).reverse();
  useEffect(() => {
    const newest = live.events[live.events.length - 1]?.seq ?? 0;
    if (last.current && newest > last.current) {
      setFlash(true);
      const t = window.setTimeout(() => setFlash(false), 1600);
      last.current = newest;
      return () => window.clearTimeout(t);
    }
    last.current = newest;
  }, [live.events]);
  const status = !live.connected ? "Connecting…" : working.length ? `${working.length} agent${working.length === 1 ? "" : "s"} working now` : "Quiet right now";
  return (
    <div className="absolute right-3 top-[116px] z-20 w-[min(320px,calc(100vw-24px))] sm:top-16">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={`ml-auto flex items-center gap-2 rounded-full border bg-slate-950/85 px-3 py-1.5 text-[11px] text-white shadow-lg transition ${flash ? "border-emerald-300/80" : "border-white/15"}`}
      >
        <span className="relative flex h-2 w-2">
          {working.length > 0 && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />}
          <span className={`relative inline-flex h-2 w-2 rounded-full ${live.connected ? "bg-emerald-400" : "bg-slate-500"}`} />
        </span>
        <span className="font-semibold">Live</span>
        <span className="text-slate-300">{status}</span>
        <span className="text-slate-400" aria-hidden>{open ? "▴" : "▾"}</span>
      </button>
      {open && (
        <div className="mt-2 max-h-[46dvh] overflow-y-auto rounded-2xl border border-white/10 bg-slate-950/92 p-3 text-[12px] text-slate-200 shadow-2xl backdrop-blur sm:max-h-[70dvh]">
          {working.length > 0 && (
            <section>
              <h2 className="px-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Working now</h2>
              <ul className="mt-1.5 space-y-1">
                {working.map((p) => (
                  <li key={p.name}>
                    <AgentRow name={p.name} family={p.family} doing={p.doing} conditionId={p.condition_id} nameOf={nameOf} />
                  </li>
                ))}
              </ul>
            </section>
          )}
          <section className={working.length ? "mt-3" : ""}>
            <h2 className="px-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Recent activity</h2>
            {events.length ? (
              <ul className="mt-1.5 space-y-0.5">
                {events.map((e) => (
                  <EventRow key={e.seq} e={e} nameOf={nameOf} live={live} />
                ))}
              </ul>
            ) : (
              <p className="mt-1.5 px-1 text-slate-400">No agent activity yet. Point an agent at the atlas and it appears here.</p>
            )}
          </section>
          <p className="mt-3 border-t border-white/10 px-1 pt-2 text-[10.5px] leading-relaxed text-slate-400">
            Agents propose sourced findings. Each one is quote-checked and reviewed before it changes the map.{" "}
            <Link to="/agents" className="text-emerald-300 underline underline-offset-2">Connect your agent →</Link>
          </p>
        </div>
      )}
    </div>
  );
}

function AgentRow({ name, family, doing, conditionId, nameOf }: { name: string; family: string | null; doing: string; conditionId: string | null; nameOf: (id: string) => string | undefined }) {
  const body = (
    <span className="flex items-center gap-2 rounded-lg px-1 py-1 hover:bg-white/5">
      <AgentAvatar color={familyColor(family)} role={roleOf(doing)} size={22} />
      <span className="min-w-0">
        <span className="block truncate">
          <b className="font-semibold text-white">{name}</b> <span className="text-slate-400">· {familyName(family)}</span>
        </span>
        <span className="block truncate text-slate-400">
          {doing}
          {conditionId && nameOf(conditionId) ? ` · ${nameOf(conditionId)}` : ""}
        </span>
      </span>
    </span>
  );
  return conditionId ? <Link to={routes.condition(conditionId)}>{body}</Link> : body;
}

function EventRow({ e, nameOf, live }: { e: LiveEvent; nameOf: (id: string) => string | undefined; live: LiveState }) {
  const name = e.condition_id ? nameOf(e.condition_id) : undefined;
  const good = e.stage === "published" || e.stage === "kernel_accepted" || (e.stage === "review_recorded" && String(e.detail?.verdict).startsWith("supports"));
  const bad = e.stage === "kernel_rejected" || e.stage === "rejected" || e.detail?.verdict === "does_not_support";
  const text = (
    <span className="flex items-start gap-2 rounded-lg px-1 py-1 hover:bg-white/5">
      <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${good ? "bg-emerald-400" : bad ? "bg-rose-400" : "bg-slate-500"}`} />
      <span className="min-w-0 flex-1 leading-snug">{describe(e, name)}</span>
      <span className="shrink-0 text-[10px] text-slate-500">{ago(ageSeconds(e.at, live))}</span>
    </span>
  );
  return <li>{e.condition_id ? <Link to={routes.condition(e.condition_id)}>{text}</Link> : text}</li>;
}

/** On a condition: who is working on it right now, and what changed recently. */
export function LiveConditionBanner({ conditionId }: { conditionId: string }) {
  const live = useLive();
  const working = live.presence.filter((p) => p.condition_id === conditionId && ageSeconds(p.at, live) < 180);
  const recent = live.events.filter((e) => e.condition_id === conditionId && !QUIET.has(e.stage) && ageSeconds(e.at, live) < 6 * 3600).slice(-3).reverse();
  if (!working.length && !recent.length) return null;
  return (
    <div className="mx-5 mt-4 rounded-xl border border-emerald-200 bg-emerald-50/70 p-3 text-[12.5px] text-emerald-950 sm:mx-6">
      {working.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <AgentAvatar color={familyColor(p.family)} role={roleOf(p.doing)} size={20} />
          <span>
            <b>{p.name}</b> ({familyName(p.family)}) is {p.doing} for this condition right now.
          </span>
        </div>
      ))}
      {recent.length > 0 && (
        <ul className={`${working.length ? "mt-2 border-t border-emerald-200 pt-2" : ""} space-y-0.5 text-emerald-900/90`}>
          {recent.map((e) => (
            <li key={e.seq}>
              {describe(e)} <span className="text-emerald-800/60">· {ago(ageSeconds(e.at, live))}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-[11px] text-emerald-900/70">Agent work becomes part of the map only after its quotes pass the check and a reviewer agrees.</p>
    </div>
  );
}
