"""Optional deterministic runner for scripts/CI; no model connection required."""
import argparse
import json
from pathlib import Path
import threading
import uuid
from .storage import read,save
from .backend import Backend
from .testing import run_cases

def main(argv):
    p=argparse.ArgumentParser();p.add_argument('project');p.add_argument('--case',action='append');p.add_argument('--tag');p.add_argument('--output');p.add_argument('--allow-map-copy',action='store_true');p.add_argument('--allow-game-launch',action='store_true');a=p.parse_args(argv)
    if not a.allow_map_copy or not a.allow_game_launch:p.error('创建测试副本与游戏启动须分别使用 --allow-map-copy --allow-game-launch')
    project=read(a.project);project['directory']=str(Path(a.project).resolve().parent);backend=Backend(project)
    cases=[c for c in project['cases'] if (not a.case or c['id'] in a.case) and (not a.tag or a.tag in c.get('tags',[]))]
    if not cases:p.error('没有匹配的用例')
    output=Path(a.output or str(Path(project['directory'])/'reports'/uuid.uuid4().hex))
    session=None
    try:
        session=backend.prepare(project['catalog']);backend.launch(session)
        report=run_cases(backend,session,cases,project['catalog'],output)
        return 0 if report['status']=='passed' else 1
    except Exception as exc:
        cleanup={}
        if session:
            try:cleanup=backend.shutdown(session)
            except Exception as e:cleanup={'ok':False,'error':str(e)}
        save(output/'failure.json',{'ok':False,'error':str(exc),'cleanup':cleanup});return 1
