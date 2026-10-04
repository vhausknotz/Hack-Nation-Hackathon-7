// Animated live layer drawn over either map: agents at work, ripples for each step, and new connections
// that draw themselves with a travelling spark. Everything here is status; evidence lives in the panel.
import { useEffect, useRef, useState } from "react";
import { AgentAvatar } from "./LiveActivity";
import type { AgentMarker, Pulse, Ripple } from "./StarMap";

export type Project = (id: string) => { x: number; y: number } | null;

const DRAW_MS = 1700; // a new connection draws itself
const GLOW_MS = 60000; // then keeps glowing, slowly fading
const RIPPLE_MS = 1600;

function curve(a: { x: number; y: number }, b: { x: number; y: number }) {
  const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
  const bend = Math.min(80, len * 0.22);
  return { a, b, c: { x: (a.x + b.x) / 2 - (dy / len) * bend, y: (a.y + b.y) / 2 + (dx / len) * bend } };
}

function point(q: ReturnType<typeof curve>, t: number) {
  const u = 1 - t;
  return { x: u * u * q.a.x + 2 * u * t * q.c.x + t * t * q.b.x, y: u * u * q.a.y + 2 * u * t * q.c.y + t * t * q.b.y };
}

function stroke(ctx: CanvasRenderingContext2D, q: ReturnType<typeof curve>, upto: number) {
  ctx.beginPath();
  const steps = Math.max(2, Math.round(40 * upto));
  for (let i = 0; i <= steps; i++) {
    const p = point(q, (i / steps) * upto);
    if (i === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  }
  ctx.stroke();
}

function spark(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, color: string, alpha: number) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, `rgba(255,255,255,${alpha})`);
  g.addColorStop(0.25, color.replace("ALPHA", String(alpha * 0.8)));
  g.addColorStop(1, color.replace("ALPHA", "0"));
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
}

export function LiveLayer({ project, subscribe, agents, pulses, ripples, reduceMotion, onSelect }: {
  project: React.MutableRefObject<Project>;
  subscribe: (listener: () => void) => () => void;
  agents: AgentMarker[];
  pulses: Pulse[];
  ripples: Ripple[];
  reduceMotion: boolean;
  onSelect: (id: string) => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const props = useRef({ agents, pulses, ripples, reduceMotion });
  props.current = { agents, pulses, ripples, reduceMotion };
  const [pins, setPins] = useState<(AgentMarker & { x: number; y: number })[]>([]);
  const redraw = useRef<() => void>(() => {});

  useEffect(() => {
    const el = canvas.current!;
    const ctx = el.getContext("2d")!;
    let frame = 0, width = 1, height = 1;
    const resize = () => {
      const r = el.getBoundingClientRect();
      width = r.width; height = r.height;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      el.width = Math.round(width * dpr); el.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      schedule();
    };
    const draw = () => {
      frame = 0;
      const now = Date.now();
      const { pulses, ripples, agents, reduceMotion: still } = props.current;
      const at = project.current;
      ctx.clearRect(0, 0, width, height);
      let animating = false;

      // New connections: draw, spark, arrive, then glow with flowing light.
      for (const p of pulses) {
        const age = now - p.at;
        if (age > DRAW_MS + GLOW_MS) continue;
        const a = at(p.from), b = at(p.to);
        if (!a || !b) continue;
        const q = curve(a, b);
        const grow = still ? 1 : Math.min(1, age / DRAW_MS);
        const eased = 1 - Math.pow(1 - grow, 3);
        const fade = still ? 0.8 : age < DRAW_MS ? 1 : 1 - (age - DRAW_MS) / GLOW_MS;
        ctx.lineCap = "round";
        ctx.strokeStyle = `rgba(134,239,172,${(0.18 * fade).toFixed(3)})`;
        ctx.lineWidth = 9;
        stroke(ctx, q, eased);
        ctx.strokeStyle = `rgba(187,247,208,${(0.35 + 0.6 * fade).toFixed(3)})`;
        ctx.lineWidth = 1.6 + 1.4 * fade;
        stroke(ctx, q, eased);
        if (!still) {
          animating = true;
          if (grow < 1) {
            const h = point(q, eased);
            spark(ctx, h.x, h.y, 16, "rgba(134,239,172,ALPHA)", 1);
            for (let i = 1; i <= 5; i++) {
              const t = Math.max(0, eased - i * 0.035);
              const tp = point(q, t);
              spark(ctx, tp.x, tp.y, 7 - i, "rgba(187,247,208,ALPHA)", 0.6 - i * 0.1);
            }
          } else {
            // light flowing along the new connection
            for (let k = 0; k < 2; k++) {
              const t = (((age - DRAW_MS) / 1600 + k / 2) % 1);
              const fp = point(q, t);
              spark(ctx, fp.x, fp.y, 6, "rgba(187,247,208,ALPHA)", 0.85 * fade);
            }
            const since = age - DRAW_MS;
            if (since < RIPPLE_MS * 1.5) {
              for (const delay of [0, 350]) {
                const r = (since - delay) / RIPPLE_MS;
                if (r < 0 || r > 1) continue;
                ctx.strokeStyle = `rgba(134,239,172,${(1 - r).toFixed(3)})`;
                ctx.lineWidth = 2;
                ctx.beginPath(); ctx.arc(b.x, b.y, 6 + r * 34, 0, Math.PI * 2); ctx.stroke();
              }
            }
          }
          spark(ctx, a.x, a.y, 14 + 4 * Math.sin(age / 300), "rgba(253,230,138,ALPHA)", 0.5 * fade);
        }
      }

      // Each workflow step ripples at its condition.
      for (const r of ripples) {
        const age = now - r.at;
        if (age > RIPPLE_MS * 1.6) continue;
        const p = at(r.id);
        if (!p) continue;
        if (still) {
          ctx.strokeStyle = r.color; ctx.globalAlpha = 0.7; ctx.lineWidth = 2;
          ctx.beginPath(); ctx.arc(p.x, p.y, 14 * r.size, 0, Math.PI * 2); ctx.stroke(); ctx.globalAlpha = 1;
          continue;
        }
        animating = true;
        for (const delay of [0, 280]) {
          const t = (age - delay) / RIPPLE_MS;
          if (t < 0 || t > 1) continue;
          ctx.globalAlpha = (1 - t) * 0.9;
          ctx.strokeStyle = r.color;
          ctx.lineWidth = 2.2 * (1 - t) + 0.5;
          ctx.beginPath(); ctx.arc(p.x, p.y, 5 + t * 30 * r.size, 0, Math.PI * 2); ctx.stroke();
        }
        ctx.globalAlpha = 1;
      }

      // Agents: a beam from each active agent to the light it works on.
      const placed: (AgentMarker & { x: number; y: number })[] = [];
      for (const agent of agents) {
        const p = at(agent.id);
        if (!p || p.x < 8 || p.y < 50 || p.x > width - 8 || p.y > height - 24) continue;
        let x = p.x + 18, y = p.y - 18;
        while (placed.some((o) => Math.hypot(o.x - x, o.y - y) < 26)) x += 24;
        placed.push({ ...agent, x, y });
        if (agent.active) {
          ctx.setLineDash([3, 4]);
          ctx.lineDashOffset = still ? 0 : -(now / 60) % 7;
          ctx.strokeStyle = agent.color; ctx.globalAlpha = 0.75; ctx.lineWidth = 1.2;
          ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(p.x, p.y); ctx.stroke();
          ctx.setLineDash([]); ctx.globalAlpha = 1;
          spark(ctx, p.x, p.y, 10 + (still ? 0 : 3 * Math.sin(now / 250)), "rgba(255,255,255,ALPHA)", 0.35);
          if (!still) animating = true;
        }
      }
      setPins((old) => (old.length === placed.length && old.every((o, i) => o.key === placed[i].key && Math.abs(o.x - placed[i].x) < 0.5 && Math.abs(o.y - placed[i].y) < 0.5) ? old : placed));
      if (animating) schedule();
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(draw); };
    redraw.current = schedule;
    const observer = new ResizeObserver(resize);
    observer.observe(el);
    const unsubscribe = subscribe(schedule);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); unsubscribe(); };
  }, [project, subscribe]);

  useEffect(() => { redraw.current(); }, [agents, pulses, ripples, reduceMotion]);

  return (
    <>
      <canvas ref={canvas} className="pointer-events-none absolute inset-0 z-[5] h-full w-full" aria-hidden />
      {pins.map((a) => (
        <button
          key={a.key}
          onClick={() => onSelect(a.id)}
          style={{ left: a.x, top: a.y, opacity: a.opacity }}
          title={`${a.name} · ${a.active ? a.doing : a.since}`}
          aria-label={`Agent ${a.name}: ${a.active ? a.doing : a.since}. Open this condition.`}
          className={`group absolute z-10 -translate-x-1/2 -translate-y-1/2 transition-opacity duration-700 ${a.active && !reduceMotion ? "animate-[bob_2.4s_ease-in-out_infinite]" : ""}`}
        >
          <AgentAvatar color={a.color} role={a.role} size={a.active ? 24 : 20} pulse={a.active && !reduceMotion} />
          <span className="pointer-events-none absolute left-7 top-0.5 hidden whitespace-nowrap rounded-md bg-slate-900/90 px-2 py-0.5 text-[10px] text-slate-100 ring-1 ring-white/10 group-hover:block group-focus:block">
            {a.name} · {a.active ? a.doing : a.since}
          </span>
        </button>
      ))}
    </>
  );
}

/** A small notifier the maps call after every redraw, so the live layer follows the camera. */
export function viewNotifier() {
  const listeners = new Set<() => void>();
  return {
    notify: () => listeners.forEach((l) => l()),
    subscribe: (l: () => void) => { listeners.add(l); return () => { listeners.delete(l); }; },
  };
}
