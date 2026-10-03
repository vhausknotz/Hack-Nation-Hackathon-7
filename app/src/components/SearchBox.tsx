import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { routes } from "../lib/links";
import { loadIndex, search, type SearchKind, type SearchResult } from "../lib/search";

const KIND: Record<SearchKind, { label: string; className: string }> = {
  c: { label: "Condition", className: "bg-ink-wash text-ink-soft" },
  g: { label: "Gene", className: "bg-ink text-white" },
  s: { label: "Symptom", className: "bg-symptom-soft text-symptom" },
  grp: { label: "Group", className: "bg-ink-wash text-ink-soft" }, // a group of conditions
  m: { label: "Mechanism", className: "bg-machinery-soft text-machinery" },
};

function hrefFor(r: SearchResult): string {
  return r.kind === "c" ? routes.condition(r.id) : routes.explore(r.kind, r.id);
}

function extraText(r: SearchResult): string {
  if (!r.extra) return "";
  if (r.kind === "c") return r.extra;
  if (r.kind === "g") return `${r.extra} condition${r.extra === "1" ? "" : "s"}`;
  if (r.kind === "s") return `in ${Number(r.extra).toLocaleString("en-US")} conditions`;
  if (r.kind === "grp") return r.extra ? `group of ${r.extra}` : "group";
  return "";
}

export function SearchBox({ size = "lg", autoFocus = false, placeholder, bare = false }: { size?: "lg" | "sm"; autoFocus?: boolean; placeholder?: string; bare?: boolean }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    if (!query.trim()) {
      setResults([]);
      return;
    }
    setLoading(true);
    search(query).then((r) => {
      if (!cancelled) {
        setResults(r);
        setActive(0);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [query]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const go = (r: SearchResult) => {
    setOpen(false);
    setQuery("");
    navigate(hrefFor(r));
  };

  const big = size === "lg";
  return (
    <div ref={box} className="relative w-full">
      <div className={`flex items-center gap-3 ${bare ? "py-1" : `rounded-2xl border border-ink-line bg-white shadow-sm transition focus-within:border-machinery/50 focus-within:shadow-md ${big ? "px-5 py-4" : "px-3 py-2"}`}`}>
        <svg aria-hidden viewBox="0 0 20 20" className={`${big ? "h-5 w-5" : "h-4 w-4"} shrink-0 text-ink-faint`} fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="9" cy="9" r="6" />
          <path d="M13.5 13.5L18 18" strokeLinecap="round" />
        </svg>
        <input
          autoFocus={autoFocus}
          value={query}
          onFocus={() => {
            setOpen(true);
            loadIndex();
          }}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, results.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter" && results[active]) {
              go(results[active]);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          placeholder={placeholder ?? (big ? "Search a condition, gene or symptom" : "Search the atlas")}
          className={`w-full bg-transparent outline-none placeholder:text-ink-faint ${big ? "text-lg" : "text-sm"}`}
          aria-label="Search the atlas"
          role="combobox"
          aria-expanded={open && results.length > 0}
        />
        {loading && <span className="h-1.5 w-1.5 animate-ping rounded-full bg-machinery" />}
      </div>
      {open && query.trim() && (
        <ul className={`absolute z-30 mt-2 max-h-[28rem] overflow-y-auto rounded-xl border border-ink-line bg-white p-1.5 shadow-xl ${bare ? "-left-12 w-[calc(100%+3.5rem)] sm:-left-14 sm:w-[calc(100%+4rem)]" : "w-full"}`} role="listbox">
          {results.length === 0 && !loading && <li className="px-3 py-3 text-sm text-ink-soft">No match. Try a gene symbol, a condition name or a symptom.</li>}
          {results.map((r, i) => (
            <li key={`${r.kind}:${r.id}`} role="option" aria-selected={i === active}>
              <button
                onMouseEnter={() => setActive(i)}
                onClick={() => go(r)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left ${i === active ? "bg-ink-wash" : ""}`}
              >
                <span className={`w-20 shrink-0 rounded px-1.5 py-0.5 text-center text-[10px] font-semibold uppercase tracking-wide ${KIND[r.kind].className}`}>{KIND[r.kind].label}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{r.label}</span>
                  {r.matched && <span className="block truncate text-xs text-ink-faint">matched “{r.matched}”</span>}
                </span>
                <span className="shrink-0 font-mono text-xs text-ink-faint">{extraText(r)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
