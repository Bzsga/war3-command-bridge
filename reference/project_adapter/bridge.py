"""Prepare isolated bridge inputs, or send a fixed command to an attached game.

Never writes a .w3x, launches an editor/game, or changes canonical source.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import uuid

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
DEFAULT_SHARED=Path(__file__).resolve().parents[2]/'runtime'

def shared_module(path):
    path=path.resolve()
    sys.path.insert(0,str(path))
    spec=importlib.util.spec_from_file_location('zjb_shared_transport',path/'war3_bridge.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def prepare(out,shared):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Blizzard Entertainment\Warcraft III') as key:
        game=Path(os.environ.get('WAR3_BRIDGE_GAME') or winreg.QueryValueEx(key,'InstallPath')[0])
    baseline=json.loads((ROOT/'project/map-baseline.json').read_text(encoding='utf8'))
    map_path=Path(baseline['active_map'])
    if hashlib.sha256(map_path.read_bytes()).hexdigest()!=baseline['sha256']:
        raise RuntimeError('Map differs from current baseline; absorb saved changes first')
    # Refuse to clobber a previous session or its evidence.
    out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    session=uuid.uuid4().hex;build='zjb1-'+session[:12]
    ipc_relative='WBTestBridge/'+session
    source=(ROOT/'project/engineering/source.j').read_text(encoding='utf8')
    anchor='    call ExecuteFunc("DTRuntimeBody")\n'
    if source.count(anchor)!=1:
        raise RuntimeError('Bootstrap anchor must be unique')
    globals_text='''    string ZJB_State=""
    integer ZJB_Control=0
    boolean ZJB_Accepted=false
    string ZJB_LastError=""
    timer ZJB_Timer=null
    string ZJB_Detail=""
    integer ZJB_Prepare=0
    integer ZJB_Scene=0
    integer ZJB_SceneSerial=0
'''
    candidate=source.replace(anchor,anchor+'    call ExecuteFunc("ZJB_Start")\n',1)
    candidate=candidate.replace('globals\n','globals\n'+globals_text,1)
    candidate+='\n'+(HERE/'bridge.j').read_text(encoding='utf8').replace('__BUILD_TEXT__',build)
    (out/'source.j').write_text(candidate,encoding='utf8')
    module=shared_module(shared)
    lua=(HERE/'bridge.lua').read_text(encoding='utf8')
    lua=lua.replace('__JSON_CODEC__',(shared/'src/json.lua').read_text(encoding='utf8'))
    for token,value in [('__SESSION__',session),('__BUILD__',build),('__IPC__',ipc_relative)]:
        lua=lua.replace(token,module.lua_string(value.encode('utf8')))
    lua="local ok,result=pcall(function()\n"+lua+"\nend);if ok then return result else return {status='bootstrap_error: '..tostring(result)} end\n"
    (out/'ZJCommandBridge.lua').write_text(lua,encoding='utf8')
    manifest={'session':session,'build':build,'folder':str(out),'ipc':str(game/ipc_relative),
              'map_source':str(map_path),'map_sha256':baseline['sha256'],'shared_bridge':str(shared.resolve()),
              'members':{'war3map.j':'compile/compiled.j','ZJCommandBridge.lua':'ZJCommandBridge.lua'},
              'scope':'Single human test copy; no map generated and no runtime proof'}
    save(out/'session.json',manifest)
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shared',type=Path,default=DEFAULT_SHARED)
    sub=parser.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--out',type=Path,required=True)
    attach=sub.add_parser('attach-ipc');attach.add_argument('--session',type=Path,required=True)
    request=sub.add_parser('request');request.add_argument('--session',type=Path,required=True)
    request.add_argument('--op',choices=['ping','snapshot','activate'],required=True)
    request.add_argument('--control',type=int);request.add_argument('--id')
    args=parser.parse_args()
    if args.command=='prepare':
        result=prepare(args.out,args.shared)
    else:
        session=json.loads(args.session.read_text(encoding='utf8'))
        if args.command=='attach-ipc':
            ipc=Path(session['ipc']);ipc.mkdir(parents=True,exist_ok=False)
            (ipc/'probe.txt').write_text(session['session'],encoding='ascii')
            result={'ipc':str(ipc),'attached':True}
        else:
            if args.op=='activate' and (args.control is None or not 1<=args.control<=327):
                parser.error('activate requires --control in 1..327')
            module=shared_module(Path(session['shared_bridge']))
            response,elapsed=module.Client(session).request(args.op,{'control':args.control} if args.op=='activate' else None,request_id=args.id)
            result={'response':response,'elapsed_ms':elapsed}
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
