"""Build a standalone PySide6 desktop distribution; requires Nuitka and a C compiler."""
from pathlib import Path
import argparse
import configparser
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--method',choices=['pyside6-deploy','pyinstaller'],default='pyside6-deploy');parser.add_argument('--output',default=str(ROOT/'release-0.1.0'));args=parser.parse_args()
    native=ROOT/'vendor/runtime/KkweLuaHost.exe';native_source=ROOT/'vendor/runtime/src/KkweLuaHost.cs'
    if not native.exists() or native.stat().st_mtime<native_source.stat().st_mtime:
        csc=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework/v4.0.30319/csc.exe'
        subprocess.run([str(csc),'/nologo','/platform:x86','/out:'+str(native),str(native_source)],check=True)
    if args.method=='pyinstaller':
        build=ROOT/'deployment-pyinstaller';build.mkdir(exist_ok=True)
        spec=build/'War3TestWorkbench.spec'
        spec.write_text(f'''a = Analysis([{str(ROOT/'main.py')!r}], pathex=[{str(ROOT)!r}], binaries=[],
datas=[({str(ROOT/'vendor')!r},'vendor'),({str(ROOT/'examples')!r},'examples')],
hiddenimports=['statistics','msvcrt','winreg','dataclasses','ctypes.wintypes','xml.etree.ElementTree'],
excludes=['pytest','PySide6.QtWebEngineWidgets','PySide6.QtWebEngineCore'],noarchive=False)
# Windows 10 supplies its own UCRT; avoid an unrelated DLL discovered via PATH.
a.binaries = [x for x in a.binaries if x[0].lower() != 'ucrtbase.dll']
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='War3TestWorkbench',console=False,debug=False,upx=False)
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='War3TestWorkbench')
''',encoding='utf8')
        env=dict(os.environ);env['PYTHONUTF8']='1';env['PATH']=str(Path(sys.executable).parent)+os.pathsep+str(Path(os.environ.get('WINDIR',r'C:\Windows'))/'System32')
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--distpath',args.output,'--workpath',str(build),str(spec)],cwd=ROOT,env=env,check=True)
        return
    exe=Path(sys.executable).parent/'pyside6-deploy.exe'
    env=dict(os.environ);env['PYTHONUTF8']='1'
    spec=ROOT/'pysidedeploy.spec'
    if spec.exists():
        try:spec.read_text(encoding='utf8')
        except UnicodeDecodeError:spec.write_text(spec.read_text(encoding='gb18030'),encoding='utf8')
    subprocess.run([str(exe),str(ROOT/'main.py'),'--init','--force','--no-install','--name','War3TestWorkbench','--extra-ignore-dirs','tests,vendor,release,deployment'],cwd=ROOT,env=env,check=True)
    config=configparser.ConfigParser()
    try:config.read(ROOT/'pysidedeploy.spec',encoding='utf8')
    except UnicodeDecodeError:config.read(ROOT/'pysidedeploy.spec',encoding='gb18030')
    config['app']['exec_directory']=str(ROOT/'release');config['app']['icon']=''
    config['python']['packages']='Nuitka==4.2.2'
    config['nuitka']['extra_args']='--assume-yes-for-downloads --mingw64 --windows-console-mode=disable --output-filename=War3TestWorkbench.exe --include-data-dir=vendor=vendor --include-module=statistics --include-module=msvcrt --include-module=winreg --include-module=ctypes.wintypes --include-qt-plugins=platforms,styles --noinclude-qt-translations --nofollow-import-to=pytest'
    with (ROOT/'pysidedeploy.spec').open('w',encoding='utf8') as f:config.write(f)
    subprocess.run([str(exe),'-c',str(ROOT/'pysidedeploy.spec'),'--force','--no-install','--no-warn','--keep-deployment-files','--extra-ignore-dirs','tests,vendor,release,deployment'],cwd=ROOT,env=env,check=True)
if __name__=='__main__':main()
