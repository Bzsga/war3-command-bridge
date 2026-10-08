"""Source-only kit checks; no maps, game startup, registry writes, or UI input."""
import ast
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import zlib

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime'))
from file_view import apply_file_view
import war3_bridge as bridge

def main():
    checks=[]
    def check(value,label):
        if not value:raise AssertionError(label)
        checks.append(label)
    for p in ROOT.rglob('*.py'):ast.parse(p.read_text(encoding='utf8'))
    check(True,'all Python sources parse')
    check((ROOT/'runtime/config.example.json').is_file(),'configuration entry exists')
    required=['war3_bridge.py','lan_support.py','background_probe.py','file_view.py','src/lan_host.py','src/KkweLuaHost.cs','src/kkwe_launcher.lua','src/map_hash.lua','src/read_w3i.lua','src/pack_demo.lua','src/map.j.template','src/bridge.lua','src/json.lua','desktop_probe.py','lan_startup_guard.py','lan_discovery.py','session_lifecycle.py','startup_diagnostics.py','owned_bootstrap.py','owned_network.py']
    check(all((ROOT/'runtime'/name).is_file() for name in required),'all runtime startup, host and protocol source dependencies included')
    forbidden={'.w3x','.w3m','.dll','.exe','.sqlite','.ogg','.mp3','.fbx','.mdx'}
    check(not any(p.suffix.lower() in forbidden for p in ROOT.rglob('*') if p.is_file()),'source-only handoff has no maps, binaries or game assets')
    with tempfile.TemporaryDirectory(prefix='war3-kit-check-') as scratch:
        base=Path(scratch);kkwe=base/'kkwe';plugin=kkwe/'plugin/warcraft3/yd_size_limit.dll';plugin.parent.mkdir(parents=True)
        plugin.write_bytes(b'\x81\xfe\xff\xff\x7f\x00'+'storm.dll'.encode('utf-16le'))
        for size,label in [(32,'small'),(0x7fffff+32,'large')]:
            raw=(b'abcd'*((size+3)//4))[:size];path=base/'map-input.bin';path.write_bytes(raw)
            config_path=base/'map.cfg';original='map_size = native\nmap_info = native\nmap_crc = unchanged\nmap_sha1 = unchanged\n'
            config_path.write_text(original,encoding='ascii')
            words=[len(raw),zlib.crc32(raw)&0xffffffff,1234,1,2,3,4,5]
            config={'cwd':str(base),'hash_words':words.copy()};session={'runtime_map':str(path)}
            result=apply_file_view(session,config,kkwe,'kkwe_8m');view=result['client_file_view']
            expected=raw if label=='small' else raw[:0x7fffff]
            check(view['reported_bytes']==len(expected) and view['reported_info']==zlib.crc32(expected)&0xffffffff,label+' file view matches independently bounded input')
            check(path.read_bytes()==raw and words==result['hash_words'] and 'map_crc = unchanged\nmap_sha1 = unchanged' in config_path.read_text(),label+' map bytes and logical hashes preserved')
            check((base/'map.native.cfg').read_text()==original,label+' original host fields retained')
        plugin.write_bytes(b'unknown plugin')
        try:apply_file_view(session,config,kkwe,'kkwe_8m')
        except ValueError:check(True,'unknown plugin rejected')
        else:raise AssertionError('unknown plugin accepted')
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            for command in ('build-demo','launch'):
                with patch.object(sys,'argv',['war3_bridge.py',command]),patch.object(bridge,'build_demo') as build,patch.object(bridge,'launch') as launch:
                    try:bridge.main()
                    except SystemExit as exc:check(exc.code==2 and not build.called and not launch.called,command+' rejects absent authorization flags')
                    else:raise AssertionError('authorization gate not applied')
            for keep in (False,True):
                argv=['war3_bridge.py','run']+(['--keep-open'] if keep else [])
                with patch.object(sys,'argv',argv),patch.object(bridge,'load_session',return_value={'folder':str(base)}),patch.object(bridge,'run_suite',side_effect=RuntimeError('test assertion fails')),patch.object(bridge,'shutdown',return_value={'ok':True}) as close:
                    check(bridge.main()==1 and close.call_count==(0 if keep else 1),'failure cleanup respects explicit keep-open='+str(keep))
            report={'ok':True,'run_id':'check','snapshot_latency':{'samples_ms':[]},'prepare_latency':{},'reset_latency':{},'order_latency':{},'response_target_met':True,'rounds':[{'passed':True}],'simulation_progress':{}}
            for keep in (False,True):
                with patch.object(sys,'argv',['war3_bridge.py','run']+(['--keep-open'] if keep else [])),patch.object(bridge,'load_session',return_value={'folder':str(base)}),patch.object(bridge,'run_suite',return_value=report),patch.object(bridge,'shutdown',return_value={'ok':True}) as close:
                    check(bridge.main()==0 and close.call_count==(0 if keep else 1),'successful batch cleanup respects explicit keep-open='+str(keep))
    check('launch_local_session(s,args.mode)' in (ROOT/'runtime/war3_bridge.py').read_text(encoding='utf8'),'LAN CLI routes through owned-room isolation')
    import desktop_probe
    with tempfile.TemporaryDirectory(prefix='war3-demo-preflight-') as scratch:
        base=Path(scratch);ipc=base/'ipc';ipc.mkdir()
        session={'session':'kit-preflight','build':'kit-build','folder':str(base),'ipc':str(ipc)}
        with patch.object(desktop_probe,'probe',return_value={'input_desktop_accessible':False,'input_desktop':None}),patch.object(bridge,'launch') as product:
            try:bridge.launch_local_session(session,'lan')
            except RuntimeError:pass
            else:raise AssertionError('inaccessible desktop accepted')
            check(not product.called,'exported LAN preflight rejects without product startup')
        with patch.object(bridge,'shutdown_native') as native_owner:
            receipt=bridge.shutdown(session)
            check(receipt['status']=='not_started' and not native_owner.called,'exported preflight cleanup never calls an unused native owner')
    import struct
    from lan_discovery import own_gameinfo
    from lan_startup_guard import startup_lease
    packet=b'\xf7\x30'+struct.pack('<H',30)+b'\x00'*16+b'WB-test\0'+struct.pack('<H',27015)
    check(own_gameinfo(packet,'WB-test',27015) and not own_gameinfo(packet,'other',27015) and not own_gameinfo(packet,'WB-test',27016) and not own_gameinfo(packet[:-1],'WB-test',27015),'room discovery validates captured identity port and length')
    with tempfile.TemporaryDirectory(prefix='war3-lease-check-') as scratch:
        with startup_lease(scratch):
            try:
                with startup_lease(scratch):raise AssertionError('concurrent LAN startup accepted')
            except RuntimeError:check(True,'actual Windows lease rejects overlap')
        try:
            with startup_lease(scratch):raise ValueError('failed startup')
        except ValueError:pass
        with startup_lease(scratch):check(True,'startup lease releases after failure')
    sys.path.insert(0,str(ROOT/'skills/war3-testing/scripts'))
    from check_lifecycle import main as check_lifecycle
    with contextlib.redirect_stdout(io.StringIO()): lifecycle=check_lifecycle()
    check(lifecycle['passed'],'lifecycle and batch failure classification regressions')
    from check_bootstrap import main as check_bootstrap
    with contextlib.redirect_stdout(io.StringIO()): bootstrap=check_bootstrap()
    check(bootstrap['passed'],'owned bootstrap nonce PID and retry contract')
    from owned_network import udp_ports,replay_destination
    import os,socket
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as endpoint:
        endpoint.bind(('127.0.0.1',0))
        check(endpoint.getsockname()[1] in udp_ports(os.getpid()),'actual current-process UDP table ownership')
    check(replay_destination([6112],[6112])=='127.255.255.255' and replay_destination([6113],[6112])=='127.0.0.1','local duplicate-receiver discovery destination')
    import importlib.util
    example_path=ROOT/'examples/demo_batch.py'
    spec=importlib.util.spec_from_file_location('demo_batch_example',example_path)
    example=importlib.util.module_from_spec(spec);spec.loader.exec_module(example)
    class DemoClient:
        def __init__(self):self.gold=0;self.rewards=0;self.deaths=0;self.live=0;self.cache={}
        def request(self,op,args=None,request_id=None):
            replay=request_id is not None and request_id in self.cache
            if replay:return dict(self.cache[request_id],replayed=True),1
            if op=='prepare':self.live=2
            if op=='order':self.rewards+=1;self.deaths+=1;self.gold+=50
            if op=='reset':self.live=0
            state={'actor':{'exists':self.live>0},'target':{'exists':self.live>0},'order_accepted':op=='order',
                'rewards':self.rewards,'deaths':self.deaths,'gold':self.gold,'live_test_units':self.live,'active_death_triggers':int(self.live>0)}
            reply={'id':request_id or op,'ok':True,'replayed':False,'result':state}
            if request_id:self.cache[request_id]=reply
            return reply,1
    with patch.object(bridge,'Client',return_value=DemoClient()):
        report={'trace':[],'checks':[]};ctx=example.Context({},report,lambda:None)
        example.attack_reward(ctx)
        check(len(report['checks'])==5,'generic demo adapter exercises reward replay and reset contract')
    with patch.object(bridge,'shutdown',return_value={'ok':True,'status':'closed'}) as closer:
        with tempfile.TemporaryDirectory() as scratch:
            path=Path(scratch)/'session.json';path.write_text('{}',encoding='utf8')
            check(example.shutdown(path)['ok'] and closer.call_count==1,'generic adapter delegates owned cleanup')
    result={'passed':True,'checks':checks,'scope':'Pure source/protocol/CLI lifecycle checks; no new-environment game proof'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result

if __name__=='__main__':main()
