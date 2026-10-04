// The 10x case: the milestone we aim to accelerate, the route today versus with the atlas, the assumptions,
// and how to measure it. No result is claimed that has not been measured.
import { Link } from "react-router-dom";
import { Section } from "../components/ui";
import { routes } from "../lib/links";

const TODAY = [
  ["Find others with the diagnosis", "Search engines return dense papers or nothing. A tiny community may not know any other family or researcher."],
  ["Find out what research already exists", "Registries, natural-history studies and outcome measures sit in separate databases, often filed under other disease names."],
  ["Judge whether it applies", "Eligibility, gene effect, symptoms and inheritance have to be compared by hand, usually by asking busy experts."],
  ["Find who runs it and how to reach them", "Cold emails and conference networking."],
  ["Prepare a proposal", "Collect sources, restrictions and the right questions from scratch."],
] as const;

const ATLAS = [
  ["Search the diagnosis", "Related conditions appear with why they are connected, what is shared and what differs.", routes.condition("MONDO:0012812")],
  ["See existing studies and groups", "Reviewed listings with eligibility restrictions, source dates and registry status rechecks.", routes.condition("MONDO:0012812")],
  ["See who runs them", "Named investigators, sponsors and public study contacts from the official record.", routes.condition("MONDO:0012812")],
  ["Get a sourced proposal draft", "Who to approach, what to ask, why the communities connect, what must be checked first, and every source.", `${routes.condition("MONDO:0012812")}?brief=1`],
  ["Fill the gaps", "If the condition is nearly empty, point an AI agent at it; findings are quote-checked and reviewed before they appear.", "/agents"],
] as const;

const ASSUMPTIONS = [
  ["Finding and preparing is a large share of the time before a first study conversation.", "Organizers report that most early time goes to other parts of the path (funding, legal, clinical access)."],
  ["An existing study can expand (protocol amendment) faster than a new study can start.", "Study teams decline, or amendments take as long as new protocols."],
  ["Conditions connected by shared signs and machinery can use similar outcome measures.", "Experts judge the measures unsuitable for most connected pairs."],
  ["Agents can keep thin conditions growing so a first search is rarely empty.", "Reviewed findings stay scarce for most conditions despite steady agent work."],
] as const;

export default function Impact() {
  return (
    <div className="max-w-3xl pb-12">
      <header className="pt-12">
        <div className="eyebrow">The 10× case</div>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight">From an isolated diagnosis to a shared study</h1>
        <p className="mt-4 text-lg leading-relaxed text-ink-soft">
          Almost every rare-disease trial needs a natural-history study first. For a tiny community, building one from scratch can take years. Joining or adapting a study that already exists for a related condition could be much faster, if the community can find it, judge whether it fits, and reach the people who run it.
        </p>
        <p className="mt-3 rounded-xl bg-caution-soft/50 p-3 text-sm text-caution">
          We have not measured a 10× acceleration. This page states the milestone, the route, the assumptions and how to test them.
        </p>
      </header>

      <Section title="The milestone" intro="A treatment-relevant step we can observe and time.">
        <p className="text-[15px] leading-relaxed text-ink-soft">
          <b className="text-ink">An expert-reviewed decision on whether an existing natural-history protocol or outcome measure can serve another community's study</b>, and if yes, that community's first participants enrolled through an amendment rather than a new study. Finding a shared record is only the beginning: compatibility, consent, data sharing and governance remain separate gates.
        </p>
      </Section>

      <Section title="The route: today versus with the atlas">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-ink-faint">Today</h3>
            <ol className="mt-3 space-y-3">
              {TODAY.map(([t, d], i) => (
                <li key={t} className="rounded-xl border border-ink-line bg-white p-3 text-sm"><b className="text-ink">{i + 1}. {t}</b><p className="mt-1 text-ink-soft">{d}</p></li>
              ))}
            </ol>
          </div>
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-machinery">With the atlas</h3>
            <ol className="mt-3 space-y-3">
              {ATLAS.map(([t, d, to], i) => (
                <li key={t}><Link to={to} className="block rounded-xl border border-machinery/30 bg-machinery-soft/30 p-3 text-sm transition hover:border-machinery/60"><b className="text-ink">{i + 1}. {t} →</b><p className="mt-1 text-ink-soft">{d}</p></Link></li>
              ))}
            </ol>
          </div>
        </div>
        <p className="mt-4 text-sm text-ink-soft">
          Try the real example: <Link className="text-machinery underline" to={`${routes.condition("MONDO:0012812")}?brief=1`}>STXBP1's partnership proposal draft</Link> for a natural-history study that already includes SYNGAP1, with its investigator, sponsor, contacts, restrictions and sources.
        </p>
      </Section>

      <Section title="The assumptions behind 10×" intro="Each one can be wrong; here is what would show it.">
        <div className="space-y-3">
          {ASSUMPTIONS.map(([a, wrong]) => (
            <div key={a} className="rounded-xl border border-ink-line bg-white p-3 text-sm">
              <p className="text-ink"><b>Assumption:</b> {a}</p>
              <p className="mt-1 text-ink-soft"><b>It would be wrong if:</b> {wrong}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="How to measure it">
        <ol className="list-decimal space-y-2 pl-5 text-[15px] leading-relaxed text-ink-soft">
          <li>Give matched patient-group and research teams the same diagnoses and a fixed brief rubric, with and without the atlas, in counterbalanced order.</li>
          <li>Record staff time to identify relevant existing studies, their responsible teams, exact evidence, restrictions and open questions, including time spent correcting the atlas.</li>
          <li>Have blinded experts score the briefs for relevance, source fidelity, missed restrictions and unsupported reuse claims. A faster but worse brief does not count.</li>
          <li>Report baseline hours divided by atlas-assisted hours, with quality and variation across cases. Ten is the target to test.</li>
          <li>Follow whether study teams confirm a reusable element and whether an amendment replaces a new protocol. Report this separately: discovery speed alone does not prove faster treatment development.</li>
        </ol>
      </Section>
    </div>
  );
}
