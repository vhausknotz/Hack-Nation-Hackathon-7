// The atlas as a map: search, fly to a condition, see who shares its biology. Like Google Maps for rare diseases.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useEvidence } from "../components/EvidenceDrawer";
import { Logo } from "../components/Layout";
import { SearchBox } from "../components/SearchBox";
import { StarMap, type Related } from "../components/StarMap";
import { getCondition, getGene, getGroup, getMechanism, getSymptom } from "../lib/data";
import { external, routes } from "../lib/links";
import { loadMap, regionColor, type StarMapData } from "../lib/map";
import { closeness, plainRarity, plainReason } from "../lib/plain";
import { connectionPanel, mechanismReason } from "../lib/reasons";
import type { Brief, ConditionBundle, Neighbor } from "../lib/types";

type Explore = { kind: "g" | "s" | "grp" | "m"; title: string; subtitle: string; conditions: Brief[]; total: number; science: string };

export default function MapPage() {
  const { id, kind } = useParams();
  const navigate = useNavigate();
  const [map, setMap] = useState<StarMapData | null>(null);
  const [condition, setCondition] = useState<ConditionBundle | null>(null);
  const [explore, setExplore] = useState<Explore | null>(null);
  const [emphasized, setEmphasized] = useState<string | null>(null);
  const conditionId = !kind && id ? decodeURIComponent(id) : null;

  useEffect(() => {
    loadMap().then(setMap);
  }, []);

  useEffect(() => {
    setCondition(null);
    setEmphasized(null);
    if (conditionId) getCondition(conditionId).then((c) => setCondition(c));
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

  const neighbors = useMemo(() => (condition ? [...condition.neighbors].sort((a, b) => b.score - a.score) : []), [condition]);
  const related: Related[] = useMemo(() => neighbors.slice(0, 8).map((n) => ({ id: n.id, strength: Math.min(1, n.score / 0.6) })), [neighbors]);
  const highlight = useMemo(() => (explore ? new Set(explore.conditions.map((c) => c.id)) : null), [explore]);

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden bg-[#04060e]">
      {map ? (
        <StarMap
          data={map}
          focus={condition ? condition.id : null}
          related={condition ? related : []}
          highlight={highlight}
          emphasized={emphasized}
          onSelect={(nodeId) => navigate(routes.condition(nodeId))}
          onBackground={() => (conditionId || kind) && navigate("/")}
        />
      ) : (
        <div className="absolute inset-0 grid place-items-center text-sm text-slate-400">Drawing the map…</div>
      )}

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
          <ConditionPanel c={condition} neighbors={neighbors} map={map} emphasized={emphasized} setEmphasized={setEmphasized} onClose={() => navigate("/")} />
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
      <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">Search for yours, or tap any point, to see who shares its biology.</p>
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

// ---- a condition --------------------------------------------------------------------------------------------
function ConditionPanel({ c, neighbors, map, emphasized, setEmphasized, onClose }: {
  c: ConditionBundle; neighbors: Neighbor[]; map: StarMapData; emphasized: string | null; setEmphasized: (id: string | null) => void; onClose: () => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const node = map.byId.get(c.id);
  const region = node ? map.regionById.get(node.region) : undefined;
  const constellation = node ? map.constellationById.get(node.constellation) : undefined;
  const rarity = plainRarity(c);
  const list = showAll ? neighbors.slice(0, 10) : neighbors.slice(0, 4);
  return (
    <div className="p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 text-xs font-medium text-ink-soft">
          {node && <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: regionColor(node.region) }} />}
          <span className="truncate" title={constellation?.blurb || region?.blurb}>
            {constellation?.name || region?.name || "Rare genetic condition"}
          </span>
        </div>
        <CloseButton onClose={onClose} />
      </div>
      <h1 className="mt-2 text-2xl font-semibold leading-tight tracking-tight">{c.name}</h1>
      <p className="mt-2 text-[15px] text-ink-soft">
        Caused by changes in the <b className="font-mono text-ink">{c.gene.symbol}</b> gene{rarity ? <> · {rarity}</> : null}
      </p>

      <h2 className="mt-7 text-lg font-semibold">You're not alone</h2>
      {neighbors.length ? (
        <>
          <p className="mt-1 text-sm text-ink-soft">These conditions share its biology. Tap one to see why.</p>
          <ul className="mt-3 space-y-2">
            {list.map((n) => (
              <RelativeRow key={n.id} c={c} n={n} open={emphasized === n.id} onToggle={() => setEmphasized(emphasized === n.id ? null : n.id)} />
            ))}
          </ul>
          {neighbors.length > 4 && (
            <button onClick={() => setShowAll(!showAll)} className="mt-3 text-sm font-medium text-machinery hover:underline">
              {showAll ? "Show fewer" : `Show ${Math.min(10, neighbors.length) - 4} more`}
            </button>
          )}
        </>
      ) : (
        <p className="mt-2 text-sm text-ink-soft">Too little is recorded about this condition to compare it with others yet.</p>
      )}

      <h2 className="mt-7 text-lg font-semibold">What already exists</h2>
      <p className="mt-1 text-sm text-ink-soft">Studies, registries and patient groups for this condition are not mapped in the atlas yet. Meanwhile, these trusted sources list them:</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <ExternalChip href={external.trialsSearch(c.gene.symbol)}>Clinical studies</ExternalChip>
        {c.xrefs.Orphanet?.[0] && <ExternalChip href={external.orphanet(c.xrefs.Orphanet[0])}>Orphanet</ExternalChip>}
        {c.xrefs.GARD?.[0] && <ExternalChip href={external.gard(c.xrefs.GARD[0])}>GARD (NIH)</ExternalChip>}
      </div>

      <Link to={routes.conditionDetails(c.id)} className="mt-8 flex items-center justify-between rounded-xl bg-ink-wash px-4 py-3 text-sm font-medium transition hover:bg-machinery-soft hover:text-machinery">
        Show the science
        <span aria-hidden>→</span>
      </Link>
      <p className="mt-3 text-xs leading-relaxed text-ink-faint">Connections are computed from open data: leads for experts to check, not medical advice.</p>
    </div>
  );
}

function RelativeRow({ c, n, open, onToggle }: { c: ConditionBundle; n: Neighbor; open: boolean; onToggle: () => void }) {
  const openEvidence = useEvidence();
  const navigate = useNavigate();
  const tag = closeness(n);
  const sources = [...new Set(n.mechanisms.map((m) => mechanismReason(m, c.gene.symbol, n.gene, c.dict.mechanisms).source.split(/[ ,·]/)[0]).concat(n.symptoms.length ? ["HPO"] : []))];
  return (
    <li className={`rounded-xl border transition ${open ? "border-machinery/40 bg-machinery-soft/40" : "border-ink-line hover:border-ink-faint"}`}>
      <button onClick={onToggle} className="w-full px-4 py-3 text-left">
        <div className="flex items-baseline justify-between gap-3">
          <span className="font-medium leading-snug">{n.name}</span>
          <span className={`shrink-0 text-[11px] font-semibold ${tag === "Very close" ? "text-machinery" : "text-ink-faint"}`}>{tag}</span>
        </div>
        <p className="mt-1 text-sm leading-snug text-ink-soft">{plainReason(c, n)}</p>
      </button>
      {open && (
        <div className="border-t border-machinery/20 px-4 py-3 text-xs text-ink-soft">
          <div>
            Where this comes from: <span className="text-ink">{sources.join(", ") || "computed from open data"}</span>
          </div>
          {n.effect === "different" && <div className="mt-1 text-caution">Note: the two gene changes act differently, so treatments may not transfer.</div>}
          <div className="mt-2 flex gap-4">
            <button onClick={() => openEvidence(connectionPanel(c, n))} className="font-medium text-machinery hover:underline">
              See the evidence
            </button>
            <button onClick={() => navigate(routes.condition(n.id))} className="font-medium text-machinery hover:underline">
              Go there on the map
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

function ExternalChip({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="rounded-full border border-ink-line px-3 py-1 text-sm text-ink-soft transition hover:border-ink-faint hover:text-ink">
      {children} <span aria-hidden>↗</span>
    </a>
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
