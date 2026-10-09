using System;
using System.IO;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Threading;

// Optional out-of-process video extension. No game DLL patches or custom natives.
class VideoCompanion {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X,Y; }
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr h,out RECT r);
    [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr h,ref POINT p);
    [DllImport("user32.dll")] static extern bool IsWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
    delegate bool EnumWindowCallback(IntPtr h,IntPtr arg);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowCallback fn,IntPtr arg);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);
    [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h,System.Text.StringBuilder text,int size);
    [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h,System.Text.StringBuilder text,int size);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h,uint command);
    [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h,int i);
    [DllImport("user32.dll")] static extern int SetWindowLong(IntPtr h,int i,int v);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h,IntPtr after,int x,int y,int w,int height,uint flags);
    [DllImport("user32.dll")] static extern bool SetLayeredWindowAttributes(IntPtr h,uint color,byte alpha,uint flags);
    static string root, request, log, evidence;
    static Window win;
    static MediaElement media;
    static IntPtr target, overlay;
    static Process attachedGame;
    static int attachedPid, pinnedPid, clientPid;
    static string active="", lastText="";
    static double offset, duration;
    static double volume=1, rate=1;
    static DateTime received, opened, deadline;
    static bool ready, visible, preview, automatic;
    static HashSet<string> completed=new HashSet<string>();
    static Dictionary<string,string> clips=new Dictionary<string,string>();
    static int opens, frameChecks;
    static string gameRoot;
    static MixPackage bundle;
    static string bundleCache;
    static DateTime scanAfter=DateTime.MinValue;
    static System.Threading.Mutex instance;
    static string lastSession="";
    static int lastSequence=-1, ownerPid;
    static double lastElapsed;
    static DateTime lastProtocol=DateTime.MinValue;
    static DateTime lastFileWrite=DateTime.MinValue;
    static DateTime gameStarted=DateTime.MinValue;
    static void Log(string s) { Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(log)));File.AppendAllText(log,DateTime.UtcNow.ToString("o")+" "+s+Environment.NewLine); }
    static string Arg(string[] args,string k,string fallback) {
        for(int i=0;i<args.Length-1;i++) if(args[i]==k) return args[i+1]; return fallback;
    }
    static double Num(string s) { return double.Parse(s,CultureInfo.InvariantCulture); }
    static void FindGame() {
        if(gameRoot==null || (target!=IntPtr.Zero && IsWindow(target)) || DateTime.UtcNow<scanAfter)return;
        scanAfter=DateTime.UtcNow.AddSeconds(1);
        var ids=new HashSet<int>();foreach(string name in new string[]{"war3","Warcraft III"})foreach(var p in Process.GetProcessesByName(name)){ids.Add(p.Id);p.Dispose();}
        EnumWindows(delegate(IntPtr h,IntPtr arg) {
            // Classic War3 can hide its window while unfocused. Still attach;
            // Position() independently gates display on the foreground handle.
            uint id;GetWindowThreadProcessId(h,out id);
            var title=new System.Text.StringBuilder(256);GetWindowText(h,title,256);
            var kind=new System.Text.StringBuilder(256);GetClassName(h,kind,256);
            // Hidden/minimized classic game windows can have an empty caption.
            // The injected debug console is not the game render window.
            if(!ids.Contains((int)id)||kind.ToString()!="Warcraft III"||(pinnedPid>0 && id!=(uint)pinnedPid))return true;
            try {using(var p=Process.GetProcessById((int)id)) {
                string path=null;try{path=p.MainModule.FileName;}catch(System.ComponentModel.Win32Exception){}
                if(path!=null && !Path.GetDirectoryName(path).Equals(gameRoot,StringComparison.OrdinalIgnoreCase))return true;
                if(active!="")Stop("game-changed");
                completed.Clear();lastText="";lastSequence=-1;lastSession="";
                try{gameStarted=p.StartTime.ToUniversalTime();}catch{gameStarted=DateTime.UtcNow.AddSeconds(-5);}
                if(attachedGame!=null)attachedGame.Dispose();
                attachedGame=Process.GetProcessById((int)id);attachedPid=(int)id;
                target=h;Log("ATTACHED pid="+id+" handle="+target+" path="+(path??"unavailable"));return false;
            }}catch(Exception){return true;}
        },IntPtr.Zero);
    }
    static bool Setup() {
        string settings=Path.Combine(root,"game-root.txt");
        string initial=File.Exists(settings)?File.ReadAllText(settings).Trim():"";
        if(initial=="")try {using(var k=Microsoft.Win32.Registry.CurrentUser.OpenSubKey(@"Software\Blizzard Entertainment\Warcraft III")) initial=Convert.ToString(k.GetValue("InstallPath"));}catch{}
        var setup=new Window {Title="War3 视频增强",Width=590,Height=210,ResizeMode=ResizeMode.NoResize,WindowStartupLocation=WindowStartupLocation.CenterScreen};
        var panel=new StackPanel {Margin=new Thickness(18)};
        panel.Children.Add(new TextBlock {Text="选择游戏目录。视频支持窗口化 / 无边框模式。",Margin=new Thickness(0,0,0,10)});
        var row=new DockPanel();var browse=new Button {Content="选择…",Padding=new Thickness(12,4,12,4),Margin=new Thickness(8,0,0,0)};
        DockPanel.SetDock(browse,Dock.Right);row.Children.Add(browse);
        var pathBox=new TextBox {Text=initial,Padding=new Thickness(5)};row.Children.Add(pathBox);panel.Children.Add(row);
        browse.Click+=delegate {var d=new Microsoft.Win32.OpenFileDialog {Title="选择 Warcraft III 游戏程序",Filter="游戏程序|war3.exe;Warcraft III.exe",CheckFileExists=true};if(d.ShowDialog(setup)==true)pathBox.Text=Path.GetDirectoryName(d.FileName);};
        panel.Children.Add(new TextBlock {Text="未运行本程序、缺少视频或解码失败时，地图基础演出照常进行。",Margin=new Thickness(0,12,0,12)});
        var start=new Button {Content="启动视频增强",HorizontalAlignment=HorizontalAlignment.Left,Padding=new Thickness(14,5,14,5)};
        panel.Children.Add(start);bool accepted=false;
        start.Click+=delegate {
            string dir=pathBox.Text.Trim();
            if(!File.Exists(Path.Combine(dir,"war3.exe"))&&!File.Exists(Path.Combine(dir,"Warcraft III.exe"))){MessageBox.Show(setup,"请选择含游戏程序的目录。");return;}
            try {gameRoot=Path.GetFullPath(dir).TrimEnd(Path.DirectorySeparatorChar);Directory.CreateDirectory(Path.Combine(gameRoot,"War3Video"));File.WriteAllText(settings,gameRoot);accepted=true;setup.Close();}
            catch(Exception e){MessageBox.Show(setup,e.Message);}
        };
        setup.Content=panel;setup.ShowDialog();return accepted;
    }
    static void Stop(string reason) {
        if(active!="") { Log("STOP "+active+" "+reason); completed.Add(active); }
        media.Stop(); media.Close(); win.Hide(); active="";ready=false;visible=false;
    }
    static bool ValidClip(string id,out string path) {
        path=null;
        if(id.Length==0 || id.Length>120 || id.IndexOfAny(Path.GetInvalidFileNameChars())>=0 || Path.GetFileName(id)!=id)return false;
        string name;
        if(!clips.TryGetValue(id,out name))name=id.EndsWith(".mp4",StringComparison.OrdinalIgnoreCase)?id:id+".mp4";
        if(bundle!=null) {
            try {path=bundle.Resolve(name,bundleCache);if(path!=null)Log("PACKAGE clip="+name+" cache="+path);return path!=null;}
            catch(Exception e){Log("FALLBACK package "+e.Message);return false;}
        }
        path=Path.GetFullPath(Path.Combine(root,"clips",name));
        return path.StartsWith(Path.GetFullPath(Path.Combine(root,"clips"))+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase) && File.Exists(path);
    }
    static void Play(string key,string clip,double elapsed,double seconds) {
        string path;
        if(completed.Contains(key)) return;
        if(!ValidClip(clip,out path)) { completed.Add(key);Log("FALLBACK missing clip "+clip+"; expected clips/"+clip+".mp4");return; }
        if(active!="") Stop("replaced");
        active=key;automatic=seconds==0;offset=automatic?0:elapsed;duration=seconds;received=DateTime.UtcNow;deadline=received.AddSeconds(automatic?15:Math.Max(0,seconds-elapsed)+2);
        ready=false;media.Volume=volume;media.SpeedRatio=rate;media.Source=new Uri(path);media.Play();opens++;Log("PLAY "+key+" "+clip+" offset="+offset+" auto="+automatic);
    }
    static void PollRequest() {
        if(!File.Exists(request)) {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(request)));
            using(var marker=new FileStream(request,FileMode.OpenOrCreate,FileAccess.Write,FileShare.ReadWrite|FileShare.Delete)){}
            return;
        }
        string text;
        using(var f=new FileStream(request,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete)) {
            if(f.Length>8192) return;
            using(var r=new StreamReader(f)) text=r.ReadToEnd();
        }
        DateTime fileWrite=File.GetLastWriteTimeUtc(request);
        if(text==lastText && fileWrite==lastFileWrite) return;
        var m=Regex.Match(text,@"WV1\|([A-Za-z0-9_-]{1,64})\|(\d{1,9})\|(PLAY|STOP|SETTINGS)\|([^|\r\n]{1,120})\|([0-9]{1,6}(?:\.[0-9]{1,5})?)\|([0-9]{1,6}(?:\.[0-9]{1,5})?)(?:\|([0-9]{1,3}(?:\.[0-9]{1,5})?)\|([0-9]{1,2}(?:\.[0-9]{1,5})?))?\|END");
        if(!m.Success) return;
        // Accept one-shot requests made during this game even if cold extraction
        // delayed attachment. Reject markers left by an earlier game instead.
        if(gameStarted!=DateTime.MinValue && fileWrite<gameStarted) {lastText=text;lastFileWrite=fileWrite;return;}
        double seconds=Num(m.Groups[5].Value), elapsed=Num(m.Groups[6].Value);
        if(seconds<0 || seconds>600 || elapsed<0 || (seconds>0 && elapsed>seconds)) return;
        lastText=text;lastFileWrite=fileWrite;
        if(m.Groups[7].Success) {
            double nextVolume=Num(m.Groups[7].Value)/100, nextRate=Num(m.Groups[8].Value);
            if(nextVolume<0 || nextVolume>1 || nextRate<0.25 || nextRate>4)return;
            if(volume!=nextVolume || rate!=nextRate) {
                volume=nextVolume;rate=nextRate;media.Volume=volume;media.SpeedRatio=rate;
                if(automatic && ready)deadline=DateTime.UtcNow.AddSeconds(Math.Max(0,duration-media.Position.TotalSeconds)/rate+3);
                Log("SETTINGS volume="+volume.ToString(CultureInfo.InvariantCulture)+" rate="+rate.ToString(CultureInfo.InvariantCulture));
            }
        }
        if(m.Groups[3].Value=="SETTINGS")return;
        string session=m.Groups[1].Value;int sequence=int.Parse(m.Groups[2].Value);
        if(session==lastSession && sequence<=lastSequence && elapsed<1 && !(automatic && sequence==lastSequence) &&
            (sequence<lastSequence || elapsed+0.75<lastElapsed || (DateTime.UtcNow-lastProtocol).TotalSeconds>2)) {
            if(active!="")Stop("map-restarted");completed.Clear();Log("RESET map timeline");
        }
        lastSession=session;lastSequence=sequence;lastElapsed=elapsed;lastProtocol=DateTime.UtcNow;
        string key=m.Groups[1].Value+":"+m.Groups[2].Value;
        if(m.Groups[3].Value=="STOP") { if(key==active) Stop("map-stop");completed.Add(key);return; }
        if(key!=active) Play(key,m.Groups[4].Value,elapsed,seconds);
        else {
            if(!automatic){offset=elapsed;received=DateTime.UtcNow;deadline=received.AddSeconds(seconds-elapsed+2);}
            // Settings change only on explicit requests; heartbeats never seek.
        }
    }
    static void Position() {
        if(preview) return;
        if(target==IntPtr.Zero || !IsWindow(target) || IsIconic(target) || !IsWindowVisible(target)) {
            if(visible) {win.Hide();visible=false;Log("HIDDEN focus/minimized");}return;
        }
        RECT r;POINT p=new POINT();if(!GetClientRect(target,out r) || !ClientToScreen(target,ref p)) return;
        if(!visible && ready) {win.Show();visible=true;Log("VISIBLE");}
        if(visible) {
            // WPF's Show() may clear native WS_EX_LAYERED; apply after Show.
            int style=GetWindowLong(overlay,-20),required=0x08000000|0x00000020|0x00000080|0x00080000;
            if((style&required)!=required)SetWindowLong(overlay,-20,style|required);
            // Keep this overlay immediately above its game in the normal Z order,
            // allowing both visible clients to render without covering other apps.
            IntPtr above=GetWindow(target,3);
            SetWindowPos(overlay,above==overlay?IntPtr.Zero:above,p.X,p.Y,r.R-r.L,r.B-r.T,(uint)(0x0010|(above==overlay?0x0004:0)));
        }
    }
    static void CheckGameLifetime() {
        if(target==IntPtr.Zero)return;
        uint windowPid;GetWindowThreadProcessId(target,out windowPid);
        bool gone=!IsWindow(target)||(attachedPid>0 && windowPid!=(uint)attachedPid);
        if(!gone && attachedGame!=null) {
            try{gone=attachedGame.HasExited;}catch(System.ComponentModel.Win32Exception){}
        }
        if(!gone)return;
        Stop("attached-game-exit");target=IntPtr.Zero;attachedPid=0;gameStarted=DateTime.MinValue;
        if(attachedGame!=null){attachedGame.Dispose();attachedGame=null;}
        // An editor-owned instance may wait for the next game, but never keep
        // the closed game's audio alive merely because the editor is running.
        Log("DETACHED game closed; waiting for next game");
    }
    static void CaptureFrame() {
        if(evidence==null || !ready || !visible) return;
        // Render the actual decoded media, not a substitute poster.
        int w=(int)media.ActualWidth,h=(int)media.ActualHeight;if(w<2||h<2)return;
        var b=new System.Windows.Media.Imaging.RenderTargetBitmap(w,h,96,96,PixelFormats.Pbgra32);
        b.Render(media);
        var e=new System.Windows.Media.Imaging.PngBitmapEncoder();e.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(b));
        string path=Path.Combine(evidence,"decoded-"+(frameChecks++)+".png");
        using(var f=File.Create(path)) e.Save(f);
        Log("FRAME "+path+" position="+media.Position.TotalSeconds+" natural="+media.NaturalVideoWidth+"x"+media.NaturalVideoHeight);
    }
    [STAThread] static int Main(string[] args) {
        root=AppDomain.CurrentDomain.BaseDirectory;
        string bundlePath=Arg(args,"--bundle",null);
        if(bundlePath!=null) {
            try {bundle=MixPackage.Open(bundlePath);bundleCache=Path.Combine(Path.GetDirectoryName(Path.GetFullPath(bundlePath)),"War3Video","cache");}
            catch(Exception){return 2;}
            root=Path.Combine(Path.GetDirectoryName(Path.GetFullPath(bundlePath)),"War3Video");Directory.CreateDirectory(root);
        }
        log=Arg(args,"--log",Path.Combine(root,"player.log"));
        request=Arg(args,"--request",Path.Combine(root,"request.pld"));
        evidence=Arg(args,"--evidence",null);if(evidence!=null)Directory.CreateDirectory(evidence);
        preview=Array.IndexOf(args,"--preview")>=0;
        int.TryParse(Arg(args,"--owner-pid","0"),out ownerPid);
        int.TryParse(Arg(args,"--client-pid","0"),out clientPid);
        int pid; if(int.TryParse(Arg(args,"--pid","0"),out pid)&&pid>0) {attachedGame=Process.GetProcessById(pid);attachedPid=pid;target=attachedGame.MainWindowHandle;gameStarted=attachedGame.StartTime.ToUniversalTime();}
        pinnedPid=clientPid>0?clientPid:pid;
        // A tiny explicit whitelist; maps never supply file paths or executable code.
        foreach(string l in File.Exists(Path.Combine(root,"clips.txt"))?File.ReadAllLines(Path.Combine(root,"clips.txt")):new string[0]) {
            string[] p=l.Split('=');if(p.Length==2)clips[p[0].Trim()]=p[1].Trim();
        }
        var app=new Application();app.ShutdownMode=ShutdownMode.OnExplicitShutdown;
        if(!preview){bool created;instance=new System.Threading.Mutex(true,@"Local\War3VideoCompanion"+(clientPid>0?"_"+clientPid:""),out created);if(!created){if(ownerPid==0)MessageBox.Show("视频增强已在后台运行。");instance.Dispose();return 0;}}
        gameRoot=Arg(args,"--game-root",null);
        if(!preview && pid==0 && gameRoot==null && !Setup())return 0;
        if(gameRoot!=null){gameRoot=Path.GetFullPath(gameRoot).TrimEnd(Path.DirectorySeparatorChar);Directory.CreateDirectory(Path.Combine(gameRoot,"War3Video"));request=Path.Combine(gameRoot,"War3Video","request.pld");}
        if(clientPid>0){request=Path.Combine(gameRoot,"War3Video","request-"+clientPid+".pld");log=Arg(args,"--log",Path.Combine(gameRoot,"War3Video","player-"+clientPid+".log"));}
        win=new Window {Title="War3 Video Companion",WindowStyle=WindowStyle.None,ResizeMode=ResizeMode.NoResize,
            ShowActivated=false,ShowInTaskbar=false,AllowsTransparency=true,Background=Brushes.Black,Width=960,Height=540,Left=80,Top=80};
        media=new MediaElement {LoadedBehavior=MediaState.Manual,UnloadedBehavior=MediaState.Manual,Stretch=Stretch.Uniform,Volume=1};
        win.Content=media;
        win.SourceInitialized+=delegate {
            overlay=new WindowInteropHelper(win).Handle;
            SetWindowLong(overlay,-20,GetWindowLong(overlay,-20)|0x08000000|0x00000020|0x00000080|0x00080000);
            HwndSource.FromHwnd(overlay).AddHook(delegate(IntPtr h,int msg,IntPtr w,IntPtr l,ref bool handled) {
                if(msg==0x84){handled=true;return new IntPtr(-1);}return IntPtr.Zero;
            });
        };
        media.MediaOpened+=delegate {
            ready=true;opened=DateTime.UtcNow;media.Position=TimeSpan.FromSeconds(offset);media.Volume=volume;media.SpeedRatio=rate;media.Play();
            if(automatic) {
                if(!media.NaturalDuration.HasTimeSpan){Stop("unknown-duration");return;}
                duration=media.NaturalDuration.TimeSpan.TotalSeconds;
                deadline=DateTime.UtcNow.AddSeconds(duration/rate+3);
                Log("AUTO_DURATION seconds="+duration.ToString(CultureInfo.InvariantCulture));
            }
            Log("OPENED "+media.NaturalVideoWidth+"x"+media.NaturalVideoHeight+" duration="+(media.NaturalDuration.HasTimeSpan?media.NaturalDuration.TimeSpan.TotalSeconds:0)+" has_audio="+media.HasAudio+" volume="+media.Volume);
            if(preview){win.Show();visible=true;}
        };
        media.MediaFailed+=delegate(object sender,ExceptionRoutedEventArgs e){Log("FALLBACK decode "+e.ErrorException.Message);Stop("decode-failed");};
        media.MediaEnded+=delegate {Stop("ended");};
        win.Show();win.Hide();
        var tick=new DispatcherTimer {Interval=TimeSpan.FromMilliseconds(100)};
        tick.Tick+=delegate {
            try {
                if(ownerPid>0) {try {using(var owner=Process.GetProcessById(ownerPid)) {}}catch(ArgumentException){Stop("game-exit");app.Shutdown();return;}}
                if(File.Exists(log+".stop")){Stop("shutdown");app.Shutdown();return;}
                if(!preview) {CheckGameLifetime();FindGame();if(target!=IntPtr.Zero && IsWindow(target))PollRequest();}
                if(active!="") {
                    if(DateTime.UtcNow>deadline) Stop("deadline");
                    else if(!preview && !automatic && (DateTime.UtcNow-received).TotalSeconds>2) Stop("heartbeat-timeout");
                    // Maps own keyboard actions and targeted stops. A global
                    // ESC listener could stop another visible client's video.
                    else Position();
                }
            } catch(IOException) {} catch(Exception e){Log("ERROR "+e.Message);Stop("error");}
        };
        var capture=new DispatcherTimer {Interval=TimeSpan.FromSeconds(1)};
        capture.Tick+=delegate {try {CaptureFrame();} catch(Exception e){Log("CAPTURE_ERROR "+e.Message);} };
        Log("START pid="+pid+" preview="+preview+" request="+request);
        if(bundle!=null)Log("BUNDLE "+bundle.PathName+" entries="+bundle.Entries.Count);
        tick.Start();if(evidence!=null)capture.Start();
        if(preview) Play("preview:1",Arg(args,"--clip","demo"),0,Num(Arg(args,"--duration","8")));
        app.Run();if(attachedGame!=null)attachedGame.Dispose();if(instance!=null){instance.ReleaseMutex();instance.Dispose();}Log("EXIT opens="+opens);return 0;
    }
}
