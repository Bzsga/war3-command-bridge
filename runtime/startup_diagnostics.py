"""Read-only startup classification from matching per-session evidence."""
import json
from pathlib import Path
import re


def classify(session,launch=None,discovery=None,phase=None,host_text='',hello=None,pid_record=None):
    launch=launch or {};discovery=discovery or {}
    expected=int(session.get('expected_clients',1));mode=launch.get('launch_mode',session.get('launch_mode','lan'))
    player_names=session.get('player_names') or ['WB'+session['session'][:8]]
    joined=[name for name in player_names if re.search(r'player \['+re.escape(name)+r'\|[^\]]+\] joined the game',host_text)]
    observed={'host_listening':bool(re.search(r' listening on port \d+',host_text)),
              'owned_room_captured':'host_port' in discovery,'client_identity_recorded':bool(pid_record or launch.get('processes')),
              'joined_players':joined,'expected_clients':expected,
              'loading':bool(re.search(r'\bstarted loading with '+str(expected)+r' players\b',host_text)),
              'handshake_matches':bool(hello and hello.get('session')==session['session'] and hello.get('build')==session['build'])}
    ping=launch.get('ready_ping') or {}
    observed['timer_ping_matches']=bool(ping.get('ok') and ping.get('session')==session['session'] and ping.get('build')==session['build'] and ping.get('result',{}).get('ticks',0)>0)
    if observed['timer_ping_matches'] and observed['handshake_matches'] and (mode!='lan' or (len(joined)==expected and observed['loading'])):
        stage='ready'
    elif phase=='preflight':stage='preflight'
    elif 'owned_host_broadcast_not_observed' in discovery.get('errors',[]):stage='room_discovery'
    elif mode=='lan' and not observed['host_listening']:stage='host_setup'
    elif not observed['client_identity_recorded']:stage='client_start'
    elif mode=='lan' and len(joined)<expected:stage='lan_join'
    elif mode=='lan' and not observed['loading']:stage='map_loading'
    elif hello and not observed['handshake_matches']:stage='handshake_identity'
    elif not observed['handshake_matches']:stage='bridge_handshake'
    else:stage='timer_ping'
    return {'session':session['session'],'build':session['build'],'status':'ready' if stage=='ready' else 'incomplete',
            'failure_stage':None if stage=='ready' else stage,'observed':observed,
            'scope':'Startup checkpoints only; no business, rendering or multiplayer acceptance'}


def write_diagnostics(session):
    folder=Path(session['folder']);errors=[]
    def read(path):
        if not path.exists():return None
        try:return json.loads(path.read_text(encoding='utf-8-sig'))
        except (ValueError,OSError) as error:errors.append({'file':str(path),'error':str(error)});return None
    phase=read(folder/'launch-attempt.json')
    if phase and (phase.get('session')!=session['session'] or phase.get('build')!=session['build']):
        raise RuntimeError('Startup phase belongs to another session')
    host=folder/'lan-host/host.log'
    result=classify(session,read(folder/'launch.json'),read(folder/'local-discovery.json'),phase.get('phase') if phase else None,
                    host.read_text(encoding='utf8',errors='replace') if host.exists() else '',
                    read(Path(session['ipc'])/'hello.json'),read(Path(session['ipc'])/'game-process.json'))
    result['read_errors']=errors
    (folder/'launch-diagnostics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result
