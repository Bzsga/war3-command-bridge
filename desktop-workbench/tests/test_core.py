import copy
import json
from pathlib import Path
import threading
import zipfile
import pytest
from workbench.schema import validate_catalog,validate_cases
from workbench.analysis import index_script,check_mapping
from workbench.testing import compare,run_cases
from workbench.storage import Vault,export_project
from workbench.worker import inject

CAT={'commands':[{'id':'apply','label':'应用','function':'Apply','params':[{'name':'value','type':'integer','default':1}]}],
     'fields':[{'id':'value','type':'integer','source':'global','name':'Value'}]}
SCRIPT='''globals
integer Value = 0
endglobals
function Apply takes integer v returns nothing
set Value = v
endfunction
function main takes nothing returns nothing
local integer a = 0
call Apply(0)
endfunction
'''

def test_mapping_rejects_changed_version():
    check_mapping(CAT,index_script(SCRIPT))
    with pytest.raises(ValueError,match='参数已变化'):check_mapping(CAT,index_script(SCRIPT.replace('takes integer v','takes real v')))

def test_injection_preserves_main_and_locals():
    patched=inject(SCRIPT)
    assert patched.index('local integer a')<patched.index('call Apply(0)')<patched.index('call TimerStart(CreateTimer')
    assert 'function WBT_Init' in patched
    with pytest.raises(ValueError,match='已含'):inject(patched)

def test_no_arbitrary_expressions():
    bad=copy.deepcopy(CAT);bad['commands'][0]['function']='Apply();os.execute()'
    with pytest.raises(ValueError):validate_catalog(bad)
    with pytest.raises(ValueError):validate_cases([{'id':'a','steps':[{'type':'assert','path':'__import__("os")','operator':'eq','value':1}]}],CAT)

def test_no_initialization_or_dynamic_script_entry():
    bad=copy.deepcopy(CAT);bad['commands'][0].update(function='main',params=[])
    with pytest.raises(ValueError,match='初始化'):check_mapping(bad,index_script(SCRIPT))
    bad['commands'][0].update(function='Eval',params=[{'name':'script','type':'string','default':''}])
    source='function Eval takes string script returns nothing\ncall ExecuteFunc(script)\nendfunction\n'+SCRIPT
    with pytest.raises(ValueError,match='解释脚本'):check_mapping(bad,index_script(source))

def test_delta_and_missing_fields():
    states={'before':{'count':3},'last':{'count':5}}
    assert compare(states,{'path':'last.count','operator':'eq','ref':'before.count','offset':2})[0]
    assert not compare(states,{'path':'last.no','operator':'exists'})[0]

class FakeBackend:
    def __init__(self,fail=None):self.value=0;self.cache={};self.closed=False;self.fail=fail
    def request(self,s,op,args=None,request_id=None,cancel=None):
        if self.fail:raise self.fail
        if request_id not in self.cache:
            if op=='apply':self.value+=(args or {}).get('value',1)
            self.cache[request_id]={'ok':True,'result':{'value':self.value},'id':request_id}
        return self.cache[request_id]
    def shutdown(self,s):self.closed=True;return {'ok':True}

CASE={'id':'sequence','name':'地图定义场景','tags':[], 'steps':[
    {'type':'command','op':'snapshot','save_as':'before'},
    {'type':'command','op':'apply','args':{'value':2},'request_id':'same'},
    {'type':'command','op':'apply','args':{'value':2},'request_id':'same'},
    {'type':'command','op':'snapshot'},
    {'type':'assert','path':'last.value','operator':'eq','ref':'before.value','offset':2}]}

@pytest.mark.parametrize('failure,status',[(None,'passed'),(TimeoutError('结果未知'),'unconfirmed'),(RuntimeError('退出'),'failed')])
def test_runner_outcomes_cleanup(tmp_path,failure,status):
    b=FakeBackend(failure);r=run_cases(b,{'session':'s','build':'b'},[CASE],CAT,tmp_path/'report')
    assert r['status']==status and b.closed
    assert (tmp_path/'report/report.html').exists()
    if not failure:assert b.value==2

def test_cancel_closes_game(tmp_path):
    event=threading.Event();event.set();b=FakeBackend()
    r=run_cases(b,{'session':'s','build':'b'},[CASE],CAT,tmp_path/'report',event)
    assert r['status']=='cancelled' and b.closed

def test_dpapi_and_export(tmp_path):
    vault=Vault(tmp_path);vault.put('test','private-test-secret');assert vault.get('test')=='private-test-secret'
    assert b'private-test-secret' not in (tmp_path/'credentials/test.bin').read_bytes()
    export_project({'name':'图','input_type':'gui','directory':str(tmp_path),'catalog':CAT,'cases':[CASE],'provider':{'api_key':'private-test-secret'},'map':'private-map'},tmp_path/'share.zip')
    with zipfile.ZipFile(tmp_path/'share.zip') as z:
        content=z.read('project.json').decode();assert 'private-test-secret' not in content and 'private-map' not in content

