import json
import pytest
from workbench.ai import Provider
from workbench.analysis import index_script,context

SCRIPT='''globals
integer Counter=0
endglobals
function Apply takes nothing returns nothing
set Counter=Counter+1
endfunction
'''
FINAL={'summary':'使用原有计数入口','catalog':{'commands':[{'id':'apply','function':'Apply','params':[]}],'fields':[{'id':'count','type':'integer','source':'global','name':'Counter'}]},'cases':[{'id':'count','name':'计数变化','steps':[{'type':'command','op':'apply'},{'type':'assert','path':'last.count','operator':'eq','value':1}]}]}

def test_registered_read_tools_then_valid_plan():
    p=Provider({'model':'fixture'},'');answers=iter([{'tool':'search_functions','query':'Apply'},{'tool':'read_functions','names':['Apply']},FINAL]);captured=[]
    def call(messages):captured.append(list(messages));return json.dumps(next(answers))
    p.call=call;idx=index_script(SCRIPT);assert p.propose(context(idx,'计数'),index=idx)==FINAL
    assert len(captured)==3 and 'Counter' in captured[-1][-1]['content']

def test_unregistered_tool_and_request_cap():
    p=Provider({'model':'fixture'},'');p.call=lambda m:json.dumps({'tool':'shell','command':'delete'})
    with pytest.raises(ValueError,match='未注册'):p.propose({},index=index_script(SCRIPT))
    p.call=lambda m:json.dumps({'tool':'read_functions','names':['Apply']})
    with pytest.raises(RuntimeError,match='5次'):p.propose({},index=index_script(SCRIPT))
