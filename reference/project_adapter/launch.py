"""Launch a packaged project bridge using the existing KKWE LAN supervisor.

Requires explicit test-map write/game launch authorization. Never launches an
editor or overwrites the fixed map. Human slots other than Player(0) are closed
in this session's host config; the map's W3I remains intact.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
import zlib
from contextlib import nullcontext
from bridge import shared_module,save

def metadata(data):
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    from project_w3i import room_layout
    room=room_layout(data)
    width,height=struct.unpack_from('<ii',data,room['flag_offset']-8)
    usable=[p for p in room['players'] if p['controller'] in (1,2)]
    if not any(p['slot']==0 and p['controller']==1 for p in usable):
        raise ValueError('Player(0) human slot required')
    slots=[]
    for p in usable:
        computer=int(p['controller']==2)
        team=next((i for i,f in enumerate(room['forces']) if f['players']&(1<<p['slot'])),None)
        if team is None:raise ValueError('Player not assigned to a force')
        status=2 if computer else (0 if p['slot']==0 else 1)
        slots.append([0,255,status,computer,team,p['slot'],{1:1,2:2,3:8,4:4}.get(p['race'],32),1,100])
    return {'w3i_version':25,'width':width,'height':height,'options':room['flags']&100,
            'slots':slots,'players':room['players'],'scope':'One human at Player(0); other human lobby slots closed'}

def _main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['launch','shutdown'])
    parser.add_argument('--session',type=Path,required=True)
    parser.add_argument('--map',type=Path)
    parser.add_argument('--mode',choices=['lan','single'],default='lan')
    size_mode=parser.add_mutually_exclusive_group()
    size_mode.add_argument('--host-size-view',action='store_true',help='Explicitly use the verified installed-KKWE client file-size view')
    size_mode.add_argument('--native-host-size',action='store_true',help='Diagnostic opt-out of the verified installed-KKWE large-map handshake adapter')
    args=parser.parse_args()
    session=json.loads(args.session.read_text(encoding='utf8'))
    shared=shared_module(Path(session['shared_bridge']))
    if args.command=='launch':
        from session_lifecycle import begin_launch,mark_phase
        begin_launch(session)
        if session.get('expected_clients',1)!=1:
            raise RuntimeError('Single-client launcher cannot satisfy this session; use the controlled multiplayer runner')
        if args.map is None:parser.error('launch requires --map')
        if args.mode=='lan':
            from desktop_probe import probe,require_lan_desktop
            desktop=probe();save(args.session.parent/'desktop-preflight.json',desktop)
            require_lan_desktop(desktop)
        candidate=args.map.resolve()
        report=json.loads(candidate.with_suffix(candidate.suffix+'.report.json').read_text(encoding='utf8'))
        if not report['ok'] or report['source_sha256']!=session['map_sha256']:
            raise RuntimeError('Candidate report does not match prepared session')
        import hashlib
        if hashlib.sha256(candidate.read_bytes()).hexdigest()!=report['output_sha256']:
            raise RuntimeError('Candidate changed after verification')
        environment=shared.doctor()
        save(args.session.parent/'launch-preflight.json',environment)
        if not environment['ok']:raise RuntimeError(json.dumps(environment,ensure_ascii=False))
        if environment['running_games']:raise RuntimeError('Another War3 session is running; see launch-preflight.json for identity')
        session['map']=str(candidate);session['launch_map']=str(candidate)
        session['environment']=environment
        save(args.session,session)
        # Local adapter only; the reusable demo's parser stays unchanged.
        shared.lan_support.classic_metadata=metadata
        if args.mode=='lan' and (args.host_size_view or not args.native_host_size):
            configure=shared.lan_support.configure
            def configure_client_view(session,root,kkwe,run_checked):
                config=configure(session,root,kkwe,run_checked)
                raw=Path(session['runtime_map']).read_bytes()
                words=config['hash_words']
                if words[0]!=len(raw) or words[1]!=(zlib.crc32(raw)&0xffffffff):
                    raise RuntimeError('Native map size/info do not match independent file check')
                plugin=(kkwe/'plugin/warcraft3/yd_size_limit.dll').read_bytes()
                signature=b'\x81\xfe\xff\xff\x7f\x00'
                if signature not in plugin or 'storm.dll'.encode('utf-16le') not in plugin:
                    raise RuntimeError('Unrecognized installed size-limit plugin; revalidate its file-size view or use --native-host-size for diagnosis')
                visible=min(len(raw),0x7fffff)
                visible_crc=zlib.crc32(raw[:visible])&0xffffffff
                path=Path(config['cwd'])/'map.cfg'
                text=path.read_text(encoding='ascii')
                (path.parent/'map.native.cfg').write_text(text,encoding='ascii')
                def le(value):return ' '.join(str(b) for b in value.to_bytes(4,'little'))
                lines=text.splitlines()
                lines=[('map_size = '+le(visible)) if line.startswith('map_size = ') else
                       ('map_info = '+le(visible_crc)) if line.startswith('map_info = ') else line for line in lines]
                path.write_text('\n'.join(lines)+'\n',encoding='ascii')
                config['client_file_view']={'native_bytes':len(raw),'reported_bytes':visible,
                    'native_info':words[1],'reported_info':visible_crc,
                    'scope':'Known installed KKWE yd_size_limit Storm GetFileSize clamp; game map bytes unchanged'}
                save(path.parent/'config-evidence.json',config)
                return config
            shared.lan_support.configure=configure_client_view
        if args.mode=='lan':
            import time
            read_log=shared.lan_support.host_log;desktop_samples=[];last_sample=0
            from owned_bootstrap import OwnedBootstrap
            from owned_network import udp_ports
            bootstrap=OwnedBootstrap(session['ipc'],session['session'],lan_ready=lambda pid:bool(udp_ports(pid)))
            def observed_host_log(active_session):
                nonlocal last_sample
                bootstrap.tick()
                if time.monotonic()-last_sample>=1:
                    last_sample=time.monotonic();state=probe();state['monotonic']=last_sample
                    desktop_samples.append(state)
                    save(args.session.parent/'desktop-startup.json',{'samples':desktop_samples,'scope':'Startup only; not whole-batch background evidence'})
                return read_log(active_session)
            shared.lan_support.host_log=observed_host_log
        if args.mode=='lan':
            from lan_startup_guard import startup_lease,local_products,require_no_products
            lease=startup_lease(environment['game_directory'])
        else:lease=nullcontext()
        with lease:
            if args.mode=='lan':
                products=local_products()
                save(args.session.parent/'lan-isolation-preflight.json',{'competing_products':products,'scope':'Local games/ydhost only; remote LAN rooms not checked'})
                require_no_products(products)
            if args.mode=='lan':
                from lan_discovery import LocalDiscovery
                discovery=LocalDiscovery(session);start_host=shared.lan_support.start_host
                shared.lan_support.start_host=lambda *params:discovery.start_host(start_host,*params)
                mark_phase(session,'starting')
                try:result=shared.launch(session,args.mode)
                finally:discovery.close()
            else:
                mark_phase(session,'starting');result=shared.launch(session,args.mode)
            if result.get('ok'):mark_phase(session,'ready')
    else:
        from session_lifecycle import cleanup_owned
        result=cleanup_owned(session,shared.shutdown)
    print(json.dumps(result,ensure_ascii=False,indent=2))

def main():
    # Keep failure diagnostics outside the operation so they also cover preflight.
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('command',nargs='?');parser.add_argument('--session',type=Path)
    args,_=parser.parse_known_args()
    try:return _main()
    finally:
        if args.command=='launch' and args.session and args.session.exists():
            from startup_diagnostics import write_diagnostics
            try:write_diagnostics(json.loads(args.session.read_text(encoding='utf8')))
            except Exception as error:
                save(args.session.parent/'diagnostic-error.json',{'error':str(error)})

if __name__=='__main__':main()
