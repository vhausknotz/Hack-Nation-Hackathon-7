// Time-lapse of how the atlas grew: every reviewed finding ripples at its condition and every new connection draws
// itself, in the order they happened, compressed into about forty seconds. Data: /live/history (engine, from the
// signed ledger and published-change events). Real events only; nothing is simulated.
import { useEffect, useMemo, useRef, useState } from "react";
import { LIVE_API } from "../lib/live";
import type { Pulse, Ripple } from "./StarMap";

type Finding = [at: string, condition: string, kind: "s" | "g" | "t" | "o"];
type Connection = [at: string, from: string, to: string];
const DURATION = 40_000;
const COLOR = { s: "#86efac", g: "#f9a8d4", t: "#93c5fd", o: "#fde68a" } as const;

export function useReplay(active: boolean) {
  const [data, setData] = useState<{ findings: Finding[]; connections: Connection[] } | null>(null);
  const [progress, setProgress] = useState(0); // 0..1
  const [playing, setPlaying] = useState(true);
  const emitted = useRef({ f: 0, c: 0 });
  const [layers, setLayers] = useState<{ pulses: Pulse[]; ripples: Ripple[] }>({ pulses: [], ripples: [] });

  useEffect(() => {
    if (!active || data) return;
    fetch(`${LIVE_API}/live/history`).then(r => r.json()).then(setData).catch(() => setData({ findings: [], connections: [] }));
  }, [active, data]);

  const span = useMemo(() => {
    if (!data) return null;
    const times = [...data.findings.map(f => Date.parse(f[0])), ...data.connections.map(c => Date.parse(c[0]))].filter(Number.isFinite);
    if (!times.length) return null;
    return { start: Math.min(...times), end: Math.max(...times) };
  }, [data]);

  useEffect(() => {
    if (!active || !playing || !span || !data) return;
    let last = performance.now();
    const tick = window.setInterval(() => {
      const now = performance.now();
      setProgress(p => {
        const next = Math.min(1, p + (now - last) / DURATION);
        last = now;
        const until = span.start + (span.end - span.start) * next;
        const fresh: { pulses: Pulse[]; ripples: Ripple[] } = { pulses: [], ripples: [] };
        while (emitted.current.f < data.findings.length && Date.parse(data.findings[emitted.current.f][0]) <= until) {
          const [, id, kind] = data.findings[emitted.current.f];
          fresh.ripples.push({ key: `rp:${emitted.current.f}`, id, at: Date.now(), color: COLOR[kind] ?? COLOR.o, size: 1.3 });
          emitted.current.f += 1;
        }
        while (emitted.current.c < data.connections.length && Date.parse(data.connections[emitted.current.c][0]) <= until) {
          const [, from, to] = data.connections[emitted.current.c];
          fresh.pulses.push({ from, to, at: Date.now() });
          emitted.current.c += 1;
        }
        if (fresh.pulses.length || fresh.ripples.length) {
          const cutoff = Date.now() - 9000;
          setLayers(l => ({ pulses: [...l.pulses.filter(x => x.at > cutoff), ...fresh.pulses].slice(-60),
                            ripples: [...l.ripples.filter(x => x.at > cutoff), ...fresh.ripples].slice(-120) }));
        }
        if (next >= 1) setPlaying(false);
        return next;
      });
    }, 100);
    return () => window.clearInterval(tick);
  }, [active, playing, span, data]);

  const restart = () => { emitted.current = { f: 0, c: 0 }; setLayers({ pulses: [], ripples: [] }); setProgress(0); setPlaying(true); };
  const current = span ? new Date(span.start + (span.end - span.start) * progress) : null;
  return {
    ready: !!data, empty: !!data && !span, layers, playing, progress, current,
    counts: { findings: emitted.current.f, connections: emitted.current.c, totalFindings: data?.findings.length ?? 0, totalConnections: data?.connections.length ?? 0 },
    toggle: () => (progress >= 1 ? restart() : setPlaying(p => !p)), restart,
  };
}

export function ReplayBar({ replay, onClose }: { replay: ReturnType<typeof useReplay>; onClose: () => void }) {
  const r = replay;
  const date = r.current?.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  return <div className="absolute bottom-[calc(58dvh+12px)] left-3 right-3 z-30 rounded-2xl bg-slate-950/90 p-3 text-white shadow-2xl ring-1 ring-white/15 sm:bottom-6 sm:left-[calc(432px+24px)] sm:right-24">
    <div className="flex items-center gap-3">
      <button onClick={r.toggle} aria-label={r.playing ? "Pause replay" : "Play replay"} className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white/15 hover:bg-white/25">{r.playing ? "❚❚" : "▶"}</button>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs">
          <b className="text-sm">{!r.ready ? "Loading the history…" : r.empty ? "No history recorded yet" : `How the atlas grew · ${date ?? ""}`}</b>
          {r.ready && !r.empty && <span className="text-slate-300"><span className="text-emerald-300">{r.counts.findings}</span> / {r.counts.totalFindings} reviewed findings · <span className="text-amber-200">{r.counts.connections}</span> / {r.counts.totalConnections} new connections</span>}
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-emerald-300/80" style={{ width: `${r.progress * 100}%` }} /></div>
        <p className="mt-1.5 text-[10.5px] text-slate-400">Real events from the evidence log, replayed in about forty seconds. <span className="text-emerald-300">●</span> symptom <span className="text-pink-300">●</span> patient group <span className="text-sky-300">●</span> study · lines are new connections.</p>
      </div>
      <button onClick={r.restart} aria-label="Restart replay" className="hidden rounded-full px-2 py-1 text-xs text-slate-300 hover:bg-white/10 sm:block">↺</button>
      <button onClick={onClose} aria-label="Close replay" className="rounded-full px-2 py-1 text-slate-300 hover:bg-white/10">✕</button>
    </div>
  </div>;
}
