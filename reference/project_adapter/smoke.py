"""Live bridge smoke: normal starter/reward controls, prepare, natural first fight.

No forced victory, resource grants, UI automation, or chapter skip.
"""
import argparse
import json
from pathlib import Path
import time
import uuid
from bridge import shared_module,save

def _run(session_path,require_background=False):
    session=json.loads(session_path.read_text(encoding='utf8'))
    client=shared_module(Path(session['shared_bridge'])).Client(session)
    folder=Path(session['folder']);batch='smoke-'+uuid.uuid4().hex[:8]
    report={'passed':False,'batch':batch,'checks':[],'trace':[],
            'boundary':'Live single-client game via timer and existing UI/sync commands; no visual or multiplayer acceptance'}
    from background_probe import BackgroundProbe
    launch=json.loads((folder/'launch.json').read_text(encoding='utf8'))
    probe=BackgroundProbe(launch['game_identity']['pid'])
    number=0
    def request(op,args=None,rid=None):
        nonlocal number
        number+=1
        r,elapsed=client.request(op,args,request_id=rid or batch+'-'+str(number))
        report['trace'].append({'op':op,'args':args,'elapsed_ms':elapsed,'response':r})
        save(folder/(batch+'.json'),report)
        return r['result']
    def check(value,label):
        if not value:raise AssertionError(label)
        report['checks'].append(label);print('PASS '+label,flush=True)
    def activate(control):
        state=request('activate',{'control':control})
        check(state['dispatched'],'control '+str(control)+' dispatched')
    def wait(predicate,seconds=10):
        deadline=time.perf_counter()+seconds;last_update=0
        while time.perf_counter()<deadline:
            state=request('snapshot')
            if state['fault']:raise AssertionError('project runtime fault')
            if predicate(state):return state
            if time.perf_counter()-last_update>20:
                print('Waiting: '+json.dumps({'running':state['running'],'flow':state['players'][0]['flow'],'life':state['players'][0]['life'],'ticks':state['ticks']}),flush=True)
                last_update=time.perf_counter()
            time.sleep(.4)
        raise TimeoutError('Expected state not reached: '+json.dumps(state))
    try:
        state=request('snapshot');check(state['ready'] and state['singleHuman'] and not state['fault'],'project initialized in real game')
        check(state.get('normalClears',0)==0 and state['players'][0]['gold']==0 and not state['running'],'fresh start before first battle; automatic defaults have not advanced combat')
        if state['players'][0]['speciesMode']==1:
            activate(220);activate(104)
            state=wait(lambda s:s['players'][0]['speciesMode']==0)
        check(state['players'][0]['speciesMode']==0 and state['players'][0]['unitType']!=0,'starter committed')
        if state['players'][0]['flow']==1:
            activate(81);activate(104)
            state=wait(lambda s:s['players'][0]['flow']==0)
        check(state['players'][0]['flow']==0 and not state['running'],'starting reward settles into preparation')
        if state['page']!=2:
            control=next((id for id in (115,112,123,102,127) if id in state['controls']),None)
            if control is None:raise AssertionError('no visible route-page control')
            activate(control);state=wait(lambda s:s['page']==2)
        check(71 in state['controls'],'preparation offers challenge')
        activate(71);state=wait(lambda s:s['running'])
        check(state['chapter']==1 and state['encounter']==1,'normal prepare starts first encounter')
        battle_start=state
        state=wait(lambda s:not s['running'],seconds=180)
        check(state['ticks']>battle_start['ticks'],'game timers advanced during natural combat')
        check(state['players'][0]['flow']!=6 and state['outcome']!=2,'natural first battle survives')
        state=wait(lambda s:s['players'][0]['flow'] in (1,2),seconds=10)
        check(state['players'][0]['rewardSerial']>battle_start['players'][0]['rewardSerial'],'victory produces new reward instance')
        check(state['players'][0]['gold']>battle_start['players'][0]['gold'],'victory credits actual gold')
        report['passed']=True;report['final']=state
    except Exception as exc:
        report['error']=str(exc)
        print('FAIL '+str(exc),flush=True)
    report['background']=probe.finish()
    bg=report['background']
    report['background_passed']=not bg['foreground_samples'] and not bg['unknown_foreground_samples'] and not bg['missing_window_samples'] and not bg['errors']
    if require_background and not report['background_passed']:
        report['passed']=False;report['error']='Business result retained; background condition was not maintained throughout'
    save(folder/(batch+'.json'),report)
    print(json.dumps({'passed':report['passed'],'checks':len(report['checks']),'report':str(folder/(batch+'.json'))},ensure_ascii=False),flush=True)
    return report['passed']

def run(session_path,require_background=False,keep_open=False):
    try:
        return _run(session_path,require_background)
    finally:
        if not keep_open:
            session=json.loads(session_path.read_text(encoding='utf8'))
            shared_module(Path(session['shared_bridge'])).shutdown(session)
            print('Owned War3 and LAN host closed; shutdown receipt saved',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--session',type=Path,required=True)
    parser.add_argument('--require-background',action='store_true')
    parser.add_argument('--keep-open',action='store_true',help='Only when explicitly asked to retain this test session for viewing')
    args=parser.parse_args()
    raise SystemExit(0 if run(args.session,args.require_background,args.keep_open) else 1)
