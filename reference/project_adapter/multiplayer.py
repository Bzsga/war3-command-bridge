"""Controlled two-client proof; fixed owned-window messages, no global input."""
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import zlib

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
runtime=HERE/'native-runtime'
if not runtime.is_dir():runtime=HERE.parents[1]/'runtime'
sys.path.insert(0,str(runtime))
import bridge
import launch as project_launch
from owned_bootstrap import OwnedBootstrap,read_complete
from owned_network import udp_ports,replay_destination
from lan_startup_guard import startup_lease,local_products,require_no_products
from desktop_probe import probe,require_lan_desktop
from lan_discovery import LocalDiscovery


def gameplay(clients,owners,report,check,persist):
    from concurrent.futures import ThreadPoolExecutor
    import uuid
    batch='mp-'+uuid.uuid4().hex[:8];report['gameplay_trace']=[]
    def request(i,op,args=None,rid=None):
        r,ms=clients[i].request(op,args,request_id=rid)
        report['gameplay_trace'].append({'seat':i+1,'op':op,'args':args,'id':r['id'],'response':r,'ms':ms})
        return r
    def snapshots():return [request(i,'snapshot')['result'] for i in (0,1)]
    def wait(predicate,seconds=12):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            state=snapshots()
            if any(s['fault'] for s in state):raise AssertionError('Formal runtime fault')
            if predicate(state):persist();return state
            time.sleep(.2)
        raise TimeoutError('Dual state wait failed: '+json.dumps([{'seat':s['localSeat'],'page':s['page'],'running':s['running'],'flow':[p['flow'] for p in s['players'][:2]]} for s in state]))
    def actions(controls,tag):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(request,i,'activate',{'control':c},batch+'-'+tag+'-'+str(i)) for i,c in enumerate(controls)]
            replies=[f.result() for f in futures]
        check(all(r['result']['dispatched'] for r in replies),'Both '+tag+' controls dispatched through formal sync entry')
    def same(states):return states[0]['players']==states[1]['players']
    state=snapshots()
    check(all(not s['running'] and s['normalClears']==0 for s in state),'Fresh two-player first battle start')
    actions([220,221],'starter-pick');wait(lambda ss:all(104 in s['controls'] for s in ss))
    actions([104,104],'starter-confirm');state=wait(lambda ss:all(all(p['speciesMode']==0 for p in s['players'][:2]) for s in ss) and same(ss))
    check(state[0]['players'][0]['kind']!=state[0]['players'][1]['kind'],'Independent starter selections agree on both clients')
    actions([81,81],'initial-reward-pick');wait(lambda ss:all(104 in s['controls'] for s in ss))
    actions([104,104],'initial-reward-confirm');state=wait(lambda ss:all(all(p['flow']==0 for p in s['players'][:2]) for s in ss) and same(ss))
    check(True,'Concurrent initial reward settlement agrees on both clients')
    for i,s in enumerate(state):
        if s['page']!=2:request(i,'activate',{'control':115})
    wait(lambda ss:all(71 in s['controls'] for s in ss))
    check(request(0,'activate',{'control':71})['result']['dispatched'],'First player becomes ready')
    state=wait(lambda ss:all(s['players'][0]['ready'] for s in ss) and same(ss))
    check(all(not s['running'] and not s['players'][1]['ready'] for s in state),'One ready player cannot start shared battle')
    check(request(1,'activate',{'control':71})['result']['dispatched'],'Second player becomes ready')
    start=wait(lambda ss:all(s['running'] for s in ss) and same(ss))
    end=wait(lambda ss:all(not s['running'] and s['players'][0]['flow'] in (1,2) and s['players'][1]['flow'] in (1,2) for s in ss) and same(ss),180)
    check(all(s['ticks']>before['ticks'] for s,before in zip(end,start)),'Both real game timers advanced through natural battle')
    check(all(p['gold']>0 and p['rewardSerial']>start[0]['players'][i]['rewardSerial'] for i,p in enumerate(end[0]['players'][:2])),'Natural victory credits separate gold and reward instances consistently')
    before=end
    for i,s in enumerate(end):
        if not s['visible']:request(i,'activate',{'control':75})
    wait(lambda ss:all(81 in s['controls'] for s in ss))
    actions([81,81],'victory-reward-pick');wait(lambda ss:all(104 in s['controls'] for s in ss))
    actions([104,104],'victory-reward-confirm');settled=wait(lambda ss:all(all(p['flow']==7 for p in s['players'][:2]) for s in ss) and same(ss))
    check(all(s['players'][i]['gold']==before[0]['players'][i]['gold'] for s in settled for i in (0,1)),'Concurrent reward claims do not re-credit battle gold')
    seq=[s['commandSequence'] for s in settled]
    replay=[request(i,'activate',{'control':104},batch+'-victory-reward-confirm-'+str(i)) for i in (0,1)]
    after=wait(lambda ss:same(ss))
    check(all(r.get('replayed') for r in replay) and all(s['commandSequence']==n for s,n in zip(after,seq)),'Duplicate reward requests settle neither player twice')
    for i,s in enumerate(after):
        if s['page']!=2:request(i,'activate',{'control':115})
    wait(lambda ss:all(203 in s['controls'] for s in ss))
    actions([203,203],'camp-vote');camp=wait(lambda ss:all(all(p['flow']==3 for p in s['players'][:2]) for s in ss) and same(ss))
    check(True,'Both route votes enter formal first camp with matching player state')
    report['camp_snapshots']=camp
    # Camp settlement can precede the next local UI refresh. A refused
    # navigation was not dispatched; retry only that seat with a fresh view.
    for i in (0,1):
        for attempt in range(4):
            current=request(i,'snapshot')['result']
            if current['page']==4:break
            control=next((id for id in (173,174,172,175,176) if id in current['controls']),None)
            if control is not None:
                reply=request(i,'activate',{'control':control},batch+'-shop-open-'+str(i)+'-'+str(attempt))
                if reply['result']['dispatched']:break
            time.sleep(.15)
        else:raise AssertionError('Camp shop navigation not available for seat '+str(i+1))
    shop=wait(lambda ss:all(s['page']==4 for s in ss))
    check(True,'Both formal camp shops opened after actual local UI refresh')
    goods=[next(row for row in s['details']['shop'] if 0<row['goods']<10000 and row['sold']==0 and row['price']<=s['players'][i]['gold']) for i,s in enumerate(shop)]
    actions([186+row['slot'] for row in goods],'shop-pick');wait(lambda ss:all(195 in s['controls'] for s in ss))
    actions([195,195],'shop-buy')
    traded=wait(lambda ss:all(s['players'][i]['gold']==shop[i]['players'][i]['gold']-goods[i]['price'] for i,s in enumerate(ss)) and same(ss))
    check(all(s['details']['equipmentCount']==shop[i]['details']['equipmentCount']+1 and any(item['type'] and item['handle'] for item in s['details']['items']) for i,s in enumerate(traded)),'Concurrent affordable equipment purchases create actual native items and separate ledgers')
    seq=[s['commandSequence'] for s in traded]
    replays=[request(i,'activate',{'control':195},batch+'-shop-buy-'+str(i)) for i in (0,1)]
    repeat=wait(lambda ss:same(ss))
    check(all(r.get('replayed') for r in replays) and all(s['commandSequence']==n for s,n in zip(repeat,seq)) and all(s['players'][i]['gold']==traded[i]['players'][i]['gold'] and s['details']['items']==traded[i]['details']['items'] for i,s in enumerate(repeat)),'Duplicate concurrent purchase requests cannot charge or create items twice')
    for i,s in enumerate(repeat):
        request(i,'activate',{'control':179})
    wait(lambda ss:all(105 in s['controls'] for s in ss))
    owner,p=owners[1];(owner/'launcher.stop').write_text('stop',encoding='ascii');p.wait(timeout=12)
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        departed=request(0,'snapshot')['result']
        if not departed['players'][1]['active']:break
        time.sleep(.3)
    else:raise TimeoutError('Remaining client did not observe departure')
    check(departed['players'][0]['active'] and not departed['fault'],'Remaining client observes real departure and remains operational')
    check(request(0,'activate',{'control':105})['result']['dispatched'],'Remaining player can dispatch a formal camp choice after departure')
    deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        continued=request(0,'snapshot')['result']
        if continued['players'][0]['flow']!=3:break
        time.sleep(.2)
    else:raise TimeoutError('Remaining camp choice did not settle')
    check(not continued['fault'] and continued['players'][0]['active'],'Remaining player settles camp choice after real departure')
    report['departure_snapshot']=continued;persist()


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True)
    parser.add_argument('--map',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--case',choices=['startup','gameplay'],default='startup')
    parser.add_argument('--i-confirm-map-write',action='store_true')
    parser.add_argument('--i-confirm-game-launch',action='store_true')
    args=parser.parse_args()
    if not (args.i_confirm_map_write and args.i_confirm_game_launch):
        parser.error('Runtime map copy and owned game startup require both explicit authorization flags')
    session=json.loads(args.session.read_text(encoding='utf8'))
    folder=args.out.resolve();folder.mkdir(parents=True,exist_ok=False)
    session['folder']=str(folder)
    if session['expected_clients']!=2:raise RuntimeError('Two-human map required')
    testmap=args.map.resolve()
    receipt=json.loads(testmap.with_suffix('.w3x.report.json').read_text(encoding='utf8'))
    if not receipt.get('ok') or receipt['source_sha256']!=session['map_sha256']:
        raise RuntimeError('Candidate verification does not match prepared source')
    if hashlib.sha256(testmap.read_bytes()).hexdigest()!=receipt['output_sha256']:raise RuntimeError('Packaged map changed')
    if any((Path(session['ipc'])/('seat-'+str(i))/'hello.json').exists() for i in (1,2)):
        raise RuntimeError('Fresh multiplayer IPC required; previous handshake must not be reused')
    shared=bridge.shared_module(Path(session['shared_bridge']))
    require_lan_desktop(probe())
    environment=shared.doctor()
    if not environment['ok']:raise RuntimeError('Environment check failed')
    game=Path(environment['game_directory'])
    report={'passed':False,'checks':[],'clients':[],'cleanup':[]}
    owners=[];discovery=None
    def persist():bridge.save(folder/'dual-report.json',report)
    def check(value,label):
        if 'desync detected' in shared.lan_support.host_log(session):
            report['host_desync_observed']=True
            raise AssertionError('Real host checksum desync observed; player snapshots cannot establish synchronization')
        if not value:raise AssertionError(label)
        report['checks'].append(label);print('PASS',label,flush=True);persist()
    def layout(data):
        value=project_launch.metadata(data)
        for slot in value['slots']:
            if slot[5] in (0,1) and slot[3]==0:slot[2]=0
        value['scope']='Two humans, slots 0 and 1; other human slots closed'
        return value
    shared.lan_support.classic_metadata=layout
    original_config=shared.lan_support.configure
    def configure(*args):
        config=original_config(*args)
        hostfolder=Path(config['cwd']);raw=Path(session['runtime_map']).read_bytes()
        plugin=(shared.KKWE/'plugin/warcraft3/yd_size_limit.dll').read_bytes()
        if b'\x81\xfe\xff\xff\x7f\x00' not in plugin or 'storm.dll'.encode('utf-16le') not in plugin:raise RuntimeError('Unknown file view')
        def le(n):return ' '.join(str(x) for x in n.to_bytes(4,'little'))
        lines=(hostfolder/'map.cfg').read_text(encoding='ascii').splitlines()
        view=min(len(raw),0x7fffff)
        lines=[('map_size = '+le(view)) if x.startswith('map_size = ') else ('map_info = '+le(zlib.crc32(raw[:view])&0xffffffff)) if x.startswith('map_info = ') else x for x in lines]
        (hostfolder/'map.cfg').write_text('\n'.join(lines)+'\n',encoding='ascii')
        p=hostfolder/'ydhost.cfg';p.write_text(p.read_text(encoding='ascii').replace('bot_autostart = 1','bot_autostart = 2'),encoding='ascii')
        return config
    shared.lan_support.configure=configure
    try:
        with startup_lease(game):
            require_no_products(local_products())
            runtime_map=game/'Maps/Test'/('zjb-'+session['session'][:12]+'-pair.w3x')
            if runtime_map.exists():raise RuntimeError('Runtime map already exists')
            shutil.copy2(testmap,runtime_map)
            session.update(map=str(testmap),runtime_map=str(runtime_map),launch_map=str(runtime_map.relative_to(game)),environment=environment)
            bridge.save(folder/'session.json',session)
            discovery=LocalDiscovery(session)
            discovery.start_host(shared.lan_support.start_host,session,shared.ROOT,shared.KKWE,shared.run_checked)
            payload=(folder/'own-gameinfo.bin').read_bytes()
            for seat in (1,2):
                owner=Path(session['ipc'])/('pair-owner-'+str(seat));owner.mkdir(exist_ok=False)
                launchfolder=folder/('client-'+str(seat));launchfolder.mkdir(exist_ok=False)
                child=dict(session,folder=str(launchfolder),ipc=str(owner))
                child['session']=session['session'][:6]+str(seat).zfill(2)+session['session'][8:]
                with shared.lan_support.temporary_player_name(child):
                    cmd='"'+str(game/'war3.exe')+'" -window -kkwe "'+str(shared.KKWE)+'"'
                    argv=[str(shared.ROOT/'KkweLuaHost.exe'),str(shared.KKWE/'bin'),str(shared.ROOT/'src/kkwe_launcher.lua'),str(game),cmd,str(shared.KKWE/'plugin/warcraft3/yd_loader.dll'),str(owner)]
                    with (launchfolder/'owner.log').open('wb') as log:
                        process=subprocess.Popen(argv,cwd=game,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
                    owners.append((owner,process))
                    boot=OwnedBootstrap(owner,child['session'],lan_ready=lambda pid:bool(udp_ports(pid)))
                    deadline=time.monotonic()+45;last_send=0;ports=[]
                    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
                        sender.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
                        while time.monotonic()<deadline:
                            if process.poll() is not None:raise RuntimeError('Native owner exited before join')
                            boot.tick()
                            if boot.pid and time.monotonic()-last_send>.5:
                                ports=udp_ports(boot.pid)
                                report['pending_client']={'seat':seat,'pid':boot.pid,'udp_ports':ports,'sent':list(boot.sent)};persist()
                                prior_ports={p for c in report['clients'] for p in c['udp_ports']}
                                destination=replay_destination(ports,prior_ports)
                                report['pending_client']['replay_destination']=destination
                                for port in ports:sender.sendto(payload,(destination,port))
                                last_send=time.monotonic()
                            text=shared.lan_support.host_log(session)
                            if 'player [WB'+child['session'][:8]+'|' in text and text.count(' joined the game')>=seat:break
                            time.sleep(.1)
                        else:raise RuntimeError('Client '+str(seat)+' LAN join timed out')
                    report['clients'].append({'seat':seat,'pid':boot.pid,'udp_ports':ports,'owner':str(owner)})
                    check(True,'Client '+str(seat)+' joined owned host')
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                hellos=[read_complete(Path(session['ipc'])/('seat-'+str(i))/'hello.json') for i in (1,2)]
                if all(h and h.get('stage')=='ready' for h in hellos):break
                if any(p.poll() is not None for _,p in owners):raise RuntimeError('Client exited while loading')
                time.sleep(.2)
            else:raise RuntimeError('Two-client handshake timed out')
            check(all(h['session']==session['session'] and h['build']==session['build'] and h['localSeat']==i for i,h in zip((1,2),hellos)),'Both clients match session/build and distinct local seats')
            clients=[shared.Client(dict(session,ipc=str(Path(session['ipc'])/('seat-'+str(i))))) for i in (1,2)]
            snapshots=[c.request('snapshot')[0]['result'] for c in clients]
            report['snapshots']=snapshots
            check(all(len([p for p in s['players'] if p['active']])==2 for s in snapshots),'Both clients observe two active human players')
            if args.case=='gameplay':
                gameplay(clients,owners,report,check,persist)
            report['passed']=True
    except Exception as error:
        report['error']=str(error);print('FAIL',error,flush=True)
    finally:
        if discovery:discovery.close()
        for owner,process in owners:
            (owner/'launcher.stop').write_text('stop',encoding='ascii')
        for owner,process in owners:
            try:process.wait(timeout=12);report['cleanup'].append({'owner':str(owner),'closed':True,'exit_code':process.returncode})
            except subprocess.TimeoutExpired:report['cleanup'].append({'owner':str(owner),'closed':False})
        try:report['host_cleanup']=shared.lan_support.stop_host(session)
        except Exception as error:report['host_cleanup_error']=str(error)
        report['cleanup_ok']=all(x['closed'] for x in report['cleanup']) and 'host_cleanup_error' not in report
        report['passed']=report['passed'] and report['cleanup_ok']
        persist()
    print(json.dumps({k:v for k,v in report.items() if k not in ('snapshots','gameplay_trace','camp_snapshots','departure_snapshot','passive')},ensure_ascii=False),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
