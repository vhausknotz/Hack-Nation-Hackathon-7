// Internal routes and links to the original sources.

export const routes = {
  condition: (id: string) => `/c/${encodeURIComponent(id)}`, // on the map
  conditionDetails: (id: string) => `/c/${encodeURIComponent(id)}/details`, // "Show the science"
  explore: (kind: "g" | "s" | "grp" | "m", id: string) => `/explore/${kind}/${encodeURIComponent(id)}`, // light up on the map
  gene: (symbol: string) => `/g/${encodeURIComponent(symbol)}`,
  symptom: (id: string) => `/s/${encodeURIComponent(id)}`,
  group: (id: string) => `/group/${encodeURIComponent(id)}`,
  mechanism: (id: string) => `/m/${encodeURIComponent(id)}`,
};

export function mechanismSource(id: string): { source: string; url: string } {
  if (id.startsWith("CPX-")) return { source: "Complex Portal", url: `https://www.ebi.ac.uk/complexportal/complex/${id}` };
  if (id.startsWith("R-HSA")) return { source: "Reactome", url: `https://reactome.org/content/detail/${id}` };
  return { source: "Gene Ontology", url: `https://amigo.geneontology.org/amigo/term/${id}` };
}

export const external = {
  pubmed: (pmid: string) => `https://pubmed.ncbi.nlm.nih.gov/${pmid.replace(/^PMID:\s*/, "")}/`,
  hpo: (id: string) => `https://hpo.jax.org/browse/term/${id}`,
  monarch: (id: string) => `https://monarchinitiative.org/${id}`,
  omim: (id: string) => `https://omim.org/entry/${id.replace("OMIM:", "")}`,
  orphanet: (id: string) => `https://www.orpha.net/en/disease/detail/${id.replace(/^(Orphanet|ORPHA):/, "")}`,
  gard: (id: string) => `https://rarediseases.info.nih.gov/diseases/${parseInt(id.replace("GARD:", ""), 10)}/index`,
  string: (symbol: string) => `https://string-db.org/network/9606.${symbol}`,
  hgnc: (hgncId: string) => `https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/${hgncId}`,
  trialsSearch: (term: string) => `https://clinicaltrials.gov/search?term=${encodeURIComponent(term)}`,
  pubmedSearch: (term: string) => `https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(term)}`,
};

/** "OMIM:612164" -> link to OMIM; returns null for prefixes we don't link. */
export function recordLink(record: string): string | null {
  if (record.startsWith("OMIM:")) return external.omim(record);
  if (record.startsWith("ORPHA:")) return external.orphanet(record);
  if (record.startsWith("PMID:")) return external.pubmed(record);
  if (record.startsWith("G2P:")) return `https://www.ebi.ac.uk/gene2phenotype/lgd/${record.slice(4)}`;
  return null;
}
