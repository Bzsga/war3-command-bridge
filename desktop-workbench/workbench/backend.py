from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from .storage import save,read

def assets():return Path(__file__).resolve().parents[1]

class Backend:
    """Every operation runs in a project-owned process; no shared runtime globals."""
    def __init__(self,project):
        self.project=project;self.directory=Path(project['directory']).resolve()
        self.engine=self.directory/'engine'
        self.engine.mkdir(parents=True,exist_ok=True)
        shutil.copytree(assets()/'vendor/runtime',self.engine,dirs_exist_ok=True)
        save(self.engine/'config.json',{**project['environment'],'template':project['map']})
    def call(self,action,params=None,cancel=None,timeout=180):
        folder=self.directory/'jobs'/uuid.uuid4().hex;folder.mkdir(parents=True)
        job={'action':action,'project':self.project,'params':params or {},'result':str(folder/'result.json'),'cancel':str(folder/'cancel')}
        path=folder/'job.json';save(path,job)
        cmd=[sys.executable,'--worker',str(path)] if getattr(sys,'frozen',False) or '__compiled__' in globals() else [sys.executable,str(assets()/'main.py'),'--worker',str(path)]
        with (folder/'stdout.log').open('wb') as out,(folder/'stderr.log').open('wb') as err:
            p=subprocess.Popen(cmd,stdout=out,stderr=err,creationflags=0x08000000 if os.name=='nt' else 0)
            started=time.monotonic();signalled=False
            while p.poll() is None:
                if cancel and cancel.is_set() and not signalled:(folder/'cancel').touch();signalled=True
                if time.monotonic()-started>timeout:
                    (folder/'cancel').touch()
                    try:p.wait(20)
                    except subprocess.TimeoutExpired:p.terminate();p.wait(5)
                    raise TimeoutError('工作进程超时，保留任务与收尾记录: '+str(folder))
                time.sleep(.03)
        if not (folder/'result.json').exists():raise RuntimeError('工作进程异常退出: '+(folder/'stderr.log').read_text(encoding='utf8',errors='replace')[-5000:])
        result=read(folder/'result.json')
        if not result['ok']:
            if action in {'prepare','launch','inspect'}:
                report_folder=self.directory/'reports'/uuid.uuid4().hex
                from datetime import datetime,timezone
                save(report_folder/'report.json',{'schema':1,'id':report_folder.name,'started_at':datetime.now(timezone.utc).isoformat(),'status':result.get('stage',action)+'_failed','cases':[],
                    'failure_stage':result.get('stage',action),'error':result['error'],'job':str(folder),'coverage':{'real_game':False,'visual':False,'audio':False,'mouse_hit':False,'multiplayer':False}})
            if result.get('kind')=='TimeoutError':raise TimeoutError(result['error'])
            if result.get('kind')=='InterruptedError':raise InterruptedError(result['error'])
            raise RuntimeError(result['error'])
        return result['value']
    def doctor(self):return self.call('doctor')
    def inspect(self,cancel=None):return self.call('inspect',cancel=cancel)
    def prepare(self,catalog,cancel=None):return self.call('prepare',{'catalog':catalog},cancel)
    def launch(self,session,cancel=None):return self.call('launch',{'session':session},cancel,timeout=160)
    def request(self,session,op,args=None,request_id=None,cancel=None):return self.call('request',{'session':session,'op':op,'args':args,'request_id':request_id or uuid.uuid4().hex},cancel,timeout=20)
    def shutdown(self,session):return self.call('shutdown',{'session':session},timeout=45)
    def create_demo(self,out,cancel=None):return self.call('create_demo',{'out':str(out)},cancel,timeout=90)
