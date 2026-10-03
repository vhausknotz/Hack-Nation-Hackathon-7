// "Why are you connected?": your condition → your gene → their gene → their condition, every link clickable.
import { useNavigate } from "react-router-dom";
import { routes } from "../lib/links";
import { connectionPanel, geneEvidencePanel, mechanismReason, shortSymptomName } from "../lib/reasons";
import type { ConditionBundle, Neighbor } from "../lib/types";
import { useEvidence, type EvidencePanel } from "./EvidenceDrawer";

const COLORS = { ink: "#0f172a", soft: "#64748b", line: "#cbd5e1", machinery: "#4f46e5", hypothesis: "#7c3aed", symptom: "#0d9488" };

function wrap(text: string, max = 24, lines = 2): string[] {
  const words = text.split(" ");
  const out: string[] = [];
  let cur = "";
  for (const w of words) {
    if ((cur + " " + w).trim().length > max && cur) {
      out.push(cur);
      cur = w;
    } else cur = (cur + " " + w).trim();
  }
  if (cur) out.push(cur);
  if (out.length > lines) {
    const kept = out.slice(0, lines);
    kept[lines - 1] = kept[lines - 1].slice(0, max - 1) + "…";
    return kept;
  }
  return out;
}

function mechanismLabel(n: Neighbor): string {
  const m = n.mechanisms[0];
  if (!m) return "similar machinery";
  if (m.k === "interaction") return "proteins bind each other";
  if (m.k === "partner") return `both bind ${m.symbol}`;
  if (m.k === "complex") return "parts of one complex";
  if (m.k === "pathway") return "same pathway";
  return "same cellular process";
}

function machineryPanel(c: ConditionBundle, n: Neighbor): EvidencePanel {
  return {
    title: `${c.gene.symbol} and ${n.gene}: shared molecular machinery`,
    tier: "data",
    summary: (
      <p>
        Each item below is recorded in a curated database. That the two genes share this machinery is data; that this makes their conditions similar is the atlas's hypothesis.
      </p>
    ),
    itemsTitle: "Shared machinery",
    items: n.mechanisms.map((m) => {
      const r = mechanismReason(m, c.gene.symbol, n.gene, c.dict.mechanisms);
      return { label: r.text, detail: r.source, url: r.url };
    }),
    note: n.mechanisms.length === 0 ? "No single shared complex or pathway stands out; the similarity comes from many small overlaps." : undefined,
  };
}

export function PathDiagram({ c, n }: { c: ConditionBundle; n: Neighbor }) {
  const open = useEvidence();
  const navigate = useNavigate();
  const same = n.same_gene;
  const y = 158;
  const A = { x: 95, y };
  const B = { x: 785, y };
  const GA = { x: same ? 440 : 300, y };
  const GB = { x: same ? 440 : 580, y };
  const sharedSymptoms = n.symptoms.length;
  const firstSymptom = n.symptoms[0] ? shortSymptomName(n.symptoms[0], c.dict.symptoms) : null;

  const edge = (x1: number, x2: number, label: string, color: string, onClick: () => void, dashed = false) => (
    <g className="cursor-pointer" onClick={onClick}>
      <line x1={x1} y1={y} x2={x2} y2={y} stroke="transparent" strokeWidth={22} />
      <line x1={x1} y1={y} x2={x2} y2={y} stroke={color} strokeWidth={2} strokeDasharray={dashed ? "6 5" : undefined} className="transition-all hover:[stroke-width:3.5]" />
      <text x={(x1 + x2) / 2} y={y - 12} textAnchor="middle" fontSize={12.5} fill={color} fontWeight={500}>
        {label}
      </text>
    </g>
  );

  const conditionNode = (p: { x: number; y: number }, title: string, gene: string, mine: boolean, onClick: () => void) => (
    <g className="cursor-pointer" onClick={onClick}>
      <circle cx={p.x} cy={p.y} r={mine ? 26 : 22} fill={mine ? COLORS.ink : "#fff"} stroke={COLORS.ink} strokeWidth={2} />
      {wrap(title).map((line, i) => (
        <text key={i} x={p.x} y={p.y + 46 + i * 16} textAnchor="middle" fontSize={13} fill={COLORS.ink} fontWeight={mine ? 600 : 500}>
          {line}
        </text>
      ))}
      <title>{`${title} (${gene})`}</title>
    </g>
  );

  const geneNode = (p: { x: number; y: number }, symbol: string) => (
    <g className="cursor-pointer" onClick={() => navigate(routes.gene(symbol))}>
      <rect x={p.x - 44} y={p.y - 16} width={88} height={32} rx={8} fill={COLORS.ink} />
      <text x={p.x} y={p.y + 5} textAnchor="middle" fontSize={13} fill="#fff" fontFamily="ui-monospace, monospace" fontWeight={600}>
        {symbol}
      </text>
      <title>{`Gene ${symbol}`}</title>
    </g>
  );

  return (
    <div className="card overflow-hidden p-2 sm:p-4">
      <svg viewBox="0 0 880 230" className="w-full" role="img" aria-label={`How ${c.name} connects to ${n.name}`}>
        {/* the computed hypothesis: symptom/overall similarity between the two conditions */}
        <g className="cursor-pointer" onClick={() => open(connectionPanel(c, n))}>
          <path d={`M ${A.x} ${A.y - 26} Q ${(A.x + B.x) / 2} -20 ${B.x} ${B.y - 22}`} fill="none" stroke="transparent" strokeWidth={20} />
          <path d={`M ${A.x} ${A.y - 26} Q ${(A.x + B.x) / 2} -20 ${B.x} ${B.y - 22}`} fill="none" stroke={COLORS.hypothesis} strokeWidth={2} strokeDasharray="7 6" />
          <text x={(A.x + B.x) / 2} y={36} textAnchor="middle" fontSize={12.5} fill={COLORS.hypothesis} fontWeight={500}>
            {sharedSymptoms ? `share ${sharedSymptoms} symptom${sharedSymptoms > 1 ? "s" : ""}${firstSymptom ? `, e.g. ${firstSymptom.toLowerCase()}` : ""}` : "computed connection"} · hypothesis
          </text>
        </g>
        {edge(A.x + 26, GA.x - 44, "caused by", COLORS.soft, () => open(geneEvidencePanel(c)))}
        {!same && edge(GA.x + 44, GB.x - 44, mechanismLabel(n), n.mechanisms.length ? COLORS.machinery : COLORS.hypothesis, () => open(machineryPanel(c, n)), !n.mechanisms.length)}
        {edge(GB.x + 44, B.x - 22, "causes", COLORS.soft, () => navigate(routes.condition(n.id)))}
        {conditionNode(A, c.name, c.gene.symbol, true, () => open(geneEvidencePanel(c)))}
        {conditionNode(B, n.name, n.gene, false, () => navigate(routes.condition(n.id)))}
        {geneNode(GA, c.gene.symbol)}
        {!same && geneNode(GB, n.gene)}
      </svg>
    </div>
  );
}
