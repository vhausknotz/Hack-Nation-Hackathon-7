"""Human expert review: a small web page on the MCP host where operator-vetted experts judge findings.

    GET  /expert          sign-in, the review queue (findings with their exact quotes and sources), past reviews
    GET  /expert/login    GitHub sign-in (reuses the atlas's GitHub app)
    POST /expert/review   one verdict with a reason; goes through the same signed intake as agent reviews
    GET  /expert/logout

Who counts as an expert is the owner's decision (tools/moderate.py expert-grant <github-login> --credential ...);
signing in alone grants nothing. Experts are enrolled as human contributors (human:expert-<login>), and the ledger
records their reviews as human reviews, which outrank model reviews (ledger/policy.py: human_reviewed).
The queue (live/expert-queue.json) is written by the engine: recent contributed findings without a human review.
"""
import hashlib
import html
import json
import re
import time

from azure.core.exceptions import ResourceNotFoundError

from .oauth import digest, slug

VERDICTS = {"supports": "Supported by the quote", "supports_with_qualification": "Supported, with a caveat",
            "does_not_support": "Not supported", "out_of_scope": "Out of scope (wrong condition or population)"}
COOKIE = "atlas_expert"


class ExpertDesk:
    def __init__(self, intake):
        self.intake, self.store = intake, intake.store

    def session(self, token):
        if not token or not token.startswith("exs_"):
            return None
        row = self.store.get("expertsession", digest(token))
        return row if row and row["expires"] > time.time() else None

    def grant(self, login):
        return self.store.get("expertgrant", login.lower())

    def actor(self, session):
        """The expert's contributor id, enrolling on first sign-in after the owner's grant. None if not granted."""
        grant = self.grant(session["login"])
        if not grant:
            return None
        principal = f"github|{session['github_id']}|expert"
        row = self.store.get("principal", principal)
        if row:
            return row["actor"]
        profile = self.intake.enroll(slug(session["login"], 40), model="human expert", family="human", principal=principal,
                                     allow_review=True, quota=200, display=grant.get("display") or session["login"],
                                     human={"credential": grant["credential"]})
        return profile["id"]

    def queue(self):
        try:
            return json.loads(self.store.container.download_blob("live/expert-queue.json").readall())
        except ResourceNotFoundError:
            return {"at": None, "claims": []}

    def csrf(self, token):
        return hashlib.sha256(("csrf|" + token).encode()).hexdigest()[:32]

    def review(self, actor, claim_id, condition_id, verdict, reason):
        if verdict not in VERDICTS or not re.fullmatch(r"claim:sha256:[0-9a-f]{64}", claim_id or ""):
            raise ValueError("Choose a verdict for a listed finding")
        if len((reason or "").strip()) < 10:
            raise ValueError("Give a short reason (one sentence) for your verdict")
        tid = "review:" + claim_id + ":human"
        self.intake.seed([{"id": tid, "condition_id": condition_id, "kind": "review", "claim_id": claim_id,
                           "title": "Expert review of a finding"}])
        task = self.store.get("task", tid)
        if task and task["state"] == "complete":
            # another expert completed this task; reviews of the same claim by more experts get their own task
            tid = f"review:{claim_id}:human:{actor.split(':')[-1]}"
            self.intake.seed([{"id": tid, "condition_id": condition_id, "kind": "review", "claim_id": claim_id, "title": "Expert review of a finding"}])
        self.intake.claim(tid, actor)
        return self.intake.enqueue(actor, tid, "review", {"claim_id": claim_id, "verdict": verdict, "reason": reason.strip()[:1500],
                                                         "prompt": "human expert review via /expert"})


def page(title, body, site_url):
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>
:root{{--ink:#0f172a;--soft:#475569;--faint:#94a3b8;--line:#e2e8f0;--wash:#f8fafc;--brand:#4f46e5}}
body{{font:15px/1.6 Inter,system-ui,sans-serif;max-width:860px;margin:0 auto;padding:28px 16px 60px;color:var(--ink);background:var(--wash)}}
h1{{font-size:28px;letter-spacing:-.02em;margin:.2em 0}} a{{color:var(--brand)}} .muted{{color:var(--soft)}} .faint{{color:var(--faint);font-size:13px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:14px 0}}
blockquote{{margin:10px 0;padding:8px 12px;border-left:3px solid var(--line);background:var(--wash);border-radius:6px}}
.tag{{display:inline-block;font-size:11px;font-weight:600;border-radius:99px;padding:2px 8px;background:#eef2ff;color:var(--brand)}}
button,.btn{{font:inherit;font-weight:600;border:0;border-radius:10px;padding:8px 14px;background:var(--brand);color:#fff;cursor:pointer;text-decoration:none;display:inline-block}}
select,textarea{{font:inherit;width:100%;box-sizing:border-box;border:1px solid var(--line);border-radius:8px;padding:8px;margin-top:6px}}
.ok{{background:#ecfdf5;border-color:#a7f3d0}} .err{{background:#fff1f2;border-color:#fecdd3}}</style></head>
<body><p class=faint><a href="{html.escape(site_url)}">Rare Disease Atlas</a> · expert review</p>{body}</body></html>"""


def add_routes(mcp, intake, oauth, site_url):
    from starlette.responses import HTMLResponse, RedirectResponse
    desk = ExpertDesk(intake)

    def render(title, body, status=200):
        return HTMLResponse(page(title, body, site_url), status_code=status, headers={"Cache-Control": "no-store"})

    @mcp.custom_route("/expert/login", methods=["GET"])
    async def login(request):
        import anyio
        try:
            return RedirectResponse(await anyio.to_thread.run_sync(oauth.expert_start), status_code=302)
        except ValueError as error:
            return render("Not available", f"<h1>Not available</h1><p>{html.escape(str(error))}</p>", 503)

    @mcp.custom_route("/expert/logout", methods=["GET"])
    async def logout(request):
        response = RedirectResponse("/expert", status_code=302)
        response.delete_cookie(COOKIE, path="/expert")
        return response

    @mcp.custom_route("/expert", methods=["GET"])
    async def home(request):
        import anyio
        token = request.cookies.get(COOKIE)
        session = await anyio.to_thread.run_sync(desk.session, token)
        intro = ("<h1>Expert review</h1><p class=muted>Clinicians, genetic counsellors and researchers can confirm or reject findings that AI agents "
                 "added to the atlas. Each finding shows the exact quote it rests on and a link to its source. Your verdict is signed, recorded "
                 "in the public evidence log as a human review, and outranks AI reviews.</p>")
        if not session:
            return render("Expert review", intro + "<p><a class=btn href='/expert/login'>Sign in with GitHub</a></p>"
                          "<p class=faint>Signing in does not make you an expert reviewer by itself: the atlas operator adds experts after "
                          "checking a professional profile (for example ORCID or an institution page).</p>")
        actor = await anyio.to_thread.run_sync(desk.actor, session)
        login = html.escape(session["login"])
        if not actor:
            return render("Expert review", intro + f"<div class=card><b>Signed in as {login}.</b> This GitHub account is not an atlas expert yet. "
                          "To become one, send your GitHub login and a link to your professional profile (ORCID or institution page) to the "
                          "atlas operator. <a href='/expert/logout'>Sign out</a></div>")
        notice = {"ok": "<div class='card ok'>Thank you. Your review is queued; it appears in the evidence log within a few minutes.</div>",
                  "err": f"<div class='card err'>{html.escape(request.query_params.get('msg', 'That did not work.'))}</div>"}.get(request.query_params.get("done", ""), "")
        queue = await anyio.to_thread.run_sync(desk.queue)
        csrf = desk.csrf(token)
        cards = []
        for c in queue.get("claims", [])[:40]:
            quotes = "".join(f"<blockquote>“{html.escape(q)}”</blockquote>" for q in c["quotes"][:3])
            ai = f"<p class=faint>AI review so far: {html.escape(c['status'])}{(' — ' + html.escape(c['ai_reason'][:300])) if c.get('ai_reason') else ''}</p>"
            options = "".join(f"<option value='{v}'>{html.escape(t)}</option>" for v, t in VERDICTS.items())
            cards.append(f"""<div class=card><span class=tag>{html.escape(c['kind'])}</span>
<h3 style="margin:.4em 0">{html.escape(c['label'])} <span class=muted style="font-weight:400">for</span> <a href="{html.escape(site_url)}/c/{html.escape(c['condition_id'])}">{html.escape(c['condition'])}</a></h3>
<p class=faint>Submitted by {html.escape(c['contributor'])} · {html.escape((c.get('at') or '')[:10])} · <a href="{html.escape(c['source_url'])}" target=_blank rel=noreferrer>source ↗</a></p>
{quotes}{ai}
<form method=post action="/expert/review"><input type=hidden name=csrf value="{csrf}"><input type=hidden name=claim_id value="{html.escape(c['claim_id'])}">
<input type=hidden name=condition_id value="{html.escape(c['condition_id'])}"><select name=verdict required><option value="">Your verdict…</option>{options}</select>
<textarea name=reason rows=2 required minlength=10 placeholder="One sentence: why (e.g. the quote describes a different variant class)"></textarea>
<p><button>Record my review</button></p></form></div>""")
        body = (intro + f"<p class=faint>Signed in as <b>{login}</b> (expert) · <a href='/expert/logout'>sign out</a></p>" + notice
                + (f"<h2>{len(cards)} findings without a human review</h2>" + "".join(cards) if cards else "<div class=card>Nothing waiting right now.</div>"))
        return render("Expert review", body)

    @mcp.custom_route("/expert/review", methods=["POST"])
    async def review(request):
        import anyio
        token = request.cookies.get(COOKIE)
        session = await anyio.to_thread.run_sync(desk.session, token)
        form = await request.form()
        if not session or form.get("csrf") != desk.csrf(token):
            return RedirectResponse("/expert", status_code=303)
        actor = await anyio.to_thread.run_sync(desk.actor, session)
        if not actor:
            return RedirectResponse("/expert", status_code=303)
        try:
            await anyio.to_thread.run_sync(desk.review, actor, form.get("claim_id"), form.get("condition_id"), form.get("verdict"), form.get("reason"))
        except ValueError as error:
            from urllib.parse import quote
            return RedirectResponse("/expert?done=err&msg=" + quote(str(error)[:200]), status_code=303)
        return RedirectResponse("/expert?done=ok", status_code=303)
