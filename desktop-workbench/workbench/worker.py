from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback
import uuid
from .analysis import decode,index_script,check_mapping
from .schema import validate_catalog
from .storage import save,read
from .backend import assets

def runtime(project):
    engine=Path(project['directory'])/'engine'
    sys.path.insert(0,str(engine))
    spec=importlib.util.spec_from_file_location('project_runtime',engine/'war3_bridge.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.configure({**project['environment'],'template':project['map']},engine)
    module.lan_support.OWNER_COMMAND=([sys.executable,'--host-owner'] if getattr(sys,'frozen',False) else [sys.executable,str(assets()/'main.py'),'--host-owner'])
    return module

def w2l_command(m,script,*args):
    root=m.KKWE/'plugin/w3x2lni_zhCN_v2.7.3'
    expr="_W2L_MODE='CLI';package.path=[["+m.short_path(root).replace('\\','/')+"/script/?.lua]];"
    return m.run_checked([root/'bin/w3x2lni-lua.exe','-e',expr,script,*[m.short_path(Path(a)) for a in args]])

def inspect(project,m):
    folder=Path(project['directory'])/'inspection'/uuid.uuid4().hex;folder.mkdir(parents=True)
    w2l_command(m,assets()/'vendor/read_archive.lua',project['map'],folder)
    script_path=folder/'war3map.j'
    if not script_path.exists():raise ValueError('地图没有已保存的war3map.j；请在编辑器保存编译后重试')
    script=decode(script_path.read_bytes());index=index_script(script)
    if 'main' not in index['functions']:raise ValueError('运行脚本缺少main，不能接入')
    gui={}
    if project['input_type']=='gui':
        for name in ['war3map.wtg','war3map.wct']:
            if not (folder/name).exists():raise ValueError('GUI地图缺少'+name+'；不支持自动接入保护图')
        sys.path.insert(0,str(assets()/'vendor'));import wtg_parser
        definitions=Path(project['environment'].get('definitions') or m.KKWE/'share/mpq')
        defs=wtg_parser.DefinitionSet.from_root(definitions)
        gui=wtg_parser.read_wtg(folder/'war3map.wtg',defs).to_dict()
    return {'script':str(script_path),'index':index,'gui':gui,'map_sha256':hashlib.sha256(Path(project['map']).read_bytes()).hexdigest(),'folder':str(folder)}

def inject(script):
    if re.search(r'\bWBT_(?:Init|Tick|Timer|Status)\b',script):raise ValueError('输入地图已含工作台桥，请选择正式原图')
    if not re.search(r'(?m)^\s*native\s+EXExecuteScript\b',script):script='native EXExecuteScript takes string script returns string\n'+script
    globals_='\n    timer WBT_Timer = null\n    string WBT_Status = ""\n'
    if not re.search(r'(?m)^\s*globals\s*$',script):raise ValueError('地图缺少globals块')
    script=re.sub(r'(?m)^(\s*globals\s*)$',lambda m:m.group(1)+globals_,script,count=1)
    bridge='''function WBT_Tick takes nothing returns nothing
    set WBT_Status = EXExecuteScript("WBT_Bridge.tick()")
endfunction
function WBT_Init takes nothing returns nothing
    local integer i = 0
    local integer humans = 0
    call DestroyTimer(GetExpiredTimer())
    loop
        exitwhen i >= 12
        if GetPlayerController(Player(i)) == MAP_CONTROL_USER and GetPlayerSlotState(Player(i)) == PLAYER_SLOT_STATE_PLAYING then
            set humans = humans + 1
        endif
        set i = i + 1
    endloop
    if humans != 1 then
        return
    endif
    call Cheat("exec-lua:War3TestBridge")
    set WBT_Status = EXExecuteScript("(require 'War3TestBridge').status")
    if WBT_Status == "ready" then
        set WBT_Timer = CreateTimer()
        call TimerStart(WBT_Timer, 0.05, true, function WBT_Tick)
    endif
endfunction
'''
    script=re.sub(r'(?m)^(\s*function\s+main\s+takes\s+nothing\s+returns\s+nothing)',lambda m:bridge+'\n'+m.group(1),script,count=1)
    pattern=r'(?ms)(^\s*function\s+main\s+takes\s+nothing\s+returns\s+nothing\b.*?)(^\s*endfunction)'
    script,count=re.subn(pattern,lambda m:m.group(1)+'    call TimerStart(CreateTimer(), 0.10, false, function WBT_Init)\n'+m.group(2),script,count=1)
    if count!=1:raise ValueError('不能定位main入口')
    return script

def compile_script(m,source,out):
    compiler=m.KKWE/'plugin/jasshelper/clijasshelper.exe'
    out.parent.mkdir(parents=True,exist_ok=True)
    (out.parent/'jasshelper.conf').write_text('[jasscompiler]\n"pjass.exe"\n"$COMMONJ $BLIZZARDJ $WAR3MAPJ"\n',encoding='ascii')
    p=subprocess.run([str(compiler),'--scriptonly',str(m.KKWE/'plugin/jasshelper/common.j'),str(m.KKWE/'plugin/jasshelper/blizzard.j'),str(source),str(out)],cwd=out.parent,capture_output=True,creationflags=0x08000000)
    (out.parent/'compile.log').write_bytes(p.stdout+p.stderr)
    if p.returncode or not out.exists():raise RuntimeError('脚本编译失败：'+decode((p.stdout+p.stderr) or b'no compiler output')[-7000:])
    return {'ok':True,'log':str(out.parent/'compile.log')}

def prepare(project,m,catalog,cancel):
    m.stage='environment'
    environment=m.doctor()
    if not environment['ok']:raise RuntimeError('环境检查失败: '+json.dumps(environment,ensure_ascii=False))
    m.stage='integration';info=inspect(project,m);check_mapping(catalog,info['index'])
    session_id=uuid.uuid4().hex;build='wbt-'+session_id[:12]
    folder=m.ROOT/'runs'/session_id;folder.mkdir(parents=True)
    original=Path(project['map']);map_hash=hashlib.sha256(original.read_bytes()).hexdigest()
    game=Path(environment['game_directory']);ipc=game/'WBTestBridge'/session_id
    ipc.mkdir(parents=True);(ipc/'probe.txt').write_text(session_id,encoding='ascii')
    input_map=original
    script=Path(info['script']).read_bytes().decode('utf8',errors='surrogateescape')
    argv=project.get('build_argv',[])
    if project['input_type']=='source' and argv:
        m.stage='source_build'
        src=Path(project['source_dir']).resolve();dst=folder/'source'
        if not src.is_dir():raise ValueError('源码目录不存在')
        if Path(project['directory']).resolve().is_relative_to(src):raise ValueError('工作台项目目录不能放在源码目录内')
        def ignore(path,names):return [n for n in names if n in {'.git','node_modules','.venv','__pycache__'} or (Path(path)/n).is_symlink() or ((Path(path)/n).stat().st_file_attributes & 0x400)]
        shutil.copytree(src,dst,ignore=ignore)
        built=folder/'source-output.j'
        command=[str(a).replace('{source}',str(dst)).replace('{output}',str(built)) for a in argv]
        if not Path(command[0]).is_absolute():raise ValueError('登记的构建程序须为绝对路径')
        with (folder/'source-build.log').open('wb') as log:
            proc=subprocess.Popen(command,cwd=dst,stdout=log,stderr=log,creationflags=0x08000000)
            import time
            deadline=time.monotonic()+120
            while proc.poll() is None:
                if Path(cancel).exists() or time.monotonic()>deadline:proc.terminate();proc.wait();raise InterruptedError('源码构建取消或超时')
                time.sleep(.1)
        if proc.returncode or not built.exists():raise RuntimeError('源码构建失败，构建入口必须输出{output}指定的完整运行脚本；见'+str(folder/'source-build.log'))
        script=built.read_bytes().decode('utf8',errors='surrogateescape');check_mapping(catalog,index_script(script))
    if Path(cancel).exists():raise InterruptedError('任务已取消')
    patched=folder/'bridge-input.j';patched.write_bytes(inject(script).encode('utf8',errors='surrogateescape'))
    m.stage='compile';compiled=folder/'compiled.j';compiler=compile_script(m,patched,compiled)
    lua=(assets()/'vendor/project_bridge.lua').read_text(encoding='utf8')
    codec=(m.ROOT/'src/json.lua').read_text(encoding='utf8')
    for key,value in {'__JSON_CODEC__':codec,'__SESSION__':m.lua_string(session_id.encode()),'__BUILD__':m.lua_string(build.encode()),'__CATALOG__':m.lua_string(json.dumps(catalog,ensure_ascii=False).encode()),'__IPC__':m.lua_string(ipc.relative_to(game).as_posix().encode())}.items():lua=lua.replace(key,value)
    generated=folder/'War3TestBridge.lua';generated.write_text(lua,encoding='utf8')
    host=m.ROOT/'KkweLuaHost.exe'
    if not host.exists():m.run_checked([Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework/v4.0.30319/csc.exe','/nologo','/platform:x86','/out:'+str(host),m.ROOT/'src/KkweLuaHost.cs'])
    map_path=folder/('WBT-'+session_id[:12]+'.w3x');shutil.copy2(input_map,map_path)
    m.stage='archive'
    try:
        packed=w2l_command(m,m.ROOT/'src/pack_demo.lua',input_map,map_path,compiled,folder,generated)
        verification=json.loads(packed['stdout'])
        if hashlib.sha256(original.read_bytes()).hexdigest()!=map_hash:raise RuntimeError('原图在构建期间发生变化，请重新接入')
    except Exception:
        map_path.unlink(missing_ok=True);raise
    session={'session':session_id,'build':build,'folder':str(folder),'ipc':str(ipc),'map':str(map_path),'launch_map':str(map_path),'template':str(original),'environment':environment,'compiler':compiler,'archive_verification':verification,'catalog':catalog,'map_sha256':map_hash,'project':project['id']}
    save(folder/'session.json',session);save(Path(project['directory'])/'active-session.json',session)
    return session

def validate_session(project,m,session):
    sid=session.get('session','')
    if not re.fullmatch(r'[0-9a-f]{32}',sid):raise ValueError('会话身份无效')
    folder=Path(session['folder']).resolve()
    if folder!=(m.ROOT/'runs'/sid).resolve():raise ValueError('会话不属于本项目')
    if Path(session['ipc']).resolve()!=(Path(project['environment']['game'])/'WBTestBridge'/sid).resolve():raise ValueError('通信目录不属于本会话')
    if not Path(session['map']).resolve().is_relative_to(folder):raise ValueError('测试地图不属于本会话')
    recorded=read(folder/'session.json')
    if recorded['session']!=sid or recorded['build']!=session['build']:raise ValueError('会话版本不匹配')

def main(job_path):
    job=read(job_path);project=job['project'];params=job['params'];m=None
    try:
        m=runtime(project);m.CANCEL_PATH=job['cancel']
        action=job['action']
        if action in {'launch','request','shutdown'}:validate_session(project,m,params['session'])
        if action=='doctor':value=m.doctor()
        elif action=='create_demo':
            spec=importlib.util.spec_from_file_location('create_demo',assets()/'examples/create_demo.py')
            demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)
            value=str(demo.create(params['out'],project['map'],project['environment']['kkwe'],project['environment']['game']))
        elif action=='inspect':value=inspect(project,m)
        elif action=='prepare':value=prepare(project,m,params['catalog'],job['cancel'])
        elif action=='launch':
            session=params['session']
            if hashlib.sha256(Path(project['map']).read_bytes()).hexdigest()!=session['map_sha256']:raise RuntimeError('原图已更新，请重新构建测试副本')
            try:value=m.launch_local_session(session,'lan')
            except Exception:
                try:m.shutdown(session)
                except Exception:pass
                raise
        elif action=='request':
            session=params['session']
            if Path(job['cancel']).exists():raise InterruptedError('任务已取消')
            value,elapsed=m.Client(session).request(params['op'],params.get('args'),params['request_id'],expected_error=True)
            if value.get('id')!=params['request_id']:raise RuntimeError('响应请求ID不匹配')
            value['elapsed_ms']=elapsed
        elif action=='shutdown':
            value=m.shutdown(params['session'])
            if value.get('ok'):
                s=params['session'];copy=Path(s['environment']['game_directory'])/'Maps/Test'/Path(s['map']).name
                if copy.resolve().is_relative_to((Path(s['environment']['game_directory'])/'Maps/Test').resolve()) and copy.name.startswith('WBT-'):
                    copy.unlink(missing_ok=True);value['runtime_copy_removed']=True
        else:raise ValueError('未知工作动作')
        save(Path(job['result']),{'ok':True,'value':value})
    except Exception as e:
        save(Path(job['result']),{'ok':False,'kind':type(e).__name__,'stage':getattr(m,'stage',job['action']),'error':str(e)})
        traceback.print_exc();return 1
    return 0
