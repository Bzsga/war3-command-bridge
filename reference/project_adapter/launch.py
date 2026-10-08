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

def main():
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
        if args.map is None:parser.error('launch requires --map')
        candidate=args.map.resolve()
        report=json.loads(candidate.with_suffix(candidate.suffix+'.report.json').read_text(encoding='utf8'))
        if not report['ok'] or report['source_sha256']!=session['map_sha256']:
            raise RuntimeError('Candidate report does not match prepared session')
        import hashlib
        if hashlib.sha256(candidate.read_bytes()).hexdigest()!=report['output_sha256']:
            raise RuntimeError('Candidate changed after verification')
        environment=shared.doctor()
        if not environment['ok']:raise RuntimeError(json.dumps(environment,ensure_ascii=False))
        if environment['running_games']:raise RuntimeError('Another War3 session is running')
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
        result=shared.launch(session,args.mode)
    else:
        result=shared.shutdown(session)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
