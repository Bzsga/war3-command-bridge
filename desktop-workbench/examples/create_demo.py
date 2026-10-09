"""Create source/GUI demonstration maps from an author's independent template.

Requires explicit map-copy permission. Never writes the input template. These
small authoring fixtures demonstrate data-driven tests, not a specific map genre.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workbench.storage import save
from workbench.backend import Backend,assets
from workbench.worker import runtime,w2l_command,compile_script

def create(out,template,kkwe,game):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    p={'id':'demo','name':'条件与计数演示','directory':str(out/'builder'),'input_type':'source','map':str(template),'environment':{'kkwe':str(kkwe),'game':str(game)}}
    backend=Backend(p);m=runtime(p)
    raw=(assets()/'vendor/runtime/src/map.j.template').read_text(encoding='utf8')
    config=raw[raw.index('function config'):].replace('__BUILD_TEXT__','WorkbenchDemo')
    globals_='''globals
    integer udg_DemoCount = 0
    integer udg_DemoInput = 0
    trigger gg_trg_Apply = null
    trigger gg_trg_Reset = null
endglobals
'''
    business='''function Apply takes integer amount returns nothing
    if amount > 0 and amount <= 3 then
        set udg_DemoCount = udg_DemoCount + amount
    endif
endfunction
function Reset takes nothing returns nothing
    set udg_DemoCount = 0
endfunction
function Trig_Apply_Conditions takes nothing returns boolean
    return udg_DemoCount < 2
endfunction
function Trig_Apply_Actions takes nothing returns nothing
    set udg_DemoCount = udg_DemoCount + 1
endfunction
function Trig_Reset_Actions takes nothing returns nothing
    set udg_DemoCount = 0
endfunction
function main takes nothing returns nothing
    call SetCameraBounds(-3584.0, -4096.0, 4352.0, 3584.0, -3584.0, 3584.0, 4352.0, -4096.0)
    call SetDayNightModels("Environment\\\\DNC\\\\DNCLordaeron\\\\DNCLordaeronTerrain.mdl", "Environment\\\\DNC\\\\DNCLordaeron\\\\DNCLordaeronUnit\\\\DNCLordaeronUnit.mdl")
    call InitBlizzard()
    set gg_trg_Apply = CreateTrigger()
    call TriggerAddCondition(gg_trg_Apply, Condition(function Trig_Apply_Conditions))
    call TriggerAddAction(gg_trg_Apply, function Trig_Apply_Actions)
    set gg_trg_Reset = CreateTrigger()
    call TriggerAddAction(gg_trg_Reset, function Trig_Reset_Actions)
endfunction
'''
    source=globals_+business+config
    (out/'source.j').write_text(source,encoding='utf8');compiled=out/'compiled.j';compile_script(m,out/'source.j',compiled)
    sys.path.insert(0,str(assets()/'vendor'));import wtg_parser as w
    defs=w.DefinitionSet.from_root(Path(kkwe)/'share/mpq')
    args=w.WtgArgument
    op=w.WtgEca(3,'OperatorInt',args=[args(1,'DemoCount'),args(0,'OperatorAdd'),args(0,'1')])
    apply=w.WtgTrigger('Apply',initially_on=1,ecas=[w.WtgEca(1,'OperatorCompareInteger',args=[args(1,'DemoCount'),args(0,'OperatorLess'),args(0,'2')]),w.WtgEca(2,'SetVariable',args=[args(1,'DemoCount'),args(2,'',call=op)])])
    reset=w.WtgTrigger('Reset',initially_on=1,ecas=[w.WtgEca(2,'SetVariable',args=[args(1,'DemoCount'),args(0,'0')])])
    gui=w.WtgFile(7,[w.WtgCategory(0,'示例')],[w.WtgVariable('DemoCount','integer'),w.WtgVariable('DemoInput','integer')],[apply,reset])
    w.write_wtg(out/'war3map.wtg',gui,defs)
    # WCT v1: root comment, root code length, per-trigger empty custom text.
    (out/'war3map.wct').write_bytes(struct.pack('<i',1)+b'\0'+struct.pack('<ii',0,2)+struct.pack('<ii',0,0))
    script=out/'make_fixture.lua';script.write_text("local fs=require 'bee.filesystem';local mpq=require 'ffi.stormlib';local a=assert(mpq.open(fs.path(arg[1]),false));for _,n in ipairs{'war3map.j','war3map.wtg','war3map.wct'} do local path=n=='war3map.j' and 'compiled.j' or n;local f=assert(io.open(arg[2]..'/'..path,'rb'));local d=f:read('*a');f:close();assert(a:save_file(n,d)) end;a:close()",encoding='utf8')
    for kind in ['source','gui']:
        map_path=out/(kind+'-demo.w3x');shutil.copy2(template,map_path);w2l_command(m,script,map_path,out)
        fields=[{'id':'count','label':'计数','type':'integer','source':'global','name':'udg_DemoCount'},{'id':'ticks','label':'桥计时','type':'integer','source':'ticks'}]
        commands=[{'id':'apply','label':'应用','function':'Apply','params':[{'name':'amount','type':'integer','default':1}]},{'id':'reset','label':'示例自有重置','function':'Reset','params':[]}]
        if kind=='gui':
            commands=[{'id':'apply','label':'运行带条件触发器','entry_kind':'trigger','trigger':'gg_trg_Apply','function':'Trig_Apply_Actions','params':[]},{'id':'reset','label':'示例自有重置','entry_kind':'trigger','trigger':'gg_trg_Reset','function':'Trig_Reset_Actions','params':[]}]
        def cmd(op,args=None,token=None):
            d={'type':'command','op':op,'args':args or {}}
            if token:d['request_id']=token
            return d
        def check(value):return {'type':'assert','path':'last.count','operator':'eq','value':value}
        steps=[cmd('reset'),check(0),cmd('apply',{'amount':1} if kind=='source' else {},'dedup'),check(1),cmd('apply',{'amount':1} if kind=='source' else {},'dedup'),cmd('snapshot'),check(1)]
        if kind=='source':steps+=[cmd('apply',{'amount':-1}),check(1)]
        else:steps+=[cmd('apply'),check(2),cmd('apply'),cmd('snapshot'),check(2)]
        cases=[{'id':'author_behavior','name':'正常、条件边界与请求去重','tags':[],'steps':steps}]
        project_dir=out/(kind+'-project');project_dir.mkdir()
        source_dir=out/'author-source'
        source_dir.mkdir(exist_ok=True);shutil.copy2(out/'source.j',source_dir/'source.j');shutil.copy2(Path(__file__).parent/'build_source.py',source_dir/'build_source.py')
        builder=[sys.executable,'--demo-build-source','{source}/source.j','{output}'] if getattr(sys,'frozen',False) else [sys.executable,'{source}/build_source.py','--output','{output}']
        project_id=uuid.uuid4().hex
        project={'schema':1,'id':project_id,'name':kind.upper()+' 接入示例','directory':str(project_dir),'input_type':kind,'map':str(map_path),'source_dir':str(source_dir) if kind=='source' else '', 'build_argv':builder if kind=='source' else [],'environment':p['environment'],'provider':{'service':'DeepSeek','base_url':'https://api.deepseek.com','model':'','credential':project_id},'catalog':{'commands':commands,'fields':fields},'cases':cases}
        save(project_dir/'project.json',project)
    return out

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--template',required=True);a.add_argument('--kkwe',required=True);a.add_argument('--game',required=True);a.add_argument('--out',required=True);a.add_argument('--i-confirm-map-write',action='store_true');p=a.parse_args()
    if not p.i_confirm_map_write:a.error('需要明确允许创建测试地图副本')
    print(create(p.out,p.template,p.kkwe,p.game))
