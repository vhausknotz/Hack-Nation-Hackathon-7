"""A real hosted contribution: add missing eligibility evidence to SNAP25's registry.

Explicit operator steps: propose -> azure_mcp_operator drain -> review ->
azure_mcp_operator publish -> status. The HTTP gateway never invokes a model.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.azure_mcp_operator import Operator

RECEIPT = ROOT / 'data/campaigns/mcp-first-contribution.json'
CID = 'MONDO:0014590'
TASK = 'evidence:' + CID


def save(receipt):
    RECEIPT.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))


async def remote(command):
    operator = Operator()
    url = 'https://' + operator.host() + '/mcp'
    token = operator.credential.get_token('api://' + operator.config['apiAudience'] + '/.default').token
    async with httpx.AsyncClient(headers={'Authorization': 'Bearer ' + token}, timeout=55) as client:
        async with streamable_http_client(url, http_client=client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                async def call(name, args):
                    result = await session.call_tool(name, args)
                    if result.isError:
                        raise ValueError(result.content)
                    return json.loads(result.content[0].text)
                if command == 'status':
                    receipt = json.loads(RECEIPT.read_text())
                    result = await call('get_submission', {'submission_id': receipt['submission_id']})
                    receipt['cloud_state'] = result['state']
                    receipt['kernel_result'] = result.get('result')
                    if claim := result.get('current_claim'):
                        receipt['published_review_status'] = claim['review_status']
                    save(receipt)
                    return
                if RECEIPT.exists():
                    raise ValueError('Contribution already has a receipt; use status instead of resubmitting')
                await call('get_contribution_schema', {})
                await call('list_frontier', {'condition_id': CID})
                await call('claim_task', {'task_id': TASK})
                fetched = await call('fetch_source', {'task_id': TASK, 'provider': 'clinicaltrials', 'record_id': 'NCT01238250'})
                source = await call('get_source', {'source_id': fetched['source_id'], 'limit': 20000})
                if source['next_offset'] is not None:
                    raise ValueError('Read the complete record before proposing')
                text = source['text']
                eligibility = text[text.index('Eligibility:'):text.index('\nStudy population:')]
                quotes = ['RNU4-2; SNAP25; FOXP2; ITSN1',
                          text[text.index('Summary:'):text.index('\nDetailed description:')],
                          eligibility, 'Status: RECRUITING']
                evidence = [{'type': 'trial_record', 'source_id': fetched['source_id'], 'quote': quote,
                             'start': text.index(quote), 'end': text.index(quote)+len(quote),
                             **({'restriction': eligibility.removeprefix('Eligibility: ')} if quote == eligibility else {})}
                            for quote in quotes]
                result = await call('submit_claim', {'task_id': TASK,
                    'assertion': {'subject': CID, 'predicate': 'has_asset', 'object': 'NCT01238250',
                                  'qualifiers': {'asset_type': 'registry', 'status': 'RECRUITING'}},
                    'evidence': evidence, 'prompt': 'lead-eligibility-completion@1'})
                assert 'submission_id' in result, result
                save({'purpose': 'Complete missing eligibility evidence for the existing SNAP25 registry listing',
                      'endpoint': url, 'condition': CID, 'record': 'NCT01238250',
                      'source_id': fetched['source_id'], 'submission_id': result['submission_id'],
                      'cloud_state': 'queued', 'gateway_model_calls': 0})


def review():
    from agents.communities import load_conditions
    from agents.trials_import import verify_asset, VERIFY_ASSET_PROMPT, VERIFY_MODEL, MODEL_FAMILY
    from ledger import identity, sources
    from ledger.api import Ledger
    from atlas_mcp.cloud_store import CloudIntake
    receipt = json.loads(RECEIPT.read_text())
    result = CloudIntake(Operator().store()).submission(receipt['submission_id'], 'agent:mcp-lead-codex')
    if result['state'] != 'kernel_accepted':
        raise ValueError('Drain the kernel worker and resolve any rejection before reviewing')
    claim_id = result['result']['claim_id']
    ledger = Ledger()
    try:
        claim = json.loads(ledger.store.claim(claim_id)['body'])
        existing = ledger.store.reviews_for(claim_id)
        if existing:
            judgment = {'verdict': existing[-1]['verdict'], 'reason': existing[-1]['reason']}
        else:
            src = ledger.store.source(claim['evidence'][0]['source_id'])
            judgment = verify_asset(load_conditions()[CID], claim, sources.read_text(src))
            ledger.review(claim_id, judgment['verdict'], judgment['reason'], identity.load_or_create('agent:asset-verifier-sol'),
                          model_family=MODEL_FAMILY, model=VERIFY_MODEL, prompt=VERIFY_ASSET_PROMPT)
        receipt.update(claim_id=claim_id, review=judgment, review_status=ledger.claim_status(claim_id),
                       log_verified=ledger.verify_log()['ok'], ledger_tree_head=ledger.publish_tree_head())
        save(receipt)
    finally:
        ledger.store.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('propose', 'review', 'status'))
    args = parser.parse_args()
    review() if args.command == 'review' else asyncio.run(remote(args.command))
