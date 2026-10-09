"""Distinguish a rejected preflight from an owned product needing cleanup.

Missing launch.json alone never proves that nothing started. Skip shutdown only
with a matching explicit preflight marker and no contradictory startup artifacts.
All actual or uncertain launches still use the existing retained-handle owner.
"""
import json
from pathlib import Path


def startup_artifacts(session):
    folder=Path(session['folder']);ipc=Path(session['ipc'])
    paths=[folder/'launch.json',folder/'launch-failure.json',folder/'launcher.log',folder/'launcher-errors.log',folder/'lan-host/supervisor.log',
           ipc/'game-process.json',ipc/'hello.json']
    return [str(p) for p in paths if p.exists()]


def read_phase(session):
    path=Path(session['folder'])/'launch-attempt.json'
    if not path.exists():return None
    value=json.loads(path.read_text(encoding='utf8'))
    if value.get('session')!=session['session'] or value.get('build')!=session['build']:
        raise RuntimeError('Lifecycle marker belongs to another session/build')
    if value.get('phase') not in ('preflight','starting','ready'):
        raise RuntimeError('Unknown lifecycle phase; do not infer no products started')
    return value


def mark_phase(session,phase):
    prior=read_phase(session)
    order={'preflight':0,'starting':1,'ready':2}
    if phase not in order or (prior and order[phase]<order[prior['phase']]):
        raise RuntimeError('Lifecycle phase cannot regress')
    path=Path(session['folder'])/'launch-attempt.json';temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'session':session['session'],'build':session['build'],'phase':phase},indent=2),encoding='utf8')
    temporary.replace(path)


def begin_launch(session):
    prior=read_phase(session)
    if startup_artifacts(session) or (prior and prior['phase']!='preflight'):
        raise RuntimeError('Session already started or attempted; preserve its evidence and use a fresh session')
    mark_phase(session,'preflight')


class SessionNotReadyError(RuntimeError):
    def __init__(self,phase):
        self.stage='preflight' if phase=='preflight' else 'startup'
        super().__init__('Session did not reach ready; launch phase='+phase)


def require_attachable(session):
    phase=read_phase(session)
    if phase and phase['phase']!='ready':
        error=SessionNotReadyError(phase['phase'])
        path=Path(session['folder'])/'launch-diagnostics.json'
        if phase['phase']=='starting' and path.exists():
            diagnostic=json.loads(path.read_text(encoding='utf8'))
            if diagnostic.get('session')==session['session'] and diagnostic.get('build')==session['build']:
                error.stage=diagnostic.get('failure_stage') or 'startup'
        raise error


def cleanup_owned(session,shutdown):
    folder=Path(session['folder'])
    if not (folder/'launch.json').exists():
        phase=read_phase(session)
        if phase and phase['phase']=='preflight' and not startup_artifacts(session):
            result={'ok':True,'status':'not_started','skipped':True,'reason':'preflight_rejected_before_product_start',
                    'evidence':str(folder/'launch-attempt.json')}
            (folder/'shutdown.json').write_text(json.dumps(result,indent=2),encoding='utf8')
            return result
    result=dict(shutdown(session));result.setdefault('status','closed' if result.get('ok') else 'failed')
    return result
