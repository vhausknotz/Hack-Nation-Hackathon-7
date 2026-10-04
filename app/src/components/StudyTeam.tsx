// Who runs a study, from its official ClinicalTrials.gov record: the route to an actual partner.
import type { StudyTeam } from "../lib/types";

export function StudyTeamCard({ team: t }: { team: StudyTeam }) {
  const lead = t.officials[0];
  if (!t.sponsor && !lead && !t.contacts.length) return null;
  return <div className="mt-3 rounded-lg bg-ink-wash/70 p-2.5 text-xs">
    <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-faint">Who runs it</div>
    {lead && <p className="mt-1"><b className="font-semibold text-ink">{lead.name}</b>{lead.affiliation ? `, ${lead.affiliation}` : ""} <span className="text-ink-faint">· {lead.role || "investigator"}</span></p>}
    {t.officials.slice(1, 3).map(o => <p key={o.name} className="text-ink-soft">{o.name}{o.affiliation ? `, ${o.affiliation}` : ""}</p>)}
    {t.sponsor && <p className="mt-1">Sponsor: {t.sponsor}{t.collaborators.length ? ` · with ${t.collaborators.slice(0, 3).join(", ")}` : ""}</p>}
    {t.contacts.filter(c => c.email).slice(0, 2).map(c => <p key={c.email!} className="mt-1">Study contact: {c.name ? `${c.name} · ` : ""}<a className="text-machinery underline" href={`mailto:${c.email}`}>{c.email}</a></p>)}
    {t.sites > 0 && <p className="mt-1 text-ink-soft">{t.sites} site{t.sites === 1 ? "" : "s"}{t.countries.length ? ` in ${t.countries.slice(0, 4).join(", ")}${t.countries.length > 4 ? " and more" : ""}` : ""}</p>}
    <p className="mt-1.5 text-[10.5px] text-ink-faint">Public contacts from the official ClinicalTrials.gov record{t.updated ? `, updated ${t.updated}` : ""}. Write to the study team, not to individual patients' doctors.</p>
  </div>;
}


/** The person to address and how, for a focused question. */
export function teamAddress(t?: StudyTeam) {
  if (!t) return null;
  const lead = t.officials[0];
  const contact = t.contacts.find(c => c.email);
  if (!lead && !contact) return null;
  return {
    greeting: lead ? `Dear ${/,\s*(MD|M\.D\.|PhD|Ph\.D\.|DPhil|MBBS)\b/i.test(lead.name) ? "Dr. " : ""}${lead.name.split(",")[0]}` : "Dear study team",
    to: [lead ? `${lead.name}${lead.affiliation ? `, ${lead.affiliation}` : ""} (${lead.role || "investigator"})` : null,
         contact ? `Study contact: ${contact.name ? contact.name + " " : ""}<${contact.email}>` : null].filter(Boolean).join("\n"),
    email: contact?.email ?? null,
  };
}
