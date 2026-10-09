from __future__ import annotations
import ctypes
import json
import os
from pathlib import Path
import uuid
import zipfile

def save(path: Path, value):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    os.replace(tmp,path)

def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))

def app_data():
    root=Path(os.environ.get('LOCALAPPDATA', str(Path.cwd()/'work')))/'War3TestWorkbench'
    root.mkdir(parents=True,exist_ok=True)
    return root

class Blob(ctypes.Structure):
    _fields_=[('size',ctypes.c_uint32),('data',ctypes.POINTER(ctypes.c_ubyte))]

def crypt(data: bytes, decrypt=False):
    if os.name!='nt': raise RuntimeError('密钥保存需要 Windows DPAPI')
    buf=(ctypes.c_ubyte*len(data)).from_buffer_copy(data)
    src=Blob(len(data),buf); dst=Blob()
    api=ctypes.WinDLL('crypt32',use_last_error=True)
    fn=api.CryptUnprotectData if decrypt else api.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(Blob)]
    fn.restype=ctypes.c_int
    if not fn(ctypes.byref(src),None,None,None,None,1,ctypes.byref(dst)):
        raise OSError(ctypes.get_last_error(),'Windows 无法解密密钥' if decrypt else 'Windows 无法保存密钥')
    try: return ctypes.string_at(dst.data,dst.size)
    finally:
        kernel=ctypes.WinDLL('kernel32'); kernel.LocalFree.argtypes=[ctypes.c_void_p]; kernel.LocalFree(dst.data)

class Vault:
    def __init__(self,root=None): self.root=Path(root or app_data())/'credentials'
    def put(self,ref,key):
        if not ref.isalnum(): raise ValueError('无效密钥引用')
        self.root.mkdir(parents=True,exist_ok=True)
        (self.root/(ref+'.bin')).write_bytes(crypt(key.encode('utf8')))
    def get(self,ref):
        if not isinstance(ref,str) or not ref.isalnum():raise ValueError('无效密钥引用')
        p=self.root/(ref+'.bin')
        return crypt(p.read_bytes(),True).decode('utf8') if p.exists() else ''

def export_project(project, destination):
    """Only explicit, portable authoring files. Never runtime, API keys or source."""
    source=Path(project['directory'])
    portable={k:project[k] for k in ['name','input_type','catalog','cases'] if k in project}
    portable.update(schema=1,id=uuid.uuid4().hex,map='',source_dir='',build_argv=[],environment={},provider={})
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('project.json',json.dumps(portable,ensure_ascii=False,indent=2))
        z.writestr('接入说明.txt','在项目页重新选择地图、运行环境与模型。命令映射必须针对新地图重新验证。')
    return str(destination)
