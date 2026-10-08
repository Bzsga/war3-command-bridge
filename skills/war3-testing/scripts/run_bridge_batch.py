"""Finite bridge batch with trusted project adapter and guaranteed owned cleanup.

This runner never generates maps or launches games. Attach a previously authorized
session. Project adapters supply actual operations and assertions, not remote code.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback
import uuid

def load_adapter(path):
    path=path.resolve();sys.path.insert(0,str(path.parent))
    spec=importlib.util.spec_from_file_location('war3_batch_project_adapter',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def run(adapter,session_path,cases,out,keep_open=False):
    if not cases or len(cases)!=len(set(cases)):raise ValueError('Specify a finite list of unique case names')
    if any(name not in adapter.CASES for name in cases):raise ValueError('Unknown project case')
    out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'passed':False,'batch':'batch-'+uuid.uuid4().hex[:12],'cases':[],'checks':[],'trace':[],
            'boundary':adapter.BOUNDARY}
    def persist():
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    ctx=None;started=time.perf_counter();cleanup_ok=keep_open;row=None;start=None
    try:
        ctx=adapter.open_context(session_path,report,persist)
        for name in cases:
            row={'name':name,'passed':False};report['cases'].append(row);persist();start=time.perf_counter()
            adapter.CASES[name](ctx)
            row.update(passed=True,elapsed_seconds=time.perf_counter()-start);persist()
        report['passed']=True
    except Exception as exc:
        report['error']=str(exc);report['traceback']=traceback.format_exc();report['failure_case']=report['cases'][-1]['name'] if report['cases'] else 'open_context'
        report['failure_stage']=getattr(exc,'stage','case' if row is not None else 'attach')
        if row is not None:row['elapsed_seconds']=time.perf_counter()-start
    finally:
        report['business_passed']=report['passed']
        report['conditions_passed']=None
        if ctx is not None and hasattr(ctx,'finish'):
            try:report['conditions']=ctx.finish();report['conditions_passed']=True
            except Exception as exc:
                report['condition_error']=str(exc);report['conditions_passed']=False;report['passed']=False;report.setdefault('failure_stage','observation')
        report['cleanup_status']='retained' if keep_open else 'failed'
        if not keep_open:
            try:
                report['shutdown']=adapter.shutdown(session_path);cleanup_ok=report['shutdown'].get('ok',False)
                report['cleanup_status']=report['shutdown'].get('status','closed' if cleanup_ok else 'failed')
            except Exception as exc:report['shutdown_error']=str(exc)
        report['cleanup_ok']=cleanup_ok;report['passed']=report['passed'] and cleanup_ok
        if report['business_passed'] and not cleanup_ok:report.setdefault('failure_stage','cleanup')
        report['elapsed_seconds']=time.perf_counter()-started;persist()
    print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'checks':len(report['checks']),'cleanup_ok':cleanup_ok,'report':str(out/'report.json')},ensure_ascii=False),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adapter',type=Path,required=True)
    p.add_argument('--session',type=Path,required=True);p.add_argument('--cases',nargs='+',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--keep-open',action='store_true')
    args=p.parse_args();result=run(load_adapter(args.adapter),args.session,args.cases,args.out,args.keep_open)
    raise SystemExit(0 if result['passed'] else 1)
