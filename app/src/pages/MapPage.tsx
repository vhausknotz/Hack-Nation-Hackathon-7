// The atlas as a map: search, fly to a condition, see who shares its biology. Like Google Maps for rare diseases.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { DirectionsPanel, STOPS } from "../components/DirectionsPanel";
import { Logo } from "../components/Layout";
import { SearchBox } from "../components/SearchBox";
import { StarMap, type Related } from "../components/StarMap";
import { GlobeMap } from "../components/GlobeMap";
import { getCondition, getGene, getGroup, getMechanism, getSymptom } from "../lib/data";
import { routes } from "../lib/links";
import { loadMap, type StarMapData } from "../lib/map";
import type { Brief, ConditionBundle } from "../lib/types";

type Explore = { kind: "g" | "s" | "grp" | "m"; title: string; subtitle: string; conditions: Brief[]; total: number; science: string };

export default function MapPage() {
  const { id, kind } = useParams();
  const navigate = useNavigate();
  const [map, setMap] = useState<StarMapData | null>(null);
  const [condition, setCondition] = useState<ConditionBundle | null>(null);
  const [explore, setExplore] = useState<Explore | null>(null);
  const [step, setStep] = useState(0);
  const [globe, setGlobe] = useState(true);
  const [emphasized, setEmphasized] = useState<string | null>(null);
  const conditionId = !kind && id ? decodeURIComponent(id) : null;

  useEffect(() => {
    loadMap().then(setMap);
  }, []);

  useEffect(() => {
    let active = true;
    setCondition(null);
    setStep(0);
    setEmphasized(null);
    if (conditionId) getCondition(conditionId).then((c) => { if (active) setCondition(c); });
    return () => { active = false; };
  }, [conditionId]);

  useEffect(() => {
    setExplore(null);
    if (!kind || !id) return;
    const key = decodeURIComponent(id);
    if (kind === "g")
      getGene(key).then((g) => g && setExplore({ kind: "g", title: g.symbol, subtitle: g.name, conditions: g.conditions, total: g.conditions.length, science: routes.gene(g.symbol) }));
    if (kind === "s")
      getSymptom(key).then((s) => s && setExplore({ kind: "s", title: s.plain[0] ?? s.name, subtitle: s.plain[0] ? s.name : "Symptom", conditions: s.conditions, total: s.direct_count, science: routes.symptom(s.id) }));
    if (kind === "grp")
      getGroup(key).then((g) => g && setExplore({ kind: "grp", title: g.name, subtitle: "Disease group", conditions: g.conditions, total: g.member_count, science: routes.group(g.id) }));
    if (kind === "m")
      getMechanism(key).then((m) => m && setExplore({ kind: "m", title: m.name, subtitle: `Shared machinery · ${m.source}`, conditions: m.conditions, total: m.condition_count, science: routes.mechanism(m.id) }));
  }, [kind, id]);

  const neighbors = useMemo(() => (condition ? condition.neighbors.filter((n) => !n.same_gene).sort((a, b) => b.score - a.score) : []), [condition]);
  const related: Related[] = useMemo(() => neighbors.slice(0, 8).map((n) => ({ id: n.id, strength: Math.min(1, n.score / 0.6) })), [neighbors]);
  const highlight = useMemo(() => (explore ? new Set(explore.conditions.map((c) => c.id)) : null), [explore]);
  const route = useMemo(() => condition ? STOPS.map((label, index) => ({
    label, step: index, id: index === 1 && !(condition.communities ?? []).some(o => o.kind === "patient_organization") ? neighbors.find(n => n.community)?.id ?? condition.id : index === 2 ? neighbors[0]?.id ?? condition.id : condition.id,
  })) : [], [condition, neighbors]);
  const selectStep = (next: number) => {
    setStep(next);
    setEmphasized(route[next]?.id === condition?.id ? null : route[next]?.id ?? null);
  };
  const MapView = globe ? GlobeMap : StarMap;

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden bg-[#04060e]">
      {map ? (
        <MapView
          data={map}
          focus={condition ? condition.id : null}
          related={condition ? related : []}
          highlight={highlight}
          emphasized={emphasized}
          route={route}
          activeStep={step}
          onStop={selectStep}
          onSelect={(nodeId) => navigate(routes.condition(nodeId))}
          onBackground={() => (conditionId || kind) && navigate("/")}
        />
      ) : (
        <div className="absolute inset-0 grid place-items-center text-sm text-slate-400">Drawing the map…</div>
      )}

      <div className="absolute right-3 top-[72px] z-20 flex rounded-full border border-white/15 bg-slate-950/85 p-1 text-[11px] text-white shadow-lg sm:top-4" aria-label="Map view">
        <button aria-pressed={globe} onClick={() => setGlobe(true)} className={`rounded-full px-3 py-1.5 ${globe ? "bg-white/15" : "text-slate-400"}`}>Globe</button>
        <button aria-pressed={!globe} onClick={() => setGlobe(false)} className={`rounded-full px-3 py-1.5 ${!globe ? "bg-white/15" : "text-slate-400"}`}>Flat map</button>
      </div>

      {/* search, top left like a maps app */}
      <div className="absolute left-3 right-3 top-3 z-20 sm:left-4 sm:right-auto sm:top-4 sm:w-[400px]">
        <div className="flex items-center gap-3 rounded-2xl bg-white/95 px-3 py-2 shadow-2xl ring-1 ring-black/5 backdrop-blur">
          <Logo iconOnly />
          <div className="min-w-0 flex-1">
            <SearchBox size="sm" placeholder="Search a condition, gene or symptom" bare />
          </div>
        </div>
      </div>

      {/* the panel: a side card on desktop, a bottom sheet on phones */}
      <Panel open>
        {conditionId && condition && map ? (
          <DirectionsPanel key={condition.id} c={condition} neighbors={neighbors} step={step} onStep={selectStep} emphasized={emphasized} onEmphasize={setEmphasized} onClose={() => navigate("/")} />
        ) : conditionId ? (
          <PanelMessage>Loading…</PanelMessage>
        ) : explore ? (
          <ExplorePanel e={explore} onClose={() => navigate("/")} />
        ) : kind ? (
          <PanelMessage>Loading…</PanelMessage>
        ) : (
          <Welcome map={map} />
        )}
      </Panel>
    </div>
  );
}

function Panel({ children }: { open: boolean; children: ReactNode }) {
  return (
    <aside className="absolute inset-x-0 bottom-0 z-10 max-h-[58dvh] overflow-y-auto rounded-t-3xl bg-white shadow-[0_-12px_40px_rgba(0,0,0,0.35)] sm:inset-x-auto sm:bottom-auto sm:left-4 sm:top-[84px] sm:max-h-[calc(100dvh-100px)] sm:w-[400px] sm:rounded-2xl sm:shadow-2xl">
      <div className="mx-auto mt-2 h-1 w-10 rounded-full bg-slate-200 sm:hidden" />
      {children}
    </aside>
  );
}

function PanelMessage({ children }: { children: ReactNode }) {
  return <div className="p-6 text-sm text-ink-soft">{children}</div>;
}

function CloseButton({ onClose }: { onClose: () => void }) {
  return (
    <button onClick={onClose} className="rounded-full p-1.5 text-ink-faint hover:bg-ink-wash hover:text-ink" aria-label="Close">
      ✕
    </button>
  );
}

// ---- nothing selected ----------------------------------------------------------------------------------------
function Welcome({ map }: { map: StarMapData | null }) {
  const examples: [string, string][] = [
    ["SNAP25", routes.condition("MONDO:0014590")],
    ["STXBP1", routes.condition("MONDO:0012812")],
    ["Dravet syndrome", routes.condition("MONDO:0100135")],
    ["Atonic seizures", routes.explore("s", "HP:0010819")],
  ];
  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold leading-snug tracking-tight">A map of {map ? map.nodes.length.toLocaleString("en-US") : "7,000+"} rare genetic conditions</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">
        Every point of light is one condition. Conditions that share symptoms or work through the same biology sit close together, even when their names have nothing in common.
      </p>
      <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">Search for yours, or tap a light. Follow the directions to find people, explore studies, and decide what to ask next.</p>
      <div className="mt-5 flex flex-wrap gap-2">
        {examples.map(([label, to]) => (
          <Link key={label} to={to} className="rounded-full border border-ink-line px-3 py-1 text-sm text-ink-soft transition hover:border-machinery/40 hover:text-machinery">
            {label}
          </Link>
        ))}
      </div>
      <p className="mt-6 text-xs leading-relaxed text-ink-faint">
        Built from open biomedical data. Connections are computed leads for experts to check, not medical advice.{" "}
        <Link to="/about" className="underline hover:text-ink">
          How it works
        </Link>
      </p>
    </div>
  );
}

// ---- a gene, symptom, group or mechanism ----------------------------------------------------------------------------
function ExplorePanel({ e, onClose }: { e: Explore; onClose: () => void }) {
  const [filter, setFilter] = useState("");
  const what = { g: "caused by this gene", s: "with this symptom", grp: "in this group", m: "whose genes share this machinery" }[e.kind];
  const shown = e.conditions.filter((b) => !filter || `${b.name} ${b.gene}`.toLowerCase().includes(filter.toLowerCase()));
  return (
    <div className="p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="text-xs font-medium text-ink-soft">{e.subtitle}</div>
        <CloseButton onClose={onClose} />
      </div>
      <h1 className="mt-2 text-2xl font-semibold leading-tight tracking-tight">{e.title}</h1>
      <p className="mt-2 text-[15px] text-ink-soft">
        <b className="text-ink">{e.total.toLocaleString("en-US")}</b> condition{e.total === 1 ? "" : "s"} {what}, lit up on the map.
      </p>
      {e.conditions.length > 8 && (
        <input value={filter} onChange={(ev) => setFilter(ev.target.value)} placeholder="Filter" className="mt-4 w-full rounded-lg border border-ink-line px-3 py-2 text-sm outline-none focus:border-machinery/50" />
      )}
      <ul className="mt-3 divide-y divide-ink-line/70">
        {shown.slice(0, 60).map((b) => (
          <li key={b.id}>
            <Link to={routes.condition(b.id)} className="flex items-baseline justify-between gap-3 py-2.5 text-sm hover:text-machinery">
              <span className="min-w-0 truncate">{b.name}</span>
              <span className="shrink-0 font-mono text-[11px] text-ink-faint">{b.gene}</span>
            </Link>
          </li>
        ))}
      </ul>
      <Link to={e.science} className="mt-6 flex items-center justify-between rounded-xl bg-ink-wash px-4 py-3 text-sm font-medium transition hover:bg-machinery-soft hover:text-machinery">
        Show the science
        <span aria-hidden>→</span>
      </Link>
    </div>
  );
}
