from __future__ import annotations
from pathlib import Path
import re
from .schema import validate_catalog

def decode(data):
    try:return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:return data.decode('gb18030')
        except UnicodeDecodeError:return data.decode('utf8',errors='replace')

def index_script(script):
    clean=re.sub(r'//[^\n]*','',script)
    functions={}
    for m in re.finditer(r'(?m)^\s*function\s+(\w+)\s+takes\s+([^\n]+?)\s+returns\s+(\w+)\s*\n(.*?)^\s*endfunction',clean,re.S|re.M):
        name,takes,returns,body=m.groups(); params=[]
        if takes.strip()!='nothing':
            for arg in takes.split(','):
                parts=arg.split()
                if len(parts)!=2:break
                params.append({'type':parts[0],'name':parts[1]})
        functions[name]={'name':name,'params':params,'returns':returns,'body':body[:6000]}
    globals_={}
    for block in re.findall(r'(?ms)^\s*globals\s*\n(.*?)^\s*endglobals',clean):
        for m in re.finditer(r'(?m)^\s*(?:constant\s+)?(integer|real|boolean|string)\s+(array\s+)?(\w+)',block):
            kind,array,name=m.groups();globals_[name]={'type':kind,'array':bool(array)}
    triggers=re.findall(r'(?m)^\s*trigger\s+(gg_trg_\w+)',clean)
    return {'functions':functions,'globals':globals_,'triggers':triggers}

def check_mapping(catalog,index):
    validate_catalog(catalog)
    for c in catalog['commands']:
        if c['function'] in {'main','config'} or c['function'].startswith('WBT_'):
            raise ValueError('初始化或桥内部入口不能作为业务命令: '+c['function'])
        if c.get('entry_kind')=='trigger':
            if c.get('trigger') not in index.get('triggers',[]):raise ValueError('GUI触发器实例不存在: '+str(c.get('trigger')))
            if c.get('params'):raise ValueError('GUI触发器入口不能直接接受函数参数')
        f=index['functions'].get(c['function'])
        if f is None:raise ValueError('地图版本中没有业务函数: '+c['function'])
        if f['returns']!='nothing':raise ValueError('命令入口须返回nothing: '+c['function'])
        actual=[p['type'] for p in f['params']];expected=[p['type'] for p in c.get('params',[])]
        if actual!=expected:raise ValueError('业务入口参数已变化: '+c['function'])
        if 'string' in actual and re.search(r'\b(?:EXExecuteScript|ExecuteFunc|Cheat|Preloader)\s*\(',f['body']):
            raise ValueError('不能暴露解释脚本或动态函数名称的字符串入口: '+c['function'])
        if re.search(r'\b(?:GetTriggerUnit|GetTriggerPlayer|GetSpell\w+|GetAttacker|GetDyingUnit|GetEnteringUnit|GetManipulatedItem)\s*\(',f['body']):
            raise ValueError('入口依赖事件上下文，需要地图现有的正式包装入口: '+c['function'])
    for f in catalog['fields']:
        if f['source']=='global':
            g=index['globals'].get(f['name'])
            if not g or g['type']!=f['type'] or g['array']!=('index' in f):raise ValueError('状态字段缺失或类型变化: '+f['name'])

def context(index,goal,gui=None):
    words=[w.lower() for w in re.findall(r'[A-Za-z_][\w]+',goal)]
    scored=sorted(index['functions'].values(),key=lambda f:sum(w in (f['name']+' '+f['body']).lower() for w in words),reverse=True)
    signatures=[{k:v for k,v in f.items() if k!='body'} for f in scored[:150]]
    snippets=[{**f,'body':f['body'][:2000]} for f in scored[:8]]
    return {'goal':goal,'functions':signatures,'function_snippets':snippets,
            'globals':dict(list(index['globals'].items())[:200]),'triggers':index.get('triggers',[])[:150],'gui':gui or {},
            'boundary':'单真人本机LAN；只有已存在的标量参数业务函数；不生成任意代码；不能使用需要触发事件上下文的动作函数。'}
