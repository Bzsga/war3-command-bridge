"""One-client LAN launch using existing KKWE ydhost; no client patching."""
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import winreg


def classic_metadata(data):
    # Only the classic v25 format used by this fixed demo template is supported.
    offset=0
    def take(fmt):
        nonlocal offset
        values=struct.unpack_from('<'+fmt,data,offset);offset+=struct.calcsize('<'+fmt)
        return values[0] if len(values)==1 else values
    def string():
        nonlocal offset
        end=data.index(0,offset);value=data[offset:end];offset=end+1
        return value
    version=take('i')
    if version!=25:raise ValueError(f'LAN metadata expects classic W3I v25, got {version}')
    take('ii')
    for _ in range(4):string()
    take('8f4i')
    width,height,flags=take('iiI');take('c');take('i')
    for _ in range(4):string()
    take('i')
    for _ in range(4):string()
    take('i3f4B4s');string();take('c4B')
    count=take('i')
    if not 1<=count<=12:raise ValueError('invalid W3I player count')
    players=[]
    for _ in range(count):
        colour,kind,race,_fixed=take('4i');string();take('2f2I')
        players.append({'colour':colour,'kind':kind,'race':race,'team':0})
    teams=take('i')
    if not 0<=teams<=12:raise ValueError('invalid W3I force count')
    for team in range(teams):
        _flags,mask=take('2I');string()
        for p in players:
            if mask&(1<<p['colour']):p['team']=team
    usable=[p for p in players if p['kind'] in (1,2)]
    # This prototype's JASS scenario is explicitly Player(0), one human.
    humans=[p for p in usable if p['kind']==1]
    if len(humans)!=1 or humans[0]['colour']!=0:
        raise ValueError('LAN demo requires exactly one human slot at Player(0)')
    slots=[]
    for p in usable:
        computer=int(p['kind']==2)
        slots.append([0,255,2 if computer else 0,computer,p['team'],p['colour'],
                      {1:1,2:2,3:8,4:4}.get(p['race'],32),1,100])
    return {'w3i_version':version,'width':width,'height':height,'options':flags&100,
            'slots':slots,'players':players}


def configure(session,root,kkwe,run_checked):
    folder=Path(session['folder'])/'lan-host';folder.mkdir()
    map_path=Path(session['runtime_map'])
    runtime=kkwe/'plugin/w3x2lni_zhCN_v2.7.3'
    expr="_W2L_MODE='CLI';package.path=[["+runtime.as_posix()+"/script/?.lua;"+runtime.as_posix()+"/script/?/init.lua]];package.cpath=[["+runtime.as_posix()+"/bin/?.dll]]"
    run_checked([runtime/'bin/w3x2lni-lua.exe','-E','-e',expr,root/'src/read_w3i.lua',map_path,folder/'war3map.w3i'])
    metadata=classic_metadata((folder/'war3map.w3i').read_bytes())
    result=run_checked([root/'KkweLuaHost.exe',kkwe/'bin',root/'src/map_hash.lua',
                        map_path,kkwe/'jass/system/ht','unused',folder])
    words=json.loads(result['stdout'].lstrip('\ufeff').strip())
    def le(n,size):return ' '.join(str(b) for b in (int(n)&((1<<(8*size))-1)).to_bytes(size,'little'))
    lines=[f'map_size = {le(words[0],4)}',f'map_info = {le(words[1],4)}',
           f'map_crc = {le(words[2],4)}','map_sha1 = '+' '.join(le(w,4) for w in words[3:]),
           f'map_options = {metadata["options"]}',f'map_width = {le(metadata["width"],2)}',
           f'map_height = {le(metadata["height"],2)}']
    lines += ['map_slot%d = %s'%(i,' '.join(map(str,s))) for i,s in enumerate(metadata['slots'],1)]
    (folder/'map.cfg').write_text('\n'.join(lines)+'\n',encoding='ascii')
    relative=session['launch_map']
    # Isolated CWD, short ASCII relative paths in the old narrow-string host.
    mirror=folder/relative;mirror.parent.mkdir(parents=True);shutil.copy2(map_path,mirror)
    (folder/'ydhost.cfg').write_text('bot_autostart = 1\nbot_defaultgamename = WB-'+session['session'][:8]+
        '\nlan_war3version = 27\nbot_mapcfgpath = map.cfg\nbot_mappath = '+relative+'\n',encoding='ascii')
    result={'metadata':metadata,'hash_words':words,'relative_map':relative,
            'executable':str(kkwe/'plugin/ydhost/ydhost.exe'),'cwd':str(folder),
            'network_binding':'ydhost defaults: LAN broadcast and dynamically assigned TCP port'}
    from file_view import apply_file_view
    result=apply_file_view(session,result,kkwe,session.get('file_view','native'))
    (folder/'config-evidence.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def start_host(session,root,kkwe,run_checked):
    config=configure(session,root,kkwe,run_checked);folder=Path(config['cwd'])
    with (folder/'supervisor.log').open('wb') as log:
        owner=subprocess.Popen([sys.executable,'-X','utf8','-B',str(root/'src/lan_host.py'),
                                str(folder),config['executable']],stdout=log,stderr=log,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    config['owner_pid']=owner.pid
    deadline=time.perf_counter()+10
    while time.perf_counter()<deadline:
        text=host_log(session)
        if ' listening on port ' in text:
            identity=json.loads((folder/'host-process.json').read_text(encoding='utf-8'))
            if Path(identity['actual_executable']).resolve()!=Path(config['executable']).resolve():
                raise RuntimeError('wrong ydhost executable')
            config['identity']=identity
            return config
        if owner.poll() is not None:break
        time.sleep(.1)
    raise RuntimeError('LAN host did not listen: '+host_log(session))


def host_log(session):
    p=Path(session['folder'])/'lan-host/host.log'
    return p.read_text(encoding='utf-8',errors='replace') if p.exists() else ''


def stop_host(session):
    folder=Path(session['folder'])/'lan-host'
    if not folder.exists():return None
    (folder/'host.stop').write_text('stop',encoding='ascii')
    # A failed configure never spawned a host.
    if not (folder/'supervisor.log').exists():return {'not_started':True}
    deadline=time.perf_counter()+10
    while time.perf_counter()<deadline:
        if (folder/'host-exited.json').exists():
            return json.loads((folder/'host-exited.json').read_text(encoding='utf-8'))
        time.sleep(.1)
    raise RuntimeError('LAN host owner did not confirm exit; inspect supervisor.log')


@contextmanager
def temporary_player_name(session):
    # The existing installation may store REG_BINARY, not REG_SZ. Preserve both.
    path=r'Software\Blizzard Entertainment\Warcraft III\String'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,path,0,winreg.KEY_READ|winreg.KEY_SET_VALUE) as key:
        try:original,kind=winreg.QueryValueEx(key,'userlocal');exists=True
        except FileNotFoundError:original=None;kind=None;exists=False
        recovery={'existed':exists,'type':kind,'value':original.hex() if isinstance(original,bytes) else original,
                  'bytes_hex':isinstance(original,bytes),'restored':False}
        record=Path(session['folder'])/'player-name-recovery.json'
        record.write_text(json.dumps(recovery,ensure_ascii=False,indent=2),encoding='utf-8')
        name='WB'+session['session'][:8]
        winreg.SetValueEx(key,'userlocal',0,winreg.REG_SZ,name)
        try:yield name
        finally:
            if exists:winreg.SetValueEx(key,'userlocal',0,kind,original)
            else:winreg.DeleteValue(key,'userlocal')
            recovery['restored']=True
            record.write_text(json.dumps(recovery,ensure_ascii=False,indent=2),encoding='utf-8')
