from __future__ import annotations
import math
import re

IDENT=re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,79}$')
TYPES={'integer','real','boolean','string'}

def identifier(value):
    if not isinstance(value,str) or not IDENT.fullmatch(value):raise ValueError('无效标识符: '+str(value))
    return value

def scalar(value,kind):
    if kind=='integer' and type(value)==int and -2147483648<=value<=2147483647:return value
    if kind=='real' and type(value) in (int,float) and math.isfinite(value):return float(value)
    if kind=='boolean' and type(value)==bool:return value
    if kind=='string' and isinstance(value,str) and len(value.encode('utf8'))<=1024:return value
    raise ValueError('参数类型不符: '+kind)

def validate_catalog(catalog):
    if not isinstance(catalog,dict):raise ValueError('命令目录必须是对象')
    commands=catalog.get('commands',[]); fields=catalog.get('fields',[])
    if not 1<=len(commands)<=40 or not 1<=len(fields)<=80:raise ValueError('需提供1～40个命令和1～80个状态字段')
    ids=set()
    for c in commands:
        identifier(c['id']);identifier(c['function'])
        if c.get('entry_kind','function') not in {'function','trigger'}:raise ValueError('入口只支持函数或GUI触发器')
        if c.get('entry_kind')=='trigger':identifier(c['trigger'])
        if c['id'] in ids or c['id'] in {'ping','snapshot','discover'}:raise ValueError('重复或保留命令名')
        ids.add(c['id']); names=set()
        for p in c.get('params',[]):
            identifier(p['name'])
            if p['name'] in names or p['type'] not in TYPES:raise ValueError('无效参数定义')
            names.add(p['name']); scalar(p['default'],p['type'])
        if len(c.get('params',[]))>12:raise ValueError('命令参数过多')
    ids=set()
    for f in fields:
        identifier(f['id'])
        if f['id'] in ids:raise ValueError('重复状态字段')
        ids.add(f['id'])
        if f['type'] not in TYPES:raise ValueError('无效状态类型')
        if f['source']=='global':
            identifier(f['name'])
            if 'index' in f and not (type(f['index'])==int and 0<=f['index']<=8191):raise ValueError('无效数组索引')
        elif f['source'] not in {'gold','lumber','ticks'}:raise ValueError('仅支持全局变量、金币、木材和计时')
    return catalog

def validate_cases(cases,catalog):
    known={c['id'] for c in catalog['commands']}|{'ping','snapshot','discover'}
    if not isinstance(cases,list) or len(cases)>60:raise ValueError('用例列表无效')
    for case in cases:
        identifier(case['id'])
        if not 1<=len(case['steps'])<=80:raise ValueError('用例需要1～80步')
        if not any(s.get('type') in {'assert','wait'} for s in case['steps']):raise ValueError('用例缺少断言或等待判据，不能证明业务通过')
        for step in case['steps']:
            if step['type']=='command':
                if step['op'] not in known:raise ValueError('未知用例命令: '+step['op'])
                identifier(step.get('save_as','last'))
            elif step['type'] in {'assert','wait'}:
                if step['operator'] not in {'eq','ne','gt','ge','lt','le','exists'}:raise ValueError('无效比较操作')
                if not re.fullmatch(r'[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*|\.\d+)*',step['path']):raise ValueError('无效状态路径')
                if 'ref' in step and not re.fullmatch(r'[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*|\.\d+)*',step['ref']):raise ValueError('无效引用路径')
                if step['type']=='wait' and not 0<float(step.get('timeout',15))<=120:raise ValueError('等待上限120秒')
            else:raise ValueError('用例只允许命令、等待和断言')
    return cases
