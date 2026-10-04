// The star map: every condition is a point of light, placed by shared biology and colored by region.
import Graph from "graphology";
import { useEffect, useRef, useState } from "react";
import Sigma from "sigma";
import { DEFAULT_SETTINGS } from "sigma/settings";
import type { MapArea, StarMapData } from "../lib/map";
import { regionColor } from "../lib/map";
import { useReducedMotion } from "../lib/useReducedMotion";
import { LiveLayer, viewNotifier, type Project } from "./LiveLayer";

export interface Related {
  id: string;
  strength: number; // 0..1, line brightness
}

export interface RouteStop { id: string; step: number; label: string }

export interface MapProps {
  data: StarMapData;
  focus: string | null; // the selected condition
  related: Related[]; // its closest relatives, drawn as lines
  highlight: Set<string> | null; // explore mode: a set of conditions to light up (gene, symptom, group…)
  emphasized: string | null; // the relative currently pointed at in the panel
  onSelect: (id: string) => void;
  onBackground: () => void;
  route: RouteStop[];
  activeStep: number;
  onStop: (step: number) => void;
  agents?: AgentMarker[]; // live presence: agents working near a condition (status, never evidence)
  pulses?: Pulse[]; // newly published connections, drawn bright for a while
  ripples?: Ripple[]; // one ripple per workflow step at its condition
}

export interface AgentMarker { key: string; id: string; name: string; family: string | null; doing: string; color: string; role: string; active: boolean; opacity: number; since: string }
export interface Pulse { from: string; to: string; at: number }
export interface Ripple { key: string; id: string; at: number; color: string; size: number }

const DIM = "#26324f"; // faint, unselected stars
const SKY = "radial-gradient(ellipse at 50% 45%, #111a33 0%, #070b18 55%, #04060e 100%)";

interface LabelBox {
  key: string;
  text: string;
  x: number;
  y: number;
  level: "region" | "constellation" | "focus" | "relative";
  color: string;
}

const shorten = (text: string, max: number) => (text.length > max ? text.slice(0, max - 1).trimEnd() + "…" : text);

export function StarMap({ data, focus, related, highlight, emphasized, onSelect, onBackground, route, activeStep, onStop, agents, pulses, ripples }: MapProps) {
  const reduceMotion = useReducedMotion();
  const container = useRef<HTMLDivElement>(null);
  const sigma = useRef<Sigma | null>(null);
  const state = useRef({ focus, related, highlight, emphasized });
  const [labels, setLabels] = useState<LabelBox[]>([]);
  const [marker, setMarker] = useState<{ x: number; y: number } | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number; name: string; gene: string } | null>(null);
  const routeRef = useRef(route);
  routeRef.current = route;
  const [pins, setPins] = useState<(RouteStop & { x: number; y: number })[]>([]);
  const project = useRef<Project>(() => null);
  const [view] = useState(viewNotifier);
  const handlers = useRef({ onSelect, onBackground });
  handlers.current = { onSelect, onBackground };

  // ---- create the renderer once --------------------------------------------------------------------------
  useEffect(() => {
    if (!container.current) return;
    const graph = new Graph();
    for (const n of data.nodes) {
      graph.addNode(n.id, { x: n.x, y: -n.y, size: 1.1 + Math.min(n.connections, 30) / 35, color: "#e3c698", label: n.name, gene: n.gene, region: n.region });
    }
    const renderer = new Sigma(graph, container.current, {
      labelColor: { color: "#f1f5f9" },
      labelFont: "Inter, ui-sans-serif, system-ui",
      labelSize: 13,
      labelWeight: "600",
      renderLabels: false, // labels are drawn in the overlay, with overlap avoidance
      defaultEdgeColor: "#a5b4fc",
      minCameraRatio: 0.002,
      maxCameraRatio: 2.5,
      stagePadding: 30,
      zIndex: true,
      zoomToSizeRatioFunction: () => 1, // points keep their on-screen size while zooming
      defaultDrawNodeHover: () => {},
      nodeReducer: (node, attrs) => {
        const { focus: f, related: rel, highlight: hl, emphasized: em } = state.current;
        const relIds = new Set(rel.map((r) => r.id));
        if (f) {
          if (node === f) return { ...attrs, size: 17, color: "#ffffff", zIndex: 3 };
          if (relIds.has(node)) return { ...attrs, size: node === em ? 15 : 11, color: regionColor(attrs.region as number, 0.74), zIndex: 2 };
          return { ...attrs, size: 2.8, color: DIM, zIndex: 0 };
        }
        if (hl) {
          if (hl.has(node)) return { ...attrs, size: 8, color: "#fde68a", zIndex: 2 };
          return { ...attrs, size: 2.8, color: DIM, zIndex: 0 };
        }
        return attrs;
      },
      edgeReducer: (edge, attrs) => {
        const { emphasized: em } = state.current;
        if (em && graph.hasEdge(edge) && graph.target(edge) === em) return { ...attrs, size: 3, color: "#ffffff", zIndex: 2 };
        return attrs;
      },
    });
    renderer.on("clickNode", ({ node }) => handlers.current.onSelect(node));
    renderer.on("clickStage", () => handlers.current.onBackground());
    renderer.on("enterNode", ({ node }) => {
      const a = graph.getNodeAttributes(node);
      const p = renderer.graphToViewport({ x: a.x, y: a.y });
      setHover({ x: p.x, y: p.y, name: a.label as string, gene: a.gene as string });
      container.current!.style.cursor = "pointer";
    });
    renderer.on("leaveNode", () => {
      setHover(null);
      container.current!.style.cursor = "default";
    });

    // area labels follow the camera; bigger areas win when labels would overlap
    let frame = 0;
    const placeLabels = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const ratio = renderer.getCamera().getState().ratio;
        const areas: MapArea[] = [...(ratio > 0.28 ? data.regions.filter((r) => ratio < 0.75 || r.size >= 120) : []), ...(ratio < 0.55 ? data.constellations.filter((c) => c.size >= 8) : [])];
        const placed: { x0: number; x1: number; y0: number; y1: number }[] = [];
        const out: LabelBox[] = [];
        const tryPlace = (box: LabelBox, w: number, h: number) => {
          const b = { x0: box.x - w / 2, x1: box.x + w / 2, y0: box.y - h / 2, y1: box.y + h / 2 };
          if (b.x0 < 4 || b.y0 < 4 || b.x1 > renderer.getDimensions().width - 4 || b.y1 > renderer.getDimensions().height - 4) return;
          if (placed.some((p) => !(b.x1 < p.x0 || b.x0 > p.x1 || b.y1 < p.y0 || b.y0 > p.y1))) return;
          placed.push(b);
          out.push(box);
        };
        // the selected condition and its relatives first, then area names around them
        const { focus: f, related: rel, emphasized: em } = state.current;
        if (f && graph.hasNode(f)) {
          const a = graph.getNodeAttributes(f);
          const p = renderer.graphToViewport({ x: a.x, y: a.y });
          const text = shorten(a.label as string, 44);
          tryPlace({ key: "focus", text, x: p.x, y: p.y + 30, level: "focus", color: "#ffffff" }, text.length * 7.6 + 16, 22);
          for (const r of [...rel].sort((x, y) => (x.id === em ? -1 : y.id === em ? 1 : y.strength - x.strength))) {
            if (!graph.hasNode(r.id)) continue;
            const ra = graph.getNodeAttributes(r.id);
            const rp = renderer.graphToViewport({ x: ra.x, y: ra.y });
            const rt = shorten(ra.label as string, 30);
            tryPlace({ key: `rel:${r.id}`, text: rt, x: rp.x, y: rp.y + 22, level: "relative", color: regionColor(ra.region as number, 0.8) }, rt.length * 6.6 + 12, 18);
          }
        }
        // Deep inside a cluster, name the individual conditions nearest the centre of the view.
        if (!f && ratio < 0.07) {
          const { width, height } = renderer.getDimensions();
          const near: { id: string; x: number; y: number; d: number }[] = [];
          graph.forEachNode((id, a) => {
            const p = renderer.graphToViewport({ x: a.x, y: a.y });
            if (p.x > 0 && p.y > 0 && p.x < width && p.y < height) near.push({ id, x: p.x, y: p.y, d: Math.hypot(p.x - width / 2, p.y - height / 2) });
          });
          for (const n of near.sort((p, q) => p.d - q.d).slice(0, 60)) {
            const t = shorten(graph.getNodeAttribute(n.id, "label") as string, 30);
            tryPlace({ key: `node:${n.id}`, text: t, x: n.x, y: n.y + 14, level: "relative", color: "rgba(226,232,240,0.78)" }, t.length * 6.6 + 12, 18);
          }
        }
        for (const a of [...areas].sort((p, q) => (p.level === q.level ? q.size - p.size : p.level === "region" ? -1 : 1))) {
          const p = renderer.graphToViewport({ x: a.x, y: -a.y });
          const w = a.name.length * (a.level === "region" ? 7.4 : 6.4) + 14;
          const h = a.level === "region" ? 18 : 15;
          tryPlace({ key: `${a.level}:${a.id}`, text: a.name, x: p.x, y: p.y, level: a.level, color: regionColor(a.level === "region" ? a.id : -1, 0.8) }, w, h);
        }
        setLabels(out);
        setPins(routeRef.current.filter(s => graph.hasNode(s.id)).map(s => {
          const a = graph.getNodeAttributes(s.id);
          return { ...s, ...renderer.graphToViewport({ x: a.x, y: a.y }) };
        }));
        if (f && graph.hasNode(f)) {
          const fa = graph.getNodeAttributes(f);
          setMarker(renderer.graphToViewport({ x: fa.x, y: fa.y }));
        } else setMarker(null);
      });
    };
    renderer.on("afterRender", placeLabels);
    renderer.on("afterRender", view.notify);
    project.current = (id) => {
      if (!graph.hasNode(id)) return null;
      const a = graph.getNodeAttributes(id);
      return renderer.graphToViewport({ x: a.x, y: a.y });
    };
    sigma.current = renderer;
    return () => {
      cancelAnimationFrame(frame);
      renderer.kill();
      sigma.current = null;
    };
  }, [data]);

  // ---- react to selection changes ------------------------------------------------------------------------
  useEffect(() => {
    state.current = { focus, related, highlight, emphasized };
    const renderer = sigma.current;
    if (!renderer) return;
    const graph = renderer.getGraph();
    graph.clearEdges();
    if (focus && graph.hasNode(focus)) {
      for (const r of related) {
        if (graph.hasNode(r.id) && !graph.hasEdge(focus, r.id)) {
          const alpha = 0.35 + 0.55 * r.strength;
          graph.addEdge(focus, r.id, { size: 1 + 2 * r.strength, color: `rgba(199, 210, 254, ${alpha.toFixed(2)})` });
        }
      }
    }
    renderer.refresh();
  }, [focus, related, highlight, emphasized, route]);

  useEffect(() => {
    const renderer = sigma.current;
    if (!renderer) return;
    // Sigma divides by duration internally: 1 ms avoids a zero-duration NaN
    // while completing on the next frame without a visible tween.
    renderer.setSettings({
      zoomDuration: reduceMotion ? 1 : DEFAULT_SETTINGS.zoomDuration,
      doubleClickZoomingDuration: reduceMotion ? 1 : DEFAULT_SETTINGS.doubleClickZoomingDuration,
      inertiaDuration: reduceMotion ? 1 : DEFAULT_SETTINGS.inertiaDuration,
      inertiaRatio: reduceMotion ? 0 : DEFAULT_SETTINGS.inertiaRatio,
    });
    // Updating Sigma settings replaces cached coordinates before its deferred
    // render normalizes them. Finish that render before the camera reads them.
    renderer.refresh();
  }, [data, reduceMotion]);

  // ---- fly the camera to the selection ---------------------------------------------------------------------
  useEffect(() => {
    const renderer = sigma.current;
    if (!renderer) return;
    const ids = focus ? [focus, ...related.slice(0, 6).map((r) => r.id)] : highlight ? [...highlight] : [];
    const pts = ids.map((id) => renderer.getNodeDisplayData(id)).filter((p): p is NonNullable<typeof p> => !!p);
    if (!pts.length) {
      renderer.getCamera().animate({ x: 0.5, y: 0.5, ratio: 1 }, { duration: reduceMotion ? 1 : 700 });
      return;
    }
    const xs = pts.map((p) => p.x);
    const ys = pts.map((p) => p.y);
    const cx = focus ? pts[0].x : (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = focus ? pts[0].y : (Math.min(...ys) + Math.max(...ys)) / 2;
    const extent = Math.max(...xs.map((x) => Math.abs(x - cx)), ...ys.map((y) => Math.abs(y - cy)));
    const ratio = Math.min(0.9, Math.max(focus ? 0.1 : 0.22, extent * 2.6));
    renderer.getCamera().animate({ x: cx, y: cy, ratio }, { duration: reduceMotion ? 1 : 900, easing: "quadraticInOut" });
  }, [focus, highlight, related, reduceMotion]);

  const zoom = (factor: number) => {
    const cam = sigma.current?.getCamera();
    if (cam) cam.animate({ ratio: cam.getState().ratio * factor }, { duration: reduceMotion ? 1 : 250 });
  };

  return (
    <div className="absolute inset-x-0 top-0 bottom-[58dvh] overflow-hidden sm:bottom-0 sm:left-[432px]" style={{ background: SKY }}>
      <div ref={container} className="absolute inset-0" />
      <LiveLayer project={project} subscribe={view.subscribe} agents={agents ?? []} pulses={pulses ?? []} ripples={ripples ?? []} reduceMotion={reduceMotion} onSelect={onSelect} />
      {pins.length > 0 && <svg className="pointer-events-none absolute inset-0 h-full w-full overflow-hidden" aria-hidden>
        {pins.slice(1).filter((p, i) => p.id !== pins[i].id).map((p, i) => {
          const a = pins[i];
          const d = `M ${a.x} ${a.y} Q ${(a.x + p.x) / 2 + 25} ${(a.y + p.y) / 2 - 40} ${p.x} ${p.y}`;
          return <g key={`${p.step}-${i}`}><path d={d} fill="none" stroke="#f7cf86" strokeWidth="8" opacity="0.08" /><path d={d} fill="none" stroke="#f7cf86" strokeWidth="1.5" strokeDasharray="5 4" opacity="0.9" /></g>;
        })}
      </svg>}
      {pins.filter(p => p.step === activeStep || !pins.some(q => q.id === p.id && q.step === activeStep) && pins.find(q => q.id === p.id)?.step === p.step).map(p => <button key={p.step} onClick={() => onStop(p.step)} aria-label={`Directions stop ${p.step + 1}: ${p.label}`} style={{ left: p.x, top: p.y }} className={`absolute z-10 grid h-7 w-7 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border text-xs font-bold shadow-lg ${p.step === activeStep ? "border-white bg-amber-100 text-slate-900" : "border-amber-200/70 bg-slate-900 text-amber-100"}`}>{p.step + 1}</button>)}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
        {labels.map((l) => (
          <span
            key={l.key}
            className={`absolute -translate-x-1/2 -translate-y-1/2 whitespace-nowrap ${
              l.level === "focus"
                ? "text-[14px] font-semibold"
                : l.level === "relative"
                  ? "text-[12px] font-medium"
                  : `${focus || highlight ? "opacity-30" : ""} ${l.level === "region" ? "text-[11px] font-semibold uppercase tracking-[0.1em]" : "text-[11px] font-medium text-slate-300/75"}`
            }`}
            style={{ left: l.x, top: l.y, color: l.level === "constellation" ? undefined : l.color, textShadow: "0 1px 8px rgba(4,6,14,0.95), 0 0 2px rgba(4,6,14,0.9)" }}
          >
            {l.text}
          </span>
        ))}
      </div>
      {marker && focus && (
        <div className="pointer-events-none absolute z-[1]" style={{ left: marker.x, top: marker.y }} aria-hidden>
          <span data-focus-ring className="absolute -left-5 -top-5 h-10 w-10 motion-safe:animate-ping rounded-full border-2 border-white/60" />
          <span className="absolute -left-4 -top-4 h-8 w-8 rounded-full border border-white/40" />
        </div>
      )}
      {hover && (
        <div className="pointer-events-none absolute z-10 -translate-x-1/2 rounded-lg bg-slate-900/95 px-3 py-2 text-xs text-white shadow-xl ring-1 ring-white/10" style={{ left: hover.x, top: hover.y + 14 }}>
          <div className="font-medium">{hover.name}</div>
          <div className="font-mono text-[10px] text-slate-400">{hover.gene}</div>
        </div>
      )}
      <div className="absolute bottom-6 right-4 z-10 flex flex-col overflow-hidden rounded-xl bg-slate-900/80 text-white shadow-lg ring-1 ring-white/10 backdrop-blur">
        <button onClick={() => zoom(0.6)} className="px-3 py-2 text-lg leading-none hover:bg-white/10" aria-label="Zoom in">
          +
        </button>
        <button onClick={() => zoom(1.6)} className="border-t border-white/10 px-3 py-2 text-lg leading-none hover:bg-white/10" aria-label="Zoom out">
          −
        </button>
      </div>
    </div>
  );
}
