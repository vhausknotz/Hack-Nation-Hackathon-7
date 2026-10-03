// Side panel that explains any connection: what it claims, how sure we are, and where it comes from.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ExternalLink, TierBadge, type Tier } from "./ui";

export interface EvidenceItem {
  label: string;
  detail?: string;
  url?: string;
  date?: string;
}

export interface EvidencePanel {
  title: string;
  tier: Tier;
  summary: ReactNode;
  items: EvidenceItem[];
  itemsTitle?: string;
  note?: ReactNode;
}

const Ctx = createContext<(panel: EvidencePanel) => void>(() => {});
export const useEvidence = () => useContext(Ctx);

export function EvidenceProvider({ children }: { children: ReactNode }) {
  const [panel, setPanel] = useState<EvidencePanel | null>(null);
  const close = useCallback(() => setPanel(null), []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  return (
    <Ctx.Provider value={setPanel}>
      {children}
      <div className={`fixed inset-0 z-40 bg-ink/10 transition-opacity ${panel ? "opacity-100" : "pointer-events-none opacity-0"}`} onClick={close} />
      <aside
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-ink-line bg-white transition-transform duration-200 ${panel ? "translate-x-0 shadow-2xl" : "translate-x-full"}`}
        aria-hidden={!panel}
      >
        {panel && (
          <>
            <div className="flex items-start justify-between gap-4 border-b border-ink-line p-6">
              <div>
                <div className="eyebrow mb-2">Evidence</div>
                <h3 className="text-lg font-semibold leading-snug">{panel.title}</h3>
                <div className="mt-3">
                  <TierBadge tier={panel.tier} />
                </div>
              </div>
              <button onClick={close} className="rounded-md p-1 text-ink-faint hover:bg-ink-wash hover:text-ink" aria-label="Close">
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6">
              <div className="text-[15px] leading-relaxed text-ink-soft">{panel.summary}</div>
              {panel.items.length > 0 && (
                <>
                  <div className="eyebrow mb-3 mt-8">{panel.itemsTitle ?? "Sources"}</div>
                  <ul className="space-y-3">
                    {panel.items.map((it, i) => (
                      <li key={i} className="rounded-lg border border-ink-line p-3">
                        <div className="flex items-baseline justify-between gap-3">
                          <div className="text-sm font-medium">{it.url ? <ExternalLink href={it.url}>{it.label}</ExternalLink> : it.label}</div>
                          {it.date && <div className="shrink-0 text-xs text-ink-faint">{it.date}</div>}
                        </div>
                        {it.detail && <div className="mt-1 text-sm text-ink-soft">{it.detail}</div>}
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {panel.note && <div className="mt-8 rounded-lg bg-ink-wash p-4 text-sm text-ink-soft">{panel.note}</div>}
            </div>
          </>
        )}
      </aside>
    </Ctx.Provider>
  );
}
