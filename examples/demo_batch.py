"""Minimal batch adapter for the bundled, single-player demo protocol.

Attach an already authorized session. Replace operations and assertions when
adapting another map; this file neither writes a map nor launches a game.
"""
import json
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'runtime'))
import war3_bridge
from session_lifecycle import require_attachable

BOUNDARY='Bundled single-player demo: natural attack/reward, request replay and reset; no visual or multiplayer proof.'


class Context:
    def __init__(self,session,report,persist):
        self.client=war3_bridge.Client(session)
        self.report=report
        self.persist=persist

    def request(self,op,args=None,request_id=None):
        reply,elapsed=self.client.request(op,args,request_id=request_id)
        self.report['trace'].append({'op':op,'id':reply['id'],'elapsed_ms':elapsed,'response':reply})
        self.persist()
        if not reply['ok']:raise AssertionError(reply.get('error','Command failed'))
        return reply

    def check(self,condition,label):
        if not condition:raise AssertionError(label)
        self.report['checks'].append(label)
        self.persist()

    def wait(self,predicate,timeout=15):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            state=self.request('snapshot')['result']
            if predicate(state):return state
            time.sleep(.15)
        raise TimeoutError('Expected demo state not reached; see the last trace')


def attack_reward(ctx):
    start=ctx.request('prepare')['result']
    ctx.check(start['actor']['exists'] and start['target']['exists'],'Demo units exist')
    request_id='attack-'+uuid.uuid4().hex[:12]
    reply=ctx.request('order',{'command':'attack'},request_id)
    ctx.check(reply['result']['order_accepted'],'Native attack order accepted')
    end=ctx.wait(lambda s:s['rewards']>start['rewards'])
    ctx.check(end['deaths']>start['deaths'] and end['gold']>start['gold'],'Real death settles a reward')
    replay=ctx.request('order',{'command':'attack'},request_id)
    current=ctx.request('snapshot')['result']
    ctx.check(replay['replayed'] and current['rewards']==end['rewards'] and current['gold']==end['gold'],'Same request does not reward twice')
    reset=ctx.request('reset')['result']
    ctx.check(reset['live_test_units']==0 and reset['active_death_triggers']==0,'Reset releases demo units and triggers')


CASES={'attack_reward':attack_reward}


def open_context(session_path,report,persist):
    session=json.loads(Path(session_path).read_text(encoding='utf8'))
    require_attachable(session)
    return Context(session,report,persist)


def shutdown(session_path):
    return war3_bridge.shutdown(json.loads(Path(session_path).read_text(encoding='utf8')))
