from __future__ import annotations
import time
import uuid
from datetime import datetime,timezone
from pathlib import Path
import threading
from .storage import save
from .schema import validate_cases

class TestCancelled(InterruptedError):pass

def lookup(states,path):
    v=states
    for key in path.split('.'):
        v=v[int(key)] if isinstance(v,list) else v[key]
    return v

def compare(states,step):
    try:a=lookup(states,step['path'])
    except (KeyError,IndexError,TypeError):
        if step['operator']=='exists':return False,{'actual':'字段不存在','expected':'字段存在'}
        raise AssertionError('状态路径不存在: '+step['path'])
    if step['operator']=='exists':return a is not None,{'actual':a,'expected':'字段存在且非null'}
    b=lookup(states,step['ref']) if 'ref' in step else step.get('value')
    if 'offset' in step:
        if type(b) not in (int,float) or type(step['offset']) not in (int,float):raise ValueError('差值比较只支持数值')
        b+=step['offset']
    op=step['operator']
    result={'eq':lambda:a==b,'ne':lambda:a!=b,'gt':lambda:a>b,'ge':lambda:a>=b,'lt':lambda:a<b,'le':lambda:a<=b}[op]()
    return result,{'path':step['path'],'operator':op,'actual':a,'expected':b}

def run_cases(backend,session,cases,catalog,report_dir,cancel=None,log=lambda s:None,close=True):
    validate_cases(cases,catalog);cancel=cancel or threading.Event()
    folder=Path(report_dir);folder.mkdir(parents=True,exist_ok=False)
    report={'schema':1,'id':uuid.uuid4().hex,'started_at':datetime.now(timezone.utc).isoformat(),
            'session':session['session'],'build':session['build'],'status':'running','cases':[],
            'coverage':{'real_game':True,'visual':False,'audio':False,'mouse_hit':False,'multiplayer':False}}
    def persist():save(folder/'report.json',report)
    persist();started=time.monotonic()
    try:
        for case in cases:
            entry={'id':case['id'],'name':case['name'],'tags':case.get('tags',[]),'status':'running','steps':[]};report['cases'].append(entry)
            states={};case_start=time.monotonic();ids={}
            try:
                for n,step in enumerate(case['steps']):
                    if cancel.is_set():raise TestCancelled('任务已取消')
                    row={'index':n+1,'definition':step,'status':'running'};entry['steps'].append(row);persist()
                    tick=time.monotonic()
                    if step['type']=='command':
                        token=step.get('request_id');rid=ids.setdefault(token,uuid.uuid4().hex) if token else uuid.uuid4().hex
                        row['request_id']=rid
                        reply=backend.request(session,step['op'],step.get('args'),rid,cancel)
                        row['response']=reply
                        if not reply.get('ok'):raise AssertionError('游戏拒绝命令: '+str(reply.get('error')))
                        states[step.get('save_as','last')]=reply['result'];states['last']=reply['result']
                    elif step['type']=='assert':
                        ok,detail=compare(states,step);row.update(detail)
                        if not ok:raise AssertionError('断言不符: '+str(detail))
                    else:
                        deadline=tick+float(step.get('timeout',15))
                        while True:
                            if cancel.is_set():raise TestCancelled('任务已取消')
                            reply=backend.request(session,'snapshot',request_id=uuid.uuid4().hex,cancel=cancel)
                            states['last']=reply['result'];ok,detail=compare(states,step);row.update(detail)
                            if ok:break
                            if time.monotonic()>=deadline:raise AssertionError('业务等待超时: '+str(detail))
                            cancel.wait(.15)
                    row.update(status='passed',elapsed_ms=round((time.monotonic()-tick)*1000,2));persist()
                entry['status']='passed';log('通过：'+case['name'])
            except Exception as exc:
                entry['status']='cancelled' if isinstance(exc,InterruptedError) else 'unconfirmed' if isinstance(exc,TimeoutError) else 'failed'
                entry['error']=str(exc)
                if entry['steps']:entry['steps'][-1].update(status=entry['status'],error=str(exc))
                log(case['name']+'：'+str(exc));report['status']=entry['status'];break
            finally:entry['elapsed_ms']=round((time.monotonic()-case_start)*1000,2);persist()
        if report['status']=='running':report['status']='passed'
    finally:
        if close:
            try:
                report['cleanup']=backend.shutdown(session)
                if not report['cleanup'].get('ok'):report['status']='cleanup_failed'
            except Exception as exc:report.update(status='cleanup_failed',cleanup={'ok':False,'error':str(exc)})
        report.update(elapsed_ms=round((time.monotonic()-started)*1000,2),finished_at=datetime.now(timezone.utc).isoformat());persist()
        from html import escape
        rows=''.join('<tr><td>'+escape(c['name'])+'</td><td>'+escape(c['status'])+'</td><td>'+escape(c.get('error',''))+'</td></tr>' for c in report['cases'])
        (folder/'report.html').write_text('<!doctype html><meta charset="utf-8"><title>War3测试报告</title><style>body{font:16px sans-serif;margin:40px;background:#f4f6f8}td,th{padding:12px;text-align:left;border-bottom:1px solid #ccd}table{width:100%}</style><h1>War3 测试报告</h1><p>'+escape(report['status'])+'</p><table><tr><th>用例</th><th>结果</th><th>错误</th></tr>'+rows+'</table><p>本报告不证明画面、音效、鼠标命中或多人同步。</p>',encoding='utf8')
    return report
