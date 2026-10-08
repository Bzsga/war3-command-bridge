"""No game or map operations: lifecycle evidence and batch failure regressions."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from session_lifecycle import begin_launch,mark_phase,cleanup_owned,require_attachable
from run_bridge_batch import run


def main():
    checks=[]
    def check(value,label):
        if not value:raise AssertionError(label)
        checks.append(label)
    with tempfile.TemporaryDirectory(prefix='war3-lifecycle-') as scratch:
        root=Path(scratch);folder=root/'session';folder.mkdir();ipc=root/'ipc';ipc.mkdir()
        session={'folder':str(folder),'ipc':str(ipc),'session':'test-session','build':'test-build'}
        begin_launch(session);calls=[]
        def close(_):calls.append(1);return {'ok':True}
        check(cleanup_owned(session,close)['status']=='not_started' and not calls,'explicit preflight skips unused shutdown owner')
        adapter=SimpleNamespace(BOUNDARY='Native owners mocked; no game',CASES={'case':lambda ctx:None},
            open_context=lambda *args:require_attachable(session),shutdown=lambda _:cleanup_owned(session,close))
        with contextlib.redirect_stdout(io.StringIO()):r=run(adapter,root/'session.json',['case'],root/'rejected')
        check(not r['passed'] and r['failure_stage']=='preflight' and r['cleanup_status']=='not_started' and r['cleanup_ok'],'rejected preflight stays failed without false cleanup error')
        (folder/'lan-host').mkdir();(folder/'lan-host/supervisor.log').write_text('started')
        check(cleanup_owned(session,close)['status']=='closed' and len(calls)==1,'contradictory host artifact requires owner cleanup')
        (folder/'lan-host/supervisor.log').unlink()
        mark_phase(session,'starting')
        cleanup_owned(session,close)
        check(len(calls)==2,'uncertain startup cannot be skipped')
        try:begin_launch(session)
        except RuntimeError:check(True,'used session cannot regress to preflight')
        else:raise AssertionError('used session reused')
        marker=folder/'launch-attempt.json';original=marker.read_text();wrong=json.loads(original);wrong['session']='other'
        marker.write_text(json.dumps(wrong))
        try:cleanup_owned(session,close)
        except RuntimeError:check(len(calls)==2,'foreign marker rejected without guessing no startup')
        else:raise AssertionError('foreign marker trusted')
        marker.unlink()
        cleanup_owned(session,close)
        check(len(calls)==3,'missing marker alone never proves not started')
        marker.write_text(original);mark_phase(session,'ready');(folder/'launch.json').write_text('{}')
        adapter.open_context=lambda *args:SimpleNamespace(finish=lambda:{'scope':'mock'})
        adapter.shutdown=lambda _:cleanup_owned(session,close)
        with contextlib.redirect_stdout(io.StringIO()):r=run(adapter,root/'session.json',['case'],root/'success')
        check(r['passed'] and r['cleanup_status']=='closed' and len(calls)==4,'ready batch closes exactly once')
        def fail(ctx):raise AssertionError('business failure')
        adapter.CASES['case']=fail
        with contextlib.redirect_stdout(io.StringIO()):r=run(adapter,root/'session.json',['case'],root/'case-failed')
        check(not r['passed'] and r['failure_stage']=='case' and r['cases'][0]['elapsed_seconds']>=0 and len(calls)==5,'case failure retains time and closes exactly once')
        adapter.CASES['case']=lambda ctx:None
        def failed_observation():raise AssertionError('required window condition lost')
        adapter.open_context=lambda *args:SimpleNamespace(finish=failed_observation)
        with contextlib.redirect_stdout(io.StringIO()):r=run(adapter,root/'session.json',['case'],root/'condition-failed')
        check(not r['passed'] and r['business_passed'] and r['conditions_passed'] is False and r['failure_stage']=='observation','observation failure preserves passed behavior evidence')
        adapter.open_context=lambda *args:SimpleNamespace(finish=lambda:{'scope':'mock'})
        adapter.shutdown=lambda _: {'ok':False}
        with contextlib.redirect_stdout(io.StringIO()):r=run(adapter,root/'session.json',['case'],root/'cleanup-failed')
        check(not r['passed'] and r['business_passed'] and r['failure_stage']=='cleanup','cleanup failure cannot hide behind passed behavior')
        def close_failure(_):raise RuntimeError('unknown owner state')
        adapter.shutdown=close_failure
        with contextlib.redirect_stdout(io.StringIO()):r=run(adapter,root/'session.json',['case'],root/'cleanup-error')
        check(not r['passed'] and not r['cleanup_ok'] and 'shutdown_error' in r,'owner error remains genuine cleanup failure')
        with contextlib.redirect_stdout(io.StringIO()):r=run(adapter,root/'session.json',['case'],root/'retained',keep_open=True)
        check(r['passed'] and r['cleanup_status']=='retained','explicit keep-open is distinct from closed')
    result={'passed':True,'checks':checks,'boundary':'Temporary evidence and owner doubles only; no map/game operations'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__=='__main__':main()
