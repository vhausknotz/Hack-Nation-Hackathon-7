// Shapes of the static data bundles written by pipeline/export_app.py.

export type Effect = "loss_of_function" | "gain_of_function" | "dominant_negative" | "non_loss_of_function" | "unknown";

export interface Brief {
  id: string;
  name: string;
  gene: string;
  category: string;
}

export interface GeneEvidence {
  source: string;
  confidence?: string;
  mechanism?: string;
  inheritance?: string;
  url?: string;
  date?: string;
  pmids?: string[];
}

export interface Prevalence {
  class: string | null;
  class_kind: string | null;
  class_geography: string | null;
  cases: number | null;
  cases_source: string | null;
  source: string;
  url: string;
}

export interface Phenotype {
  id: string;
  frequency: string;
  sources: string[];
  refs: string[];
}

export type SharedMechanism =
  | { k: "interaction"; score: number }
  | { k: "partner"; id: string; symbol: string }
  | { k: "complex" | "pathway" | "go"; id: string };

export interface Neighbor extends Brief {
  score: number;
  sym: number;
  mech: number;
  same_gene: boolean;
  effect: "same" | "different" | "unknown" | "not_comparable";
  mech_known?: boolean; // both genes have interaction-level data
  sym_known?: boolean;
  community?: string | null;
  asset_count?: number;
  same_category: boolean;
  symptoms: string[];
  mechanisms: SharedMechanism[];
}

export interface Lookalike extends Brief {
  family: string;
  sym: number;
  mech: number;
  same_category: boolean;
}

export interface Partner {
  hgnc_id: string;
  symbol: string;
  score: number;
  has_condition: boolean;
}

export interface Dosage {
  haploinsufficiency_score: string;
  haploinsufficiency: string;
  url: string;
}

/** symptom id -> [name, plain-language name, number of conditions with it] */
export type SymptomDict = Record<string, [string, string | null, number]>;
/** mechanism term id -> [name, number of genes with it] */
export type MechanismDict = Record<string, [string, number]>;

export interface ConditionBundle {
  plain?: { summary: string; model: string; prompt: string } | null;
  communities?: Community[];
  assets?: ResearchAsset[];
  id: string;
  name: string;
  also_known_as: string[];
  disease: string;
  disease_name: string;
  synthetic: boolean;
  definition: string;
  category: string;
  gene: { hgnc_id: string; symbol: string; name: string; strength: string; evidence: GeneEvidence[] };
  other_genes_for_this_disease: string[];
  variant_effect: { value: Effect; sources: { source: string; value: string; support?: string; url?: string }[] };
  inheritance: string[];
  onset: string[];
  prevalence: Prevalence | null;
  phenotypes: Phenotype[];
  phenotype_count: number;
  xrefs: Record<string, string[]>;
  url: string;
  machinery: { complexes: string[]; pathways: string[]; go: string[]; partners: Partner[]; dosage: Dosage | null };
  other_conditions_of_gene: Brief[];
  neighbors: Neighbor[];
  lookalikes: Lookalike[];
  dict: { symptoms: SymptomDict; mechanisms: MechanismDict };
}

export interface ActionReview {
  status: "reviewed" | "independently_reviewed" | "human_reviewed";
  verdict: "supports" | "supports_with_qualification";
  reason: string;
}

export interface Community {
  id: string;
  name: string;
  homepage: string;
  kind: "patient_organization" | "research_program" | "information_service" | "professional_network" | "company";
  scope: "this_condition" | "this_gene" | "broader_group";
  quote: string;
  page: string;
  page_read: "live" | "archived_snapshot";
  page_date: string;
  claim_id: string;
  via?: string;
  review: ActionReview;
}

export interface ResearchAsset {
  id: string;
  title: string;
  type: string;
  status: string;
  phase: string;
  restriction: string | null;
  quotes: string[];
  url: string;
  source_date: string;
  claim_id: string;
  review: ActionReview;
}

export interface GeneBundle {
  hgnc_id: string;
  symbol: string;
  name: string;
  aliases: string[];
  previous_symbols: string[];
  gene_groups: string[];
  uniprot: string[];
  entrez: string;
  complexes: string[];
  pathways: string[];
  go: string[];
  partners: Partner[];
  dosage: Dosage | null;
  mechanism_neighbors: { hgnc_id: string; symbol: string; score: number }[];
  url: string;
  conditions: (Brief & { effect: Effect; phenotype_count: number; inheritance: string[] })[];
  dict: { mechanisms: MechanismDict };
}

export interface SymptomBundle {
  id: string;
  name: string;
  plain: string[];
  synonyms: string[];
  definition: string;
  conditions_with_it: number;
  direct_count: number;
  conditions: (Brief & { frequency: string })[];
  url: string;
}

export interface GroupBundle {
  id: string;
  name: string;
  definition: string;
  synonyms: string[];
  member_count: number;
  conditions: Brief[];
  url: string;
}

export interface MechanismBundle {
  id: string;
  name: string;
  source: string;
  url: string;
  genes_with_it: number;
  condition_genes: string[];
  conditions: Brief[];
  condition_count: number;
}

export interface Meta {
  built: string;
  shards: Record<string, number>;
  counts: Record<string, unknown> & { conditions: number; genes: number; groups: number };
  sources: Record<string, { file: string; url: string; description: string; license: string; retrieved: string }>;
}
