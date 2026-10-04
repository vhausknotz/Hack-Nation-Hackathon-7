// Family navigation assistant: ask a question about this condition; the answer comes only from the atlas page,
// names the sections it used, and says when the atlas doesn't know. Hidden unless the operator has switched it on.
import { useEffect, useState } from "react";
import { LIVE_API } from "../lib/live";

let statusPromise: Promise<boolean> | null = null;
const available = () => (statusPromise ??= fetch(`${LIVE_API}/assistant/status`).then(r => r.json()).then(s => !!s.available).catch(() => false));

const EXAMPLES = ["What does this condition usually involve?", "Is there a patient group we can contact?", "Are there studies we could ask about?"];

export function AskAtlas({ conditionId, name }: { conditionId: string; name: string }) {
  const [on, setOn] = useState(false);
  const [question, setQuestion] = useState("");
  const [state, setState] = useState<{ status: "idle" | "waiting" | "done" | "error"; answer?: string; sections?: string[]; error?: string }>({ status: "idle" });
  useEffect(() => { available().then(setOn); }, []);
  useEffect(() => { setState({ status: "idle" }); setQuestion(""); }, [conditionId]);
  if (!on) return null;
  const ask = async (q: string) => {
    if (q.trim().length < 3) return;
    setQuestion(q);
    setState({ status: "waiting" });
    try {
      const r = await fetch(`${LIVE_API}/assistant/ask`, { method: "POST", headers: { "Content-Type": "text/plain" }, body: JSON.stringify({ condition_id: conditionId, question: q }) });
      const b = await r.json();
      if (!r.ok) throw new Error(b.error || "failed");
      for (let i = 0; i < 40; i++) {  // answers usually arrive within a few seconds
        await new Promise(res => setTimeout(res, 1500));
        const a = await fetch(`${LIVE_API}/assistant/answer/${b.id}`).then(x => x.json());
        if (a.state === "answered") return setState({ status: "done", answer: a.answer, sections: a.sections });
        if (a.state === "unavailable" || a.state === "failed") throw new Error("The assistant is not available right now.");
      }
      throw new Error("No answer yet. Please try again later.");
    } catch (e) {
      setState({ status: "error", error: e instanceof Error ? e.message : "Something went wrong." });
    }
  };
  return <div className="mt-4 rounded-xl border border-machinery/25 bg-machinery-soft/30 p-3 text-xs">
    <h3 className="font-semibold text-ink">Ask about {name}</h3>
    <p className="mt-0.5 text-ink-soft">Answers come only from what the atlas holds for this condition, with the sections they used. Not medical advice.</p>
    <form onSubmit={e => { e.preventDefault(); ask(question); }} className="mt-2 flex gap-1.5">
      <input value={question} onChange={e => setQuestion(e.target.value)} maxLength={500} placeholder="Your question" aria-label="Your question about this condition"
        className="min-w-0 flex-1 rounded-lg border border-ink-line bg-white px-2.5 py-1.5 outline-none focus:border-machinery" />
      <button disabled={state.status === "waiting"} className="rounded-lg bg-machinery px-3 py-1.5 font-semibold text-white hover:opacity-90">{state.status === "waiting" ? "…" : "Ask"}</button>
    </form>
    {state.status === "idle" && <div className="mt-2 flex flex-wrap gap-1.5">{EXAMPLES.map(q => <button key={q} onClick={() => ask(q)} className="rounded-full border border-ink-line bg-white px-2 py-0.5 text-[11px] text-ink-soft hover:border-machinery/40">{q}</button>)}</div>}
    {state.status === "waiting" && <p className="mt-2 text-ink-faint" aria-live="polite">Reading the atlas page…</p>}
    {state.status === "error" && <p className="mt-2 text-caution" aria-live="polite">{state.error}</p>}
    {state.status === "done" && <div className="mt-2 rounded-lg bg-white p-2.5" aria-live="polite">
      <p className="whitespace-pre-wrap leading-relaxed text-ink">{state.answer}</p>
      {!!state.sections?.length && <p className="mt-2 text-[10.5px] text-ink-faint">From: {state.sections.join(" · ")}</p>}
      <p className="mt-1 text-[10.5px] text-ink-faint">Written by an AI (GPT-6 Luna) from this page only. Check details in the sections above and with your care team.</p>
    </div>}
  </div>;
}
