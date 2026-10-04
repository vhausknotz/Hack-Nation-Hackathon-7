"""Explicit, resumable import of the staged coverage-v1 package with Sol review.

One ledger writer, no discovery search, at most one kind/scope correction per
candidate. The proposing Claude agent does not count as an independent reviewer.
"""
import json
from copy import deepcopy

from agents import communities as scout
from ledger import identity, sources
from ledger.api import Ledger, now
from .stage import ARCHIVE, PACKAGE, CONTRIBUTOR, ROOT, verify


def main():
    problems = verify()
    if problems:
        raise ValueError(problems)
    manifest = json.loads((PACKAGE/'manifest.json').read_text(encoding='utf-8'))
    candidates = [json.loads(line) for line in (PACKAGE/'candidates.jsonl').read_text(encoding='utf-8').splitlines()]
    conditions = scout.load_conditions()
    path = ROOT/'data/campaigns/community-coverage-v1.json'
    receipt = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
        'campaign': 'community-coverage-v1', 'started': now(), 'candidates': {}, 'errors': {}}
    ledger = Ledger()
    try:
        proposer = ledger.register(identity.load_or_create(CONTRIBUTOR), 'agent', {
            'role': 'community researcher', 'model_family': 'anthropic-claude',
            'model': candidates[0]['claim']['provenance_proposal']['model'],
            'prompt': 'community-coverage-v1', 'source': 'external agent package f382cf4'})
        reviewer = identity.load_or_create('agent:community-verifier-sol')
        for entry in manifest['sources'].values():
            src = entry['source']
            copied = sources.archive(sources.read_raw(src, ARCHIVE), src['url'], src['media_type'], src['license'], src['redistributable'])
            if copied.source_id != src['source_id'] or copied.raw_hash != src['raw_hash']:
                raise ValueError('Raw archive does not reproduce declared canonical source')
            ledger.add_source(sources.Source(**src), proposer)
        for candidate in candidates:
            key = candidate['candidate_id']
            if key in receipt['candidates']:
                continue
            try:
                staged = candidate['claim']
                claim = {'assertion': deepcopy(staged['assertion']),
                         'evidence': [{k: v for k, v in e.items() if k != 'supports'} for e in staged['evidence']],
                         'provenance': {**staged['provenance_proposal'], 'created': now(), 'prompt': 'community-coverage-v1'}}
                attempts = []
                for attempt in range(2):
                    claim = scout.reuse_claim(ledger, claim)
                    proposal = ledger.propose(claim, proposer)
                    if not proposal.accepted:
                        raise ValueError(proposal.checks)
                    quotes = '\n\n[Separate verbatim excerpt]\n\n'.join(e['quote'] for e in claim['evidence'])
                    src = ledger.store.source(claim['evidence'][0]['source_id'])
                    judgment = scout.verify_community(conditions[claim['assertion']['subject']], claim['assertion']['qualifiers'],
                                                       src['title'], quotes, sources.read_text(src))
                    prior = ledger.store.db.execute("SELECT 1 FROM events WHERE type='review.attested' AND target=? AND json_extract(payload,'$.prompt')=?",
                                                    (proposal.claim_id, scout.VERIFY_PROMPT)).fetchone()
                    if not prior:
                        ledger.review(proposal.claim_id, judgment['verdict'], judgment['reason'], reviewer,
                                      model_family=scout.MODEL_FAMILY, model=scout.VERIFY_MODEL, prompt=scout.VERIFY_PROMPT)
                    attempts.append({'claim_id': proposal.claim_id, 'judgment': judgment, 'status': ledger.claim_status(proposal.claim_id)})
                    q = claim['assertion']['qualifiers']
                    if attempt or not judgment['serves'] or not judgment['org_type'] or not judgment['scope'] or (
                            q['org_type'] == judgment['org_type'] and q['scope'] == judgment['scope']):
                        break
                    claim = deepcopy(claim)
                    claim['assertion']['qualifiers'].update(org_type=judgment['org_type'], scope=judgment['scope'])
                    claim['provenance'].update(created=now(), corrected_after_review=True)
                receipt['candidates'][key] = {'attempts': attempts, 'caveats': candidate['caveats']}
                receipt['errors'].pop(key, None)
                print(key, attempts[-1]['status'], flush=True)
            except Exception as error:
                receipt['errors'][key] = str(error)[:1200]
                print(key, 'ERROR', type(error).__name__, flush=True)
            scout.save_receipt(path, receipt)
        receipt.update(finished=now(), ledger_tree_head=ledger.publish_tree_head(), log_verified=ledger.verify_log()['ok'])
        scout.save_receipt(path, receipt)
        print(json.dumps({'completed': len(receipt['candidates']), 'errors': receipt['errors'], 'log_verified': receipt['log_verified']}))
        if receipt['errors']:
            raise SystemExit(1)
    finally:
        ledger.store.close()


if __name__ == '__main__':
    main()
