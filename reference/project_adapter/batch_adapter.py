"""Reward -> real camp trade -> prepared evolution inheritance in one game."""
import json
from pathlib import Path
import time
from bridge import shared_module
from smoke import _run as natural_smoke

BOUNDARY='Live project logic. Reward and camp entry follow natural first battle; camp wallet=500 and evolution-node/life/status setup are explicit test fixtures. No intermediate battle completion or multiplayer/visual proof.'

class Context:
    def __init__(self,session_path,report,persist,client=None):
        self.path=session_path;self.session=json.loads(session_path.read_text(encoding='utf8'))
        from session_lifecycle import require_attachable
        require_attachable(self.session)
        self.report=report;self.persist=persist;self.counter=0
        self.client=client or shared_module(Path(self.session['shared_bridge'])).Client(self.session)
        self.acquired=None
        self.condition_probe=None
        if self.session.get('required_condition')=='minimized':
            from background_probe import BackgroundProbe
            launch=json.loads((Path(self.session['folder'])/'launch.json').read_text(encoding='utf8'))
            if not launch.get('process_identity_verified'):raise RuntimeError('Cannot minimize an unverified game identity')
            pid=launch['game_identity']['pid'];finder=BackgroundProbe(pid)
            try:
                owner=Path(self.session['ipc']);request_id=self.report['batch']+'-minimize'
                (owner/'window.minimize').write_text(request_id,encoding='ascii')
                deadline=time.monotonic()+5
                while True:
                    reply=owner/'window-minimize-result.json'
                    receipt=json.loads(reply.read_text()) if reply.exists() else None
                    if receipt and receipt.get('id')==request_id:
                        if not receipt.get('ok') or receipt.get('pid')!=pid:raise RuntimeError('Native owner rejected minimize: '+json.dumps(receipt))
                        if finder.samples[-1]['minimized'] and not finder.samples[-1]['game_foreground']:break
                    if time.monotonic()>=deadline:raise RuntimeError('Owned game did not enter minimized/nonforeground condition')
                    time.sleep(.05)
            finally:finder.finish()
            self.condition_probe=BackgroundProbe(pid)
    def request(self,op,args=None,rid=None):
        self.counter+=1;rid=rid or self.report['batch']+'-'+str(self.counter)
        response,elapsed=self.client.request(op,args,request_id=rid)
        self.report['trace'].append({'op':op,'args':args,'id':rid,'elapsed_ms':elapsed,'response':response});self.persist()
        if not response['ok']:raise AssertionError(response)
        return response
    def snapshot(self):return self.request('snapshot')['result']
    def check(self,value,label):
        if not value:raise AssertionError(label)
        self.report['checks'].append(label);self.persist();print('PASS '+label,flush=True)
    def activate(self,control,rid=None):
        result=self.request('activate',{'control':control},rid)['result'];self.check(result['dispatched'],'control '+str(control)+' dispatched');return result
    def wait(self,predicate,seconds=8):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            state=self.snapshot()
            if state['fault']:raise AssertionError('project runtime fault')
            if predicate(state):return state
            time.sleep(.15)
        raise TimeoutError('Expected state not reached: '+json.dumps(state))
    def prepare(self,name):
        state=self.snapshot();r=self.request('prepare',{'scene':name,'expected_serial':state['sceneSerial']})
        self.check(r['result']['dispatched'],'prepared '+name);return self.snapshot()
    def page(self,page):
        state=self.snapshot()
        if not state['visible']:self.activate(75);state=self.snapshot()
        if state['page']==page:return state
        choices={1:[116,113,119,128],2:[115,112,118,123,127],4:[174,173,172,175,176]}
        control=next((i for i in choices[page] if i in state['controls']),None)
        if control is None:raise AssertionError('no page navigation control to '+str(page))
        self.activate(control);return self.wait(lambda s:s['page']==page)
    def finish(self):
        conditions={'bounded_cases':True,'global_reset_used':False,'startups':1}
        if self.condition_probe:
            observation=self.condition_probe.finish()
            target=Path(self.session['folder'])/(self.report['batch']+'-minimized.json')
            target.write_text(json.dumps(observation,indent=2),encoding='utf8')
            summary={k:v for k,v in observation.items() if k!='samples'}
            self.report['condition_evidence']=str(target);self.persist()
            valid=observation['sample_count']>1 and observation['minimized_samples']==observation['sample_count'] and not any(observation[k] for k in ['foreground_samples','unknown_foreground_samples','missing_window_samples','errors'])
            conditions['minimized']=summary
            if not valid:raise AssertionError('Minimized condition was not maintained; business evidence retained separately')
        return conditions

def open_context(path,report,persist):return Context(path,report,persist)
def shutdown(path):
    from session_lifecycle import cleanup_owned
    s=json.loads(path.read_text(encoding='utf8'));return cleanup_owned(s,shared_module(Path(s['shared_bridge'])).shutdown)

def reward(ctx):
    state=ctx.snapshot()
    if state['normalClears']==0:
        existing=set(Path(ctx.session['folder']).glob('smoke-*.json'))
        ctx.check(natural_smoke(ctx.path),'natural first battle prerequisite')
        ctx.report.setdefault('prerequisite_reports',[]).extend(str(p.resolve()) for p in sorted(set(Path(ctx.session['folder']).glob('smoke-*.json'))-existing));ctx.persist()
        state=ctx.snapshot()
    ctx.check(state['normalClears']==1 and state['players'][0]['flow']==1,'reward scene starts after real victory')
    ctx.page(1);before=ctx.snapshot();ctx.activate(81)
    rid=ctx.report['batch']+'-reward-claim';ctx.activate(104,rid)
    after=ctx.wait(lambda s:s['players'][0]['rewardSerial']>before['players'][0]['rewardSerial'])
    ctx.check(after['details']['bondCount']==before['details']['bondCount']+1,'reward adds one actual bond')
    ctx.check(after['players'][0]['gold']==before['players'][0]['gold'],'claim does not re-credit battle gold')
    seq=after['commandSequence'];r=ctx.request('activate',{'control':104},rid);after=ctx.snapshot()
    ctx.check(r['replayed'] and after['commandSequence']==seq,'duplicate reward request neither re-sends nor re-settles')
    ctx.page(2);ctx.activate(203);state=ctx.wait(lambda s:s['players'][0]['flow']==3)
    ctx.check(state['details']['camp']==1,'normal route vote enters real first camp')

def trade(ctx):
    ctx.prepare('camp_trade');state=ctx.page(4)
    row=None
    for refresh in range(4):
        row=next((r for r in state['details']['shop'] if 0<r['goods']<10000 and r['sold']==0 and r['price']<=state['players'][0]['gold']),None)
        if row is not None:break
        if refresh==3:break
        old=state['players'][0]['gold'];ctx.activate(196)
        state=ctx.wait(lambda s:s['players'][0]['gold']<old)
        ctx.check(state['players'][0]['gold']>=0,'bounded normal shop refresh pays without overdraft')
    if row is None:raise AssertionError('no affordable real equipment stock: '+json.dumps(state['details']['shop']))
    before=state;ctx.activate(186+row['slot']);rid=ctx.report['batch']+'-trade-buy';ctx.activate(195,rid)
    after=ctx.wait(lambda s:s['players'][0]['gold']==before['players'][0]['gold']-row['price'])
    ctx.check(after['details']['equipmentCount']==before['details']['equipmentCount']+1,'purchase ledger increases once')
    old={i['handle'] for i in before['details']['items'] if i['handle']}
    item=next((i for i in after['details']['items'] if i['handle'] and i['handle'] not in old),None)
    ctx.check(item is not None,'real purchased item exists in native inventory');ctx.acquired=item
    seq=after['commandSequence'];r=ctx.request('activate',{'control':195},rid);end=ctx.snapshot()
    ctx.check(r['replayed'] and end['commandSequence']==seq and end['players'][0]['gold']==after['players'][0]['gold'],'duplicate purchase cannot charge twice')

def evolution(ctx):
    before=ctx.prepare('evolution_inheritance');ctx.check(before['players'][0]['flow']==4,'formal camp setup reaches prepared evolution node')
    ctx.check(ctx.acquired is not None and any(i['handle']==ctx.acquired['handle'] for i in before['details']['items']),'traded equipment reaches evolution fixture')
    ctx.page(1);ctx.activate(81);ctx.wait(lambda s:104 in s['controls']);rid=ctx.report['batch']+'-evolution';ctx.activate(104,rid)
    state=ctx.wait(lambda s:s['details']['evolutionCount']>before['details']['evolutionCount'] or s['players'][0]['speciesMode']==2)
    if state['players'][0]['speciesMode']==2:
        ctx.activate(81);ctx.wait(lambda s:104 in s['controls']);ctx.activate(104);state=ctx.wait(lambda s:s['details']['evolutionCount']>before['details']['evolutionCount'])
    a=before['details'];b=state['details']
    ctx.check(b['evolutionCount']==a['evolutionCount']+1 and state['players'][0]['unitType']!=before['players'][0]['unitType'],'A advances exactly one form')
    ctx.check(b['unitHandle']!=a['unitHandle'] and b['items']==a['items'],'replacement unit retains original native item handles and slots')
    ctx.check(state['players'][0]['life']==before['players'][0]['life'] and all(b[k]==a[k] for k in ('burn','mark','coreCD','skillCD')),'life statuses and cooldowns survive evolution')
    ctx.check(set(a['skills'])<=set(b['skills']) and state['players'][0]['gold']==before['players'][0]['gold'],'earned skills and wallet survive evolution')
    seq=state['commandSequence'];r=ctx.request('activate',{'control':104},rid);state=ctx.snapshot()
    ctx.check(r['replayed'] and state['commandSequence']==seq and state['details']['evolutionCount']==b['evolutionCount'],'duplicate evolution request cannot evolve twice')

CASES={'reward':reward,'camp_trade':trade,'evolution_inheritance':evolution}
