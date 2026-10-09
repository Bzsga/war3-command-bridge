"""Packaged-app diagnostics: exercise widgets and an isolated runtime worker."""
import os
from pathlib import Path
import sys
from .storage import save

def main(output):
    os.environ['QT_QPA_PLATFORM']='offscreen'
    from PySide6.QtWidgets import QApplication
    from .ui import Window,STYLE,configure_fonts
    from .backend import Backend
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=True)
    app=QApplication([]);configure_fonts(app);app.setStyleSheet(STYLE);w=Window(root/'profile');w.timer.stop();w.show();app.processEvents()
    w.grab().save(str(root/'desktop.png'));w.close()
    p={'schema':1,'id':'smoke','name':'包诊断','directory':str(root/'project'),'input_type':'source','map':'unconfigured.w3x','environment':{}}
    try:result=Backend(p).doctor()
    except Exception as exc:
        save(root/'smoke.json',{'ok':False,'ui_constructed':True,'worker_executed':False,'error':str(exc)});return 1
    save(root/'smoke.json',{'ok':result['ok'] is False,'ui_constructed':True,'worker_executed':True,'python_executable':sys.executable,'environment':result})
    return 0
