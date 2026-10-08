"""Local War3 1.27a test bridge. Python 3.10+, standard library only.

Only build-demo creates a new map. Launch defaults to windowed one-client KKWE LAN.
Shutdown signals only the owners of this session's game and host process handles.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import msvcrt
import os
import shutil
from pathlib import Path
import statistics
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
import lan_support

ROOT = Path(__file__).resolve().parent
CONFIG_PATH=ROOT / 'config.json'
CONFIG=json.loads(CONFIG_PATH.read_text(encoding='utf8')) if CONFIG_PATH.exists() else {}
KKWE=Path(os.environ.get('WAR3_BRIDGE_KKWE') or CONFIG.get('kkwe') or ROOT/'UNCONFIGURED_KKWE')
TOOLS=Path(os.environ.get('WAR3_BRIDGE_TOOLS') or CONFIG.get('tools') or ROOT/'optional-tools')
TEMPLATE=Path(os.environ.get('WAR3_BRIDGE_TEMPLATE') or CONFIG.get('template') or ROOT/'UNCONFIGURED_TEMPLATE.w3x')
SCRATCH=ROOT/'work'
if CONFIG.get('game') and not os.environ.get('WAR3_BRIDGE_GAME'):
    os.environ['WAR3_BRIDGE_GAME']=CONFIG['game']



def save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


def atomic_write(path: Path, data: bytes):
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(data)
    # Lua briefly opens the destination without FILE_SHARE_DELETE on Windows.
    # Retry publication of the same complete payload, never partially rewrite it.
    deadline=time.perf_counter()+.5
    while True:
        try:
            os.replace(temp,path)
            return
        except PermissionError:
            if time.perf_counter()>=deadline: raise
            time.sleep(.003)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def run_checked(argv, *, cwd=None):
    proc = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    result = {"command": [str(x) for x in argv], "exit_code": proc.returncode,
              "stdout": proc.stdout.decode("utf-8", errors="replace"),
              "stderr": proc.stderr.decode("utf-8", errors="replace")}
    if proc.returncode:
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


def processes():
    script = """[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new();
Get-CimInstance Win32_Process -Filter "Name = 'war3.exe' OR Name = 'Warcraft III.exe'" |
ForEach-Object { [PSCustomObject]@{pid=$_.ProcessId;parent=$_.ParentProcessId;path=$_.ExecutablePath;command=$_.CommandLine;created=$_.CreationDate.ToUniversalTime().ToString('o')} } |
ConvertTo-Json -Compress"""
    p = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    if p.returncode:
        raise RuntimeError(p.stderr.decode("utf-8", errors="replace"))
    s = p.stdout.decode("utf-8-sig", errors="replace").strip()
    if not s:
        return []
    value = json.loads(s)
    return value if isinstance(value, list) else [value]


def file_version(path: Path):
    dll = ctypes.WinDLL("version", use_last_error=True)
    dll.GetFileVersionInfoSizeW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_uint32)]
    size = dll.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return None
    data = ctypes.create_string_buffer(size)
    dll.GetFileVersionInfoW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    if not dll.GetFileVersionInfoW(str(path), 0, size, data):
        return None
    pointer = ctypes.c_void_p(); length = ctypes.c_uint32()
    dll.VerQueryValueW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32)]
    if not dll.VerQueryValueW(data, "\\", ctypes.byref(pointer), ctypes.byref(length)):
        return None
    fields = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))
    hi, lo = fields[2], fields[3]
    return f"{hi >> 16}.{hi & 65535}.{lo >> 16}.{lo & 65535}"


def doctor():
    import winreg
    local_files=False;registry_game=''
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Blizzard Entertainment\Warcraft III') as key:
            try:registry_game=winreg.QueryValueEx(key,'InstallPath')[0]
            except FileNotFoundError:pass
            try:local_files=winreg.QueryValueEx(key,'Allow Local Files')[0]!=0
            except FileNotFoundError:pass
    except FileNotFoundError:pass
    game=Path(os.environ.get('WAR3_BRIDGE_GAME') or registry_game or ROOT/'UNCONFIGURED_GAME')
    required = [KKWE / "bin/YDWEConfig.exe", KKWE / "plugin/warcraft3/yd_loader.dll",
                KKWE / "plugin/warcraft3/yd_lua_engine.dll", TEMPLATE,
                KKWE / "plugin/pjass/pjass-latest.exe", KKWE / "plugin/jasshelper/common.j",
                KKWE / "plugin/jasshelper/blizzard.j", KKWE / "bin/luacore.dll",
                KKWE / "bin/modules/sys.dll", KKWE / "bin/modules/filesystem.dll",
                KKWE / "bin/modules/maphash.dll", KKWE / "plugin/ydhost/ydhost.exe",
                KKWE / "plugin/w3x2lni_zhCN_v2.7.3/bin/w3x2lni-lua.exe",
                game / "Game.dll", game / "war3.exe"]
    missing = [str(p) for p in required if not p.is_file()]
    version = file_version(game / "Game.dll") if (game / "Game.dll").is_file() else None
    result = {"ok": not missing and local_files and version == "1.27.0.52240", "game_directory": str(game),
              "game_version": version, "kkwe_directory": str(KKWE), "missing": missing,
              "allow_local_files": local_files,
              "running_games": processes(), "runtime_capabilities": "require real-game bootstrap"}
    return result


def lua_string(data: bytes):
    # ASCII-only source: all non-ASCII path bytes are explicit Lua decimal escapes.
    return '"' + ''.join(chr(b) if 32 <= b <= 126 and b not in (34, 92)
                         else "\\%03d" % b for b in data) + '"'


def short_path(path: Path):
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.GetShortPathNameW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint32]
    buffer=ctypes.create_unicode_buffer(32768)
    size=kernel.GetShortPathNameW(str(path),buffer,len(buffer))
    return buffer.value if 0<size<len(buffer) else str(path)


def jass_string(text: str):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n") + '"'


def build_demo(probe_only=False):
    environment = doctor()
    if not environment["ok"]:
        raise RuntimeError(json.dumps(environment, ensure_ascii=False))
    if (TOOLS/'ai_workflow/kkwe_ai.py').is_file():
        preflight=run_checked([sys.executable,TOOLS/'ai_workflow/kkwe_ai.py','preflight','w3x_mpq_file_patch'])
    elif CONFIG.get('tools') or os.environ.get('WAR3_BRIDGE_TOOLS'):
        raise RuntimeError('Configured tool preflight is missing; do not bypass project gates')
    else:
        preflight={'ok':True,'scope':'Standalone bundled demo: doctor component checks; packer performs member readback. Existing project gates still apply.'}
    host_source=ROOT / "src/KkweLuaHost.cs";host=ROOT / "KkweLuaHost.exe"
    if not host.exists() or host.stat().st_mtime<host_source.stat().st_mtime:
        run_checked([Path(os.environ.get("WINDIR",r"C:\Windows"))/"Microsoft.NET/Framework/v4.0.30319/csc.exe","/nologo","/platform:x86","/out:"+str(host),host_source])
    session = uuid.uuid4().hex
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = ROOT / "runs" / f"{stamp}-{session[:8]}"
    folder.mkdir(parents=True)
    # The embedded YDWE IO layer permits writes only below the game root.
    game = Path(environment["game_directory"])
    ipc = game / "WBTestBridge" / session
    ipc.mkdir(parents=True)
    (ipc / "probe.txt").write_text(session, encoding="ascii")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    scratch = SCRATCH / session; scratch.mkdir()
    path = str(ipc).replace("\\", "/")
    candidates = [("game-relative-utf8", ipc.relative_to(game).as_posix().encode("utf-8")),
                  ("windows-short-path", short_path(ipc).replace("\\", "/").encode("utf-8")),
                  ("utf-8", path.encode("utf-8")), ("windows-acp", path.encode("mbcs"))]
    paths = '{' + ','.join('{path=' + lua_string(p) + ',encoding=' + lua_string(enc.encode()) + '}' for enc,p in candidates) + '}'
    build = "wb1-" + session[:12]
    lua = (ROOT / "src/bridge.lua").read_text(encoding="utf-8")
    lua = lua.replace("__JSON_CODEC__", (ROOT / "src/json.lua").read_text(encoding="utf-8"))
    lua = lua.replace("__SESSION__", lua_string(session.encode())).replace("__BUILD__", lua_string(build.encode())).replace("__PATHS__", paths)
    lua = "local ok,result=pcall(function()\n"+lua+"\nend);if ok then return result else return {status='bootstrap_error: '..tostring(result)} end\n"
    # Load trusted source as an MPQ module; requests never contain executable code.
    generated=folder / "bridge.generated.lua"
    generated.write_text(lua,encoding="ascii")
    statements = ['    call WB_Mark("module-before", "exec-lua module requested")',
                  '    call Cheat("exec-lua:War3TestBridge")',
                  '    call WB_Mark("module-after", "exec-lua module call returned")',
                  '    set WB_LastError = EXExecuteScript("(require\'War3TestBridge\').status")']
    script = (ROOT / "src/map.j.template").read_text(encoding="utf-8")
    probe_path=lua_string(short_path(ipc / "probe.txt").replace("\\", "/").encode("mbcs"))
    probes=[]
    if probe_only:
        for stage,expr in [('lua-version','_VERSION'),('io-type','type(io)'),('io-open-type','type(io and io.open)'),('load-type','type(load)'),('file-open','tostring(io.open('+probe_path+",'rb'))")]:
            probes+=['    set WB_LastError = EXExecuteScript('+jass_string(expr)+')','    call WB_Mark('+jass_string(stage)+', WB_LastError)']
        statements=['    set WB_LastError = "probe_only_done"']
    script=script.replace("__IO_PROBE__",'\n'.join(probes))
    script = script.replace("__BOOTSTRAP__", '\n'.join(statements)).replace("__BUILD_TEXT__", build)
    script_path = folder / "war3map.j"; script_path.write_text(script, encoding="ascii")
    (folder / "bridge.generated.lua").write_text(lua, encoding="ascii")
    compiler = run_checked([KKWE / "plugin/pjass/pjass-latest.exe", KKWE / "plugin/jasshelper/common.j",
                            KKWE / "plugin/jasshelper/blizzard.j", script_path])
    map_path = folder / ("wb-"+session[:8]+".w3x")
    runtime = KKWE / "plugin/w3x2lni_zhCN_v2.7.3"
    expr = "_W2L_MODE='CLI';package.path=[["+runtime.as_posix()+"/script/?.lua;"+runtime.as_posix()+"/script/?/init.lua]];package.cpath=[["+runtime.as_posix()+"/bin/?.dll]]"
    partial = map_path.with_suffix(".partial")
    shutil.copy2(TEMPLATE, partial)
    patch = run_checked([runtime / "bin/w3x2lni-lua.exe", "-E", "-e", expr,
                         ROOT / "src/pack_demo.lua", TEMPLATE, partial, script_path, scratch, generated])
    partial.rename(map_path)
    manifest = {"session": session, "build": build, "folder": str(folder), "ipc": str(ipc),
                "map": str(map_path), "launch_map":str(Path(short_path(map_path.parent))/map_path.name),"probe_only":probe_only,"template": str(TEMPLATE), "environment": environment,
                "preflight": preflight, "compiler": compiler, "archive_verification": json.loads(patch["stdout"])}
    save_json(folder / "session.json", manifest)
    save_json(ROOT / "latest.json", {"session_file": str(folder / "session.json")})
    return manifest


def load_session(path=None):
    p = Path(path) if path else Path(read_json(ROOT / "latest.json")["session_file"])
    session = read_json(p)
    # Never let a supplied manifest make shutdown operate outside our delivered runs.
    if not Path(session["folder"]).resolve().is_relative_to((ROOT / "runs").resolve()):
        raise ValueError("session outside owned runs directory")
    return session


def owned_processes(session):
    wanted = [str(Path(session["map"]).resolve()).casefold(),session.get("launch_map",session["map"]).casefold()]
    launch_file=Path(session["folder"])/"launch.json"
    recorded=read_json(launch_file).get("processes",[]) if launch_file.exists() else []
    return [p for p in processes() if any(w in (p.get("command") or "").casefold() for w in wanted)
            or any(p["pid"]==r["pid"] and p["created"]==r["created"] for r in recorded)]


def launch(session, mode="lan"):
    # Reject reuse before entering cleanup: a second launch must not stop a live session.
    folder=Path(session['folder']);ipc=Path(session['ipc'])
    if (folder/'launch.json').exists() or (folder/'launch-failure.json').exists() or (ipc/'hello.json').exists() or owned_processes(session):
        raise RuntimeError('session already launched or attempted; build-demo creates a fresh session')
    if mode=="lan" and processes():
        raise RuntimeError("LAN auto-join needs an isolated game session; another War3 is already running")
    try:
        if mode=="lan":
            with lan_support.temporary_player_name(session):return _launch(session,mode)
        return _launch(session,mode)
    except Exception as exc:
        # Only these session owners can act on retained native process handles.
        atomic_write(Path(session['ipc'])/'launcher.stop',b'stop')
        cleanup=None
        try:cleanup=lan_support.stop_host(session)
        except Exception as stop_error:cleanup={'error':str(stop_error)}
        save_json(Path(session['folder'])/'launch-failure.json',{'error':str(exc),'host_cleanup':cleanup})
        raise


def _launch(session, mode):
    folder = Path(session["folder"]); ipc = Path(session["ipc"])
    if (ipc / "hello.json").exists() or owned_processes(session):
        raise RuntimeError("session already launched; build-demo creates a fresh session")
    before={p["pid"] for p in processes()}
    game=Path(session["environment"]["game_directory"])
    # Warcraft's classic loader reliably resolves map paths relative to its root.
    runtime_map=game / "Maps/Test" / Path(session["map"]).name
    if runtime_map.exists(): raise RuntimeError("owned runtime map path already exists")
    shutil.copy2(session["map"],runtime_map)
    session["runtime_map"]=str(runtime_map)
    session["launch_map"]=str(runtime_map.relative_to(game))
    session["launch_mode"]=mode
    save_json(folder/"session.json",session)
    started=time.perf_counter()
    host=lan_support.start_host(session,ROOT,KKWE,run_checked) if mode=="lan" else None
    # Classic arguments must precede loader-only arguments. In 1.27a an
    # unknown leading -auto causes the later -window to be ignored.
    route='' if mode=="lan" else ' -loadfile "'+session["launch_map"]+'"'
    game_command='"'+str(game/"war3.exe")+'" -window'+route+' -kkwe "'+str(KKWE)+'"'
    command=[str(ROOT/"KkweLuaHost.exe"),str(KKWE/"bin"),str(ROOT/"src/kkwe_launcher.lua"),str(game),game_command,str(KKWE/"plugin/warcraft3/yd_loader.dll"),str(ipc)]
    # The loader creates the game. It is not the process later terminated by shutdown.
    log=(folder/"launcher.log").open("wb");errors=(folder/"launcher-errors.log").open("wb")
    launcher = subprocess.Popen(command,cwd=game,stdout=log,stderr=errors,creationflags=0x08000000)
    log.close();errors.close()
    result = {"backend":"kkwe_sys_spawn_inject","command":command,"game_command":game_command,"loader":str(KKWE/"plugin/warcraft3/yd_loader.dll"),"launcher_pid":launcher.pid,"processes":[],"started_at":datetime.now(timezone.utc).isoformat()}
    result.update(launch_mode=mode,lan_host=host)
    last_scan=0
    print("Waiting for real-game ready handshake (up to 90 seconds)...", flush=True)
    deadline = started + 90
    while time.perf_counter() < deadline:
        if time.perf_counter()-last_scan>3:
            last_scan=time.perf_counter()
            returned_pid=launcher.poll()
            result["launcher_return"]=returned_pid
            if returned_pid is not None:
                result.update(ok=False,failure_stage="kkwe_launcher_helper",helper_error=(folder/"launcher-errors.log").read_text(encoding="utf-8-sig",errors="replace"))
                save_json(folder/"launch.json",result)
                raise RuntimeError("KKWE launcher helper exited: "+result["helper_error"])
            for p in processes():
                if p["pid"] not in before and (p.get("parent")==launcher.pid or (returned_pid and (p["pid"]==returned_pid or p.get("parent")==returned_pid))):
                    if p.get("path") and str(Path(p["path"]).parent).casefold()!=session["environment"]["game_directory"].casefold():
                        continue
                    if not any(old["pid"]==p["pid"] for old in result["processes"]):
                        p["ownership"]="observed KKWE launcher child/restarted child"
                        result["processes"].append(p)
            save_json(folder / "launch.json",result)
        try:
            if mode=="lan":
                host_text=lan_support.host_log(session)
                result['lan_joined']='player [WB'+session['session'][:8]+'|' in host_text and ' joined the game' in host_text
                result['lan_loading']=' started loading with 1 players' in host_text
                if not result['lan_joined'] or not result['lan_loading']:
                    time.sleep(.1);continue
            identity=read_json(ipc / "game-process.json")
            result["game_identity"]=identity
            actual=identity.get("actual_executable")
            result["process_identity_verified"]=bool(actual) and Path(actual).resolve()==(game/"war3.exe").resolve()
            if actual and not result["process_identity_verified"]:
                raise RuntimeError("launched executable differs from configured client")
            hello = read_json(ipc / "hello.json")
            if hello.get("session") == session["session"] and hello.get("build") == session["build"] and hello.get("stage") == "ready":
                result["hello"]=hello
                # A module handshake precedes timer startup. Prove the timer can
                # actually execute a request before reporting readiness.
                try:
                    ping,elapsed=Client(session).request("ping",request_id="launch-ready")
                except TimeoutError as exc:
                    result["timer_wait"]=str(exc)
                else:
                    from background_probe import BackgroundProbe
                    window_probe=BackgroundProbe(identity['pid'])
                    try:result['window']=window_probe.geometry()
                    finally:window_probe.finish()
                    if not result['window']['has_caption']:
                        result.update(ok=False,failure_stage='windowed_mode_not_observed')
                        save_json(folder/'launch.json',result)
                        raise RuntimeError('expected a captioned War3 window; actual style: '+result['window']['style'])
                    result.update(ok=True,ready_seconds=time.perf_counter()-started,
                                  ready_ping=ping,ready_ping_ms=elapsed)
                    save_json(folder / "launch.json", result)
                    return result
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(.1)
    stages={p.stem:p.read_text(encoding="utf-8",errors="replace") for p in (game/"Logs").glob("WB-"+session["build"]+"-*.pld")}
    result.update(ok=False, ready_seconds=time.perf_counter()-started,
                  failure_stage="lua_or_map_bootstrap" if stages else "map_main_not_observed", stages=stages,
                  bootstrap=read_json(ipc / "bootstrap.json") if (ipc / "bootstrap.json").exists() else None)
    if result.get("hello"):
        result["failure_stage"]="game_timer_not_responding"
    if mode=="lan" and not result.get('lan_loading'):
        result['failure_stage']='lan_loading_not_observed' if result.get('lan_joined') else 'lan_join_not_observed'
    save_json(folder / "launch.json", result)
    raise RuntimeError("Game handshake failed; diagnostics saved to " + str(folder / "launch.json"))


class Client:
    def __init__(self, session):
        self.session = session; self.ipc = Path(session["ipc"])
        hello = read_json(self.ipc / "hello.json")
        if hello.get("session") != session["session"] or hello.get("build") != session["build"]:
            raise RuntimeError("stale or wrong game handshake")
        seq_path = self.ipc / "request.ready"
        self.sequence = int(seq_path.read_text()) if seq_path.exists() else 0

    def exchange(self, payload: bytes, timeout=3.0):
        # Serialize different CLI processes; never overwrite an outstanding request.
        with (self.ipc / "client.lock").open("a+b") as lock:
            lock.seek(0);lock.write(b"0");lock.flush();lock.seek(0)
            lock_deadline=time.perf_counter()+3
            while True:
                try:
                    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);break
                except OSError:
                    if time.perf_counter()>=lock_deadline:raise TimeoutError("another bridge client holds the transport")
                    time.sleep(.01)
            try:return self._exchange_locked(payload,timeout)
            finally:
                lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

    def _exchange_locked(self,payload,timeout):
        previous=self.ipc / "request.ready"
        self.sequence=int(previous.read_text()) if previous.exists() else 0
        pending_deadline=time.perf_counter()+3
        while self.sequence:
            response_ready=self.ipc / "response.ready"
            if response_ready.exists() and response_ready.read_text()==str(self.sequence):break
            if time.perf_counter()>=pending_deadline:raise TimeoutError("previous request is still in flight; refusing overwrite")
            time.sleep(.003)
        self.sequence += 1; seq = str(self.sequence)
        start = time.perf_counter()
        atomic_write(self.ipc / "request.json", payload)
        atomic_write(self.ipc / "request.ready", seq.encode("ascii"))
        deadline = start + timeout
        while time.perf_counter() < deadline:
            try:
                if (self.ipc / "response.ready").read_text(encoding="ascii") == seq:
                    response = read_json(self.ipc / "response.json")
                    if response.get("session") != self.session["session"] or response.get("build") != self.session["build"]:
                        raise RuntimeError("wrong-session response")
                    return response, (time.perf_counter()-start)*1000
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            time.sleep(.003)
        raise TimeoutError(f"No response for transport sequence {seq} within {timeout}s")

    def request(self, op, args=None, request_id=None, expected_error=False):
        req = {"session": self.session["session"], "id": request_id or uuid.uuid4().hex, "op": op}
        if args is not None: req["args"] = args
        response, elapsed = self.exchange(json.dumps(req, ensure_ascii=False).encode("utf-8"))
        if not expected_error and not response.get("ok"):
            raise RuntimeError(json.dumps(response, ensure_ascii=False))
        return response, elapsed


def require(condition, message):
    if not condition: raise AssertionError(message)


def summary(values):
    ordered = sorted(values)
    return {"count": len(values), "median_ms": statistics.median(values),
            "p95_ms": ordered[math.ceil(len(ordered)*.95)-1], "max_ms": max(values)}


def run_suite(session, require_background=False, require_minimized=False):
    client = Client(session); folder = Path(session["folder"])
    run_id=uuid.uuid4().hex[:12]
    report = {"session": session["session"], "build": session["build"], "map": session["map"],
              "run_id":run_id,"started_at": datetime.now(timezone.utc).isoformat(), "checks": [], "rounds": [], "ok": False}
    probe=None
    def finish_probe():
        nonlocal probe
        if probe is None:return
        measured=probe.finish();probe=None
        trace=folder/('background-'+run_id+'.json')
        save_json(trace,measured)
        report['background']={k:v for k,v in measured.items() if k!='samples'}
        report['background']['trace']=str(trace)
    def persist():
        save_json(folder / ("suite-"+run_id+".json"),report)
        save_json(folder / "report.json",report)
    def check(name, condition, evidence):
        report["checks"].append({"name": name, "passed": bool(condition), "evidence": evidence})
        persist()
        require(condition, name)
    try:
        launch_record=read_json(folder / "launch.json")
        report["launch"]=launch_record
        if require_background or require_minimized:
            from background_probe import BackgroundProbe
            require(launch_record.get('launch_mode')=='lan','background verification requires LAN launch')
            probe=BackgroundProbe(launch_record['game_identity']['pid'])
            require(not probe.samples[0]['game_foreground'],'put another window in front before background run')
            if require_minimized:require(probe.samples[0]['minimized'],'minimize the game before minimized run')
        start_state,_=client.request('ping')
        simulation_start=time.perf_counter()
        check("actual executable verified",launch_record.get("process_identity_verified"),launch_record.get("game_identity"))
        hello = read_json(Path(session["ipc"]) / "hello.json")
        check("real-game handshake", hello["file_io"] and hello["jass_globals"], hello)
        client.request("reset")
        r,_ = client.request("not_a_command", expected_error=True)
        check("unknown command rejected", not r["ok"] and "unknown_operation" in r["error"],r)
        r,_ = client.request("order",{"command":"delete_all"},expected_error=True)
        check("invalid order rejected",not r["ok"] and "unsupported_order" in r["error"],r)
        r,_ = client.request("order",{"command":"attack"},expected_error=True)
        check("unprepared order rejected",not r["ok"] and "scenario_not_prepared" in r["error"],r)
        r,_ = client.exchange(b'{"broken":')
        check("malformed JSON rejected",not r["ok"],r)
        r,_ = client.exchange(b'{"value":1.e2}')
        check("malformed number rejected",not r["ok"] and "missing fraction" in r["error"],r)
        wrong={"session":"old-session","id":"stale","op":"reset"}
        r,_=client.exchange(json.dumps(wrong).encode())
        check("stale session rejected",not r["ok"] and "wrong_session" in r["error"],r)
        ping,_=client.request("ping")
        check("bridge survives bad requests",ping["ok"],ping)
        unicode_id=run_id+"-中文验证"
        r,_=client.request("ping",request_id=unicode_id)
        check("UTF-8 request ID roundtrip",r.get("id")==unicode_id,r)
        timeout_seen=False
        try:
            client.exchange(json.dumps({"session":session["session"],"id":run_id+"-tiny-timeout","op":"snapshot"}).encode(),timeout=.000001)
        except TimeoutError: timeout_seen=True
        # The command remains in flight after caller timeout: wait for its response before publishing another.
        time.sleep(.2)
        r,_=client.request("ping")
        check("timeout recovery",timeout_seen and r["ok"],r)
        latencies=[]
        for _ in range(100):
            _,elapsed=client.request("snapshot");latencies.append(elapsed)
        report["snapshot_latency"]=summary(latencies)
        report["snapshot_latency"]["samples_ms"]=latencies
        prep_times=[];reset_times=[];order_times=[]
        for round_no in range(1,21):
            prefix=f"{run_id}-{round_no}"
            evidence={"round":round_no,"passed":False}
            report["rounds"].append(evidence)
            persist()
            prepared,elapsed=client.request("prepare",request_id=prefix+"-prepare");prep_times.append(elapsed)
            initial=prepared["result"]
            evidence["initial"]=initial;evidence["prepare_ms"]=elapsed
            require(initial["observed_map_units"]==2 and initial["gold"]==0 and initial["deaths"]==0 and initial["active_death_triggers"]==1,"dirty prepared scene")
            require(initial["actor"]["type_id"]==int.from_bytes(b'Hpal','big') and initial["target"]["type_id"]==int.from_bytes(b'hfoo','big'),"rawcode integer precision lost")
            time.sleep(.35)
            before_order,_=client.request("snapshot")
            evidence["before_order"]=before_order["result"]
            # Paused stock units still regenerate HP; only a decrease is damage.
            before=before_order["result"]
            require(before["actor"]["paused"] and before["target"]["life"]>=initial["target"]["life"] and before["deaths"]==0 and before["actor"]["x"]==initial["actor"]["x"] and before["actor"]["y"]==initial["actor"]["y"],"combat began before explicit order")
            duplicate,_=client.request("prepare",request_id=prefix+"-prepare")
            evidence["duplicate_prepare"]=duplicate
            require(duplicate["replayed"] and duplicate["result"]["round"]==initial["round"],"duplicate prepare executed")
            conflict={"session":session["session"],"id":prefix+"-prepare","op":"reset"}
            conflict_result,_=client.exchange(json.dumps(conflict).encode())
            evidence["conflict_rejected"]=conflict_result
            require(not conflict_result["ok"] and "request_id_conflict" in conflict_result["error"],"conflicting request ID accepted")
            started=time.perf_counter()
            ordered,elapsed=client.request("order",{"command":"attack"},request_id=prefix+"-attack");order_times.append(elapsed)
            evidence["order_ms"]=elapsed;evidence["ordered"]=ordered
            require(ordered["result"]["order_accepted"],"attack order rejected")
            samples=[];decreased=False;final=None
            evidence["samples"]=samples
            while time.perf_counter()-started<15:
                r,_=client.request("snapshot");state=r["result"]
                life=state["target"].get("life",0)
                if 0<life<initial["target"]["life"]:decreased=True
                if not samples or life!=samples[-1]["life"]:
                    samples.append({"elapsed_s":time.perf_counter()-started,"life":life,"gold":state["gold"],"deaths":state["deaths"],"rewards":state["rewards"]})
                if state["deaths"]:
                    final=state;break
                time.sleep(.04)
            evidence["combat_seconds"]=time.perf_counter()-started
            evidence["final"]=final
            require(final is not None,"attack did not produce target death")
            require(decreased,"no observed nonfatal life decrease")
            require(final["gold"]==100 and final["deaths"]==1 and final["rewards"]==1,"incorrect death reward")
            replay,_=client.request("order",{"command":"attack"},request_id=prefix+"-attack")
            evidence["duplicate_order"]=replay
            require(replay["replayed"],"duplicate order not replayed")
            client.request("order",{"command":"attack"})
            time.sleep(.1)
            after,_=client.request("snapshot")
            evidence["after_repeat"]=after["result"]
            require(after["result"]["gold"]==100 and after["result"]["deaths"]==1 and after["result"]["rewards"]==1,"dead-target repeat rewarded")
            reset,elapsed=client.request("reset");reset_times.append(elapsed)
            clean=reset["result"]
            evidence["reset"]=clean;evidence["reset_ms"]=elapsed
            require(clean["observed_map_units"]==0 and clean["live_test_units"]==0 and not clean["actor"]["exists"] and not clean["target"]["exists"],"units remained after reset")
            require(clean["active_death_triggers"]==0 and clean["triggers_created"]==clean["triggers_destroyed"],"death trigger lifecycle unbalanced")
            evidence["passed"]=True
            print(f"Round {round_no}/20 passed",flush=True)
            persist()
        report["prepare_latency"]=summary(prep_times);report["reset_latency"]=summary(reset_times)
        report["order_latency"]=summary(order_times)
        report["response_target_met"]=all(report[k]["p95_ms"]<=250 for k in ("snapshot_latency","prepare_latency","reset_latency","order_latency"))
        require(report["response_target_met"],"response P95 exceeds 250ms target")
        end_state,_=client.request('ping')
        progress={'wall_seconds':time.perf_counter()-simulation_start,
                  'game_seconds':end_state['result']['game_seconds']-start_state['result']['game_seconds'],
                  'ticks':end_state['result']['ticks']-start_state['result']['ticks']}
        report['simulation_progress']=progress
        require(progress['ticks']>0 and progress['game_seconds']>0,'game clock did not advance')
        if probe:
            finish_probe();bg=report['background']
            check('background throughout sampled run',bg['foreground_samples']==0 and bg['unknown_foreground_samples']==0
                  and bg['missing_window_samples']==0 and not bg['errors'],{k:v for k,v in bg.items() if k!='trace'})
            if require_minimized:check('minimized throughout sampled run',bg['minimized_samples']==bg['sample_count'],bg)
        report["ok"]=True
    except Exception as exc:
        report["error"]=str(exc)
        raise
    finally:
        finish_probe()
        report["finished_at"]=datetime.now(timezone.utc).isoformat()
        persist()
    return report


def shutdown_native(session):
    folder=Path(session["folder"]); ipc=Path(session["ipc"])
    launch_file=folder/"launch.json"
    if not launch_file.exists(): raise RuntimeError("no recorded launch")
    record=read_json(launch_file)
    if record.get("backend")!="kkwe_sys_spawn_inject":
        raise RuntimeError("no retained KKWE process owner for this session")
    live=owned_processes(session)
    if live:
        atomic_write(ipc/"launcher.stop",b"stop")
        deadline=time.perf_counter()+10
        while time.perf_counter()<deadline:
            if not owned_processes(session): break
            time.sleep(.2)
        else: raise RuntimeError("owned game did not exit through its retained handle")
    host_closed=lan_support.stop_host(session)
    if ipc.exists(): shutil.copytree(ipc,folder/"ipc-evidence",dirs_exist_ok=True)
    diagnostics=folder/"diagnostics";diagnostics.mkdir(exist_ok=True)
    game=Path(session["environment"]["game_directory"])
    for marker in (game/"Logs").glob("WB-"+session["build"]+"-*.pld"):
        shutil.copy2(marker,diagnostics/marker.name)
    result={"ok":True,"closed":live,"method":"KKWE retained process handle",
            "host_closed":host_closed,
            "evidence":str(folder/"ipc-evidence"),"finished_at":datetime.now(timezone.utc).isoformat()}
    save_json(folder/"shutdown.json",result)
    return result


def main():
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["doctor","build-demo","launch","run","shutdown","request"])
    parser.add_argument("--session",help="session.json; defaults to latest.json")
    parser.add_argument("--op",choices=["ping","prepare","order","snapshot","reset"],default="ping")
    parser.add_argument("--probe-only",action="store_true",help="build a diagnostic native/IO probe map")
    parser.add_argument("--mode",choices=["lan","single"],default="lan",help="LAN runs while unfocused; single is the original comparison mode")
    parser.add_argument("--require-background",action="store_true",help="fail unless game stays unfocused during sampled regression")
    parser.add_argument("--require-minimized",action="store_true",help="also require game to stay minimized")
    parser.add_argument("--keep-open",action="store_true",help="Retain the owned game/host only when explicitly requested")
    parser.add_argument('--i-confirm-map-write',action='store_true',help='Explicit authorization to create demo and runtime map copies')
    parser.add_argument('--i-confirm-game-launch',action='store_true',help='Explicit authorization to launch the owned test game')
    args=parser.parse_args()
    if args.command=='build-demo' and not args.i_confirm_map_write:
        parser.error('build-demo requires --i-confirm-map-write')
    if args.command=='launch' and not (args.i_confirm_map_write and args.i_confirm_game_launch):
        parser.error('launch copies a map and starts the game; both explicit confirmation flags are required')
    try:
        if args.command=="doctor":result=doctor()
        elif args.command=="build-demo":result=build_demo(args.probe_only)
        else:
            s=load_session(args.session)
            if args.command=="launch":
                s['file_view']=CONFIG.get('file_view','native')
                result=launch_local_session(s,args.mode)
            elif args.command=="run":
                try:
                    report=run_suite(s,args.require_background,args.require_minimized)
                finally:
                    if not args.keep_open:
                        shutdown(s)
                result={k:report[k] for k in ("ok","run_id","snapshot_latency","prepare_latency","reset_latency","order_latency","response_target_met")}
                result["snapshot_latency"]={k:v for k,v in result["snapshot_latency"].items() if k!="samples_ms"}
                result["passed_rounds"]=sum(r["passed"] for r in report["rounds"])
                if 'background' in report:result['background']=report['background']
                result['simulation_progress']=report['simulation_progress']
                result["report"]=str(Path(s["folder"])/"report.json")
            elif args.command=="shutdown":result=shutdown(s)
            else:result=Client(s).request(args.op,{"command":"attack"} if args.op=="order" else None)[0]
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result.get("ok",True) else 1
    except Exception as exc:
        print(str(exc),file=sys.stderr);return 1





def shutdown(session):
    from session_lifecycle import cleanup_owned
    return cleanup_owned(session,shutdown_native)

def launch_local_session(session,mode):
    from session_lifecycle import begin_launch,mark_phase
    begin_launch(session)
    if mode!='lan':
        mark_phase(session,'starting');result=launch(session,mode)
        if result.get('ok'):mark_phase(session,'ready')
        return result
    from desktop_probe import probe,require_lan_desktop
    from lan_startup_guard import startup_lease,local_products,require_no_products
    from lan_discovery import LocalDiscovery
    from owned_bootstrap import OwnedBootstrap
    from owned_network import udp_ports
    bootstrap=OwnedBootstrap(session['ipc'],session['session'],lan_ready=lambda pid:bool(udp_ports(pid)))
    original_log=lan_support.host_log
    def observed_log(active_session):
        bootstrap.tick()
        return original_log(active_session)
    desktop=probe();save_json(Path(session['folder'])/'desktop-preflight.json',desktop)
    require_lan_desktop(desktop)
    environment=doctor()
    with startup_lease(environment['game_directory']):
        products=local_products()
        save_json(Path(session['folder'])/'lan-isolation-preflight.json',{'competing_products':products})
        require_no_products(products)
        discovery=LocalDiscovery(session);original=lan_support.start_host
        lan_support.start_host=lambda *params:discovery.start_host(original,*params)
        mark_phase(session,'starting')
        lan_support.host_log=observed_log
        try:
            result=launch(session,mode)
            if result.get('ok'):mark_phase(session,'ready')
            return result
        finally:
            discovery.close();lan_support.start_host=original;lan_support.host_log=original_log

if __name__=="__main__":
    raise SystemExit(main())
