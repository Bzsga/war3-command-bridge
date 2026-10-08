"""Read-only Win32 sampling; never activates, moves, or sends input to windows."""
import ctypes
import threading
import time


class BackgroundProbe:
    def __init__(self,pid):
        self.pid=pid;self.samples=[];self.errors=[];self.started=time.perf_counter()
        self.stop=threading.Event()
        self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.user.GetForegroundWindow.restype=ctypes.c_void_p
        self.user.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32)]
        self.user.IsIconic.argtypes=[ctypes.c_void_p]
        self.user.IsWindow.argtypes=[ctypes.c_void_p]
        self.user.GetWindowTextW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_int]
        callback=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
        windows=[]
        def visit(hwnd,_):
            owner=ctypes.c_uint32();self.user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
            if owner.value==pid:
                name=ctypes.create_unicode_buffer(256);self.user.GetWindowTextW(hwnd,name,len(name))
                if name.value=='Warcraft III':windows.append(hwnd)
            return True
        self.user.EnumWindows.argtypes=[callback,ctypes.c_void_p]
        self.user.EnumWindows(callback(visit),None)
        if len(windows)!=1:raise RuntimeError(f'expected one owned Warcraft III window, found {len(windows)}')
        self.window=windows[0]
        self.sample()
        self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()

    def sample(self):
        hwnd=self.user.GetForegroundWindow();pid=ctypes.c_uint32()
        query_ok=(not hwnd) or bool(self.user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid)) and pid.value)
        self.samples.append({'elapsed_s':time.perf_counter()-self.started,'foreground_pid':pid.value,
                             'game_foreground':pid.value==self.pid,'foreground_hwnd':int(hwnd or 0),'foreground_query_ok':query_ok,'minimized':bool(self.user.IsIconic(self.window)),
                             'game_window_exists':bool(self.user.IsWindow(self.window))})

    def geometry(self):
        class Rect(ctypes.Structure):
            _fields_=[('left',ctypes.c_long),('top',ctypes.c_long),('right',ctypes.c_long),('bottom',ctypes.c_long)]
        self.user.GetWindowLongW.argtypes=[ctypes.c_void_p,ctypes.c_int]
        self.user.GetWindowLongW.restype=ctypes.c_long
        self.user.GetWindowRect.argtypes=[ctypes.c_void_p,ctypes.POINTER(Rect)]
        self.user.GetClientRect.argtypes=[ctypes.c_void_p,ctypes.POINTER(Rect)]
        self.user.IsZoomed.argtypes=[ctypes.c_void_p]
        outer=Rect();client=Rect()
        if not self.user.GetWindowRect(self.window,ctypes.byref(outer)):raise ctypes.WinError(ctypes.get_last_error())
        if not self.user.GetClientRect(self.window,ctypes.byref(client)):raise ctypes.WinError(ctypes.get_last_error())
        style=self.user.GetWindowLongW(self.window,-16)&0xffffffff
        return {'hwnd':self.window,'style':hex(style),'has_caption':style&0xc00000==0xc00000,
                'has_system_menu':bool(style&0x80000),'resizable':bool(style&0x40000),
                'maximized':bool(self.user.IsZoomed(self.window)),'minimized':bool(self.user.IsIconic(self.window)),
                'window_rect':[outer.left,outer.top,outer.right,outer.bottom],
                'client_size':[client.right-client.left,client.bottom-client.top],
                'primary_screen_size':[self.user.GetSystemMetrics(0),self.user.GetSystemMetrics(1)]}

    def loop(self):
        while not self.stop.wait(.05):
            try:self.sample()
            except Exception as exc:self.errors.append(str(exc));return

    def finish(self):
        self.stop.set();self.thread.join(timeout=2);self.sample()
        samples=self.samples
        return {'sample_interval_ms':50,'sample_count':len(samples),'duration_s':samples[-1]['elapsed_s'],
                'game_pid':self.pid,'game_hwnd':self.window,
                'foreground_samples':sum(s['game_foreground'] for s in samples),
                'unknown_foreground_samples':sum(not s['foreground_query_ok'] for s in samples),
                'no_foreground_window_samples':sum(s['foreground_hwnd']==0 for s in samples),
                'minimized_samples':sum(s['minimized'] for s in samples),
                'missing_window_samples':sum(not s['game_window_exists'] for s in samples),
                'max_sample_gap_ms':max((b['elapsed_s']-a['elapsed_s'])*1000 for a,b in zip(samples,samples[1:])),
                'errors':self.errors,'samples':samples}
