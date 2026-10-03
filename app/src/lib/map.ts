// The star map: positions, regions and constellations from pipeline/build_map.py.
import { dataUrl } from "./dataVersion";

export interface MapNode {
  id: string;
  name: string;
  gene: string;
  x: number;
  y: number;
  region: number;
  constellation: number;
  category: number;
  connections: number;
}

export interface MapArea {
  id: number;
  level: "region" | "constellation";
  name: string;
  blurb: string;
  x: number;
  y: number;
  size: number;
  named_by: string;
}

export interface StarMapData {
  nodes: MapNode[];
  byId: Map<string, MapNode>;
  edges: [number, number, number][];
  regions: MapArea[];
  constellations: MapArea[];
  regionById: Map<number, MapArea>;
  constellationById: Map<number, MapArea>;
  categories: string[];
}

type RawNode = [string, string, string, number, number, number, number, number, number];

let cached: Promise<StarMapData> | null = null;

export function loadMap(): Promise<StarMapData> {
  if (!cached) {
    cached = fetch(dataUrl("/data/map.json"))
      .then((r) => r.json())
      .then((raw: { nodes: RawNode[]; edges: [number, number, number][]; regions: MapArea[]; constellations: MapArea[]; categories: string[] }) => {
        const nodes = raw.nodes.map(([id, name, gene, x, y, region, constellation, category, connections]) => ({ id, name, gene, x, y, region, constellation, category, connections }));
        return {
          nodes,
          byId: new Map(nodes.map((n) => [n.id, n])),
          edges: raw.edges,
          regions: raw.regions,
          constellations: raw.constellations,
          regionById: new Map(raw.regions.map((r) => [r.id, r])),
          constellationById: new Map(raw.constellations.map((c) => [c.id, c])),
          categories: raw.categories,
        };
      });
  }
  return cached;
}

/** A calm, well-separated hue per region (golden-angle spacing), as hex. */
export function regionColor(region: number, lightness = 0.66): string {
  if (region < 0) return "#5b6478";
  const hue = (region * 0.618034 + 0.05) % 1;
  return hslToHex(hue, 0.72, lightness);
}

function hslToHex(h: number, s: number, l: number): string {
  const f = (n: number) => {
    const k = (n + h * 12) % 12;
    const a = s * Math.min(l, 1 - l);
    const c = l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
    return Math.round(c * 255)
      .toString(16)
      .padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}
