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
    required=['war3_bridge.py','lan_support.py','background_probe.py','file_view.py','src/lan_host.py','src/KkweLuaHost.cs','src/kkwe_launcher.lua','src/map_hash.lua','src/read_w3i.lua','src/pack_demo.lua','src/map.j.template','src/bridge.lua','src/json.lua']
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
    result={'passed':True,'checks':checks,'scope':'Pure source/protocol/CLI lifecycle checks; no new-environment game proof'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result

if __name__=='__main__':main()
