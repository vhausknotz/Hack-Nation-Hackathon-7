// The atlas as a map: search, fly to a condition, see who shares its biology. Like Google Maps for rare diseases.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { DirectionsPanel, STOPS } from "../components/DirectionsPanel";
import { Logo } from "../components/Layout";
import { SearchBox } from "../components/SearchBox";
import { StarMap, type Related } from "../components/StarMap";
import { GlobeMap } from "../components/GlobeMap";
import { ReplayBar, useReplay } from "../components/Replay";
import { LiveConditionBanner, LivePanel, LiveToasts, SparseInvite, useLiveLayers } from "../components/LiveActivity";
import { conditionRevision, getCondition, getGene, getGroup, getMechanism, getSymptom, onDataChange } from "../lib/data";
import { ageSeconds, useLive, type LiveState } from "../lib/live";
import { useReducedMotion } from "../lib/useReducedMotion";
import type { Pulse } from "../components/StarMap";
import { routes } from "../lib/links";
import { loadMap, type StarMapData } from "../lib/map";
import type { Brief, ConditionBundle } from "../lib/types";

// One stable empty list: a fresh [] on every live-feed render would make the map re-fly and undo the user's zoom.
const NO_RELATED: Related[] = [];

type Explore = { kind: "g" | "s" | "grp" | "m"; title: string; subtitle: string; conditions: (Brief & { group?: boolean; studies?: number })[]; total: number; science: string;
  people?: { name: string; affiliation: string; genes: string[] }[] };

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
  const live = useLive();
  const layers = useLiveLayers(live);
  const [params, setParams] = useSearchParams();
  const replaying = params.get("replay") === "1";
  const replay = useReplay(replaying);
  const echo = useEcho(live, !conditionId && !kind && !replaying);
  const [revision, setRevision] = useState("base");

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

  // The live engine republished this condition: show the new evidence without a reload.
  useEffect(() => onDataChange(() => { if (conditionId) setRevision(conditionRevision(conditionId)); }), [conditionId]);
  useEffect(() => {
    if (!conditionId || revision === "base") return;
    let active = true;
    getCondition(conditionId).then((c) => { if (active && c) setCondition(c); });
    return () => { active = false; };
  }, [revision, conditionId]);

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
      getMechanism(key).then((m) => m && setExplore({ kind: "m", title: m.name, subtitle: `Shared machinery · ${m.source}`, total: m.condition_count, science: routes.mechanism(m.id),
        // Ranked for someone holding a therapeutic idea for this machinery: communities and studies first.
        conditions: [...m.conditions].sort((a, b) => Number(!!b.group) - Number(!!a.group) || (b.studies ?? 0) - (a.studies ?? 0)), people: m.bridging_people }));
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
          related={condition ? related : NO_RELATED}
          highlight={highlight}
          emphasized={emphasized}
          route={route}
          activeStep={step}
          onStop={selectStep}
          onSelect={(nodeId) => navigate(routes.condition(nodeId))}
          onBackground={() => (conditionId || kind) && navigate("/")}
          agents={replaying ? [] : layers.agents}
          pulses={replaying ? replay.layers.pulses : echo ? [...layers.pulses, echo.pulse] : layers.pulses}
          ripples={replaying ? replay.layers.ripples : layers.ripples}
        />
      ) : (
        <div className="absolute inset-0 grid place-items-center text-sm text-slate-400">Drawing the map…</div>
      )}

      <div className="absolute right-3 top-[72px] z-20 flex rounded-full border border-white/15 bg-slate-950/85 p-1 text-[11px] text-white shadow-lg sm:top-4" aria-label="Map view">
        <button aria-pressed={globe} onClick={() => setGlobe(true)} className={`rounded-full px-3 py-1.5 ${globe ? "bg-white/15" : "text-slate-400"}`}>Globe</button>
        <button aria-pressed={!globe} onClick={() => setGlobe(false)} className={`rounded-full px-3 py-1.5 ${!globe ? "bg-white/15" : "text-slate-400"}`}>Flat map</button>
      </div>

      <LivePanel nameOf={(nodeId) => map?.byId.get(nodeId)?.name} />
      {echo && <div className="pointer-events-none absolute bottom-[calc(58dvh+8px)] left-1/2 z-10 -translate-x-1/2 rounded-full bg-slate-950/70 px-3 py-1 text-[10.5px] text-emerald-200/90 motion-safe:animate-[toast-in_.5s_ease-out] sm:bottom-12 sm:left-[calc(50%+216px)]">Recently connected by reviewed evidence: {echo.from} ↔ {echo.to}</div>}
      {!replaying && <LiveToasts onOpen={(nodeId) => navigate(routes.condition(nodeId))} />}
      {replaying && <ReplayBar replay={replay} onClose={() => { const next = new URLSearchParams(params); next.delete("replay"); setParams(next); }} />}

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
          <>
          <LiveConditionBanner conditionId={condition.id} />
          <SparseInvite id={condition.id} name={condition.name} symptoms={condition.phenotype_count} connections={neighbors.length} />
          <DirectionsPanel key={condition.id} c={condition} neighbors={neighbors} step={step} onStep={selectStep} emphasized={emphasized} onEmphasize={setEmphasized} onClose={() => navigate("/")} />
          </>
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

/** On the home view, now and then redraw one real, recently published connection, captioned. Never invented. */
function useEcho(live: LiveState, home: boolean) {
  const [echo, setEcho] = useState<{ pulse: Pulse; from: string; to: string } | null>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    if (!home || reduce) { setEcho(null); return; }
    const pick = () => {
      const recent = (live.overlay?.changes ?? []).filter((c) => c.new_connections.length && ageSeconds(c.at, live) < 7 * 86400);
      if (!recent.length) return;
      const c = recent[Math.floor(Math.random() * recent.length)];
      const n = c.new_connections[Math.floor(Math.random() * c.new_connections.length)];
      setEcho({ pulse: { from: c.condition_id, to: n.id, at: Date.now() }, from: c.name, to: n.name });
      window.setTimeout(() => setEcho(null), 9000);
    };
    const first = window.setTimeout(pick, 4000);
    const every = window.setInterval(pick, 22000);
    return () => { window.clearTimeout(first); window.clearInterval(every); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [home, reduce, live.overlay?.version]);
  return echo;
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
  const live = useLive();
  const journeys: { title: string; text: string; to: string }[] = [
    { title: "I organize a patient group", text: "STXBP1: a shared natural-history study, who runs it, and a partnership proposal", to: `${routes.condition("MONDO:0012812")}` },
    { title: "We were just diagnosed", text: "MELAS (MT-TL1): what it is, people to contact, studies, questions to ask", to: routes.condition("MONDO:0800032") },
    { title: "My condition looks empty", text: "Ask an AI agent to expand it from published research, and watch it here", to: "/agents" },
  ];
  const day = live.events.filter((e) => ageSeconds(e.at, live) < 86400);
  const agents = new Set(day.filter((e) => e.stage === "queued").map((e) => e.agent)).size;
  const checked = day.filter((e) => e.stage === "kernel_accepted" || e.stage === "kernel_rejected").length;
  const latest = [...(live.overlay?.changes ?? [])].reverse().find((c) => c.new_connections.length);
  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold leading-snug tracking-tight">A living map of {map ? map.nodes.length.toLocaleString("en-US") : "7,000+"} rare genetic conditions</h1>
      <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">
        Every point of light is one condition. Conditions that share symptoms or work through the same biology sit close together, even when their names have nothing in common. Search for yours, or start from a journey:
      </p>
      <div className="mt-4 space-y-2">
        {journeys.map((j) => (
          <Link key={j.title} to={j.to} className="block rounded-xl border border-ink-line p-3 transition hover:border-machinery/40 hover:bg-machinery-soft/30">
            <span className="block text-sm font-semibold text-ink">{j.title} →</span>
            <span className="mt-0.5 block text-xs text-ink-soft">{j.text}</span>
          </Link>
        ))}
      </div>
      {(agents > 0 || checked > 0 || latest) && (
        <div className="mt-4 rounded-xl bg-slate-950 p-3 text-xs text-slate-200">
          <div className="flex items-center gap-2 font-semibold text-white"><span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />Growing right now</div>
          <p className="mt-1 text-slate-300">
            {agents > 0 ? `${agents} AI agent${agents === 1 ? "" : "s"} contributed today` : "Agents contribute through our MCP server"}{checked > 0 ? ` · ${checked} findings quote-checked` : ""}.
            {latest && <> Newest connection: <Link className="text-emerald-300 underline" to={routes.condition(latest.condition_id)}>{latest.name}</Link> ↔ {latest.new_connections[0].name}.</>}
          </p>
          <Link to="/?replay=1" className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-1 font-semibold text-white hover:bg-white/20">▶ Watch the atlas grow</Link>
        </div>
      )}
      <p className="mt-5 text-xs leading-relaxed text-ink-faint">
        Built from open biomedical data and reviewed agent contributions. Connections are leads for experts to check, not medical advice.{" "}
        <Link to="/about" className="underline hover:text-ink">How it works</Link> · <Link to="/impact" className="underline hover:text-ink">The 10× case</Link> · <Link to="/agents" className="underline hover:text-ink">For agents</Link> · <Link to="/contributors" className="underline hover:text-ink">Contributors</Link> · <Link to="/campaigns" className="underline hover:text-ink">Campaigns</Link>
      </p>
    </div>
  );
}

// ---- a gene, symptom, group or mechanism ----------------------------------------------------------------------------
function ExplorePanel({ e, onClose }: { e: Explore; onClose: () => void }) {
  const [filter, setFilter] = useState("");
  const what = { g: "caused by this gene", s: "with this symptom", grp: "in this group", m: "whose genes share this machinery" }[e.kind];
  const shown = e.conditions.filter((b) => !filter || `${b.name} ${b.gene}`.toLowerCase().includes(filter.toLowerCase()));
  const people = e.people ?? [];
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
      {e.kind === "m" && people.length > 0 && (
        <div className="mt-4 rounded-xl bg-ink-wash/70 p-3 text-xs">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">People working across this machinery</div>
          <ul className="mt-1.5 space-y-1">{people.map((p) => <li key={p.name}><b className="font-semibold text-ink">{p.name}</b>{p.affiliation ? `, ${p.affiliation}` : ""} <span className="text-ink-faint">· publishes on {p.genes.join(", ")}</span></li>)}</ul>
          <p className="mt-1.5 text-[10.5px] text-ink-faint">From recent PubMed patient research per gene. The same mechanism under different gene names.</p>
        </div>
      )}
      {e.kind === "m" && <p className="mt-3 text-xs text-ink-faint">Conditions with patient groups and studies are listed first.</p>}
      {e.conditions.length > 8 && (
        <input value={filter} onChange={(ev) => setFilter(ev.target.value)} placeholder="Filter" className="mt-4 w-full rounded-lg border border-ink-line px-3 py-2 text-sm outline-none focus:border-machinery/50" />
      )}
      <ul className="mt-3 divide-y divide-ink-line/70">
        {shown.slice(0, 60).map((b) => (
          <li key={b.id}>
            <Link to={routes.condition(b.id)} className="flex items-baseline justify-between gap-3 py-2.5 text-sm hover:text-machinery">
              <span className="min-w-0 truncate">{b.name}</span>
              <span className="flex shrink-0 items-center gap-1.5">
                {b.group && <span className="rounded-full bg-machinery-soft px-1.5 py-0.5 text-[10px] text-machinery">group</span>}
                {!!b.studies && <span className="rounded-full bg-ink-wash px-1.5 py-0.5 text-[10px] text-ink-soft">{b.studies} stud{b.studies === 1 ? "y" : "ies"}</span>}
                <span className="font-mono text-[11px] text-ink-faint">{b.gene}</span>
              </span>
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
