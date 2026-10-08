// Hosts KKWE's own Lua ABI so its sys/filesystem modules can be reused safely.
using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Runtime.InteropServices;

class KkweLuaHost {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern IntPtr LoadLibraryW(string p);
    [DllImport("kernel32.dll", CharSet=CharSet.Ansi)] static extern IntPtr GetProcAddress(IntPtr h,string n);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] static extern bool SetDllDirectoryW(string p);
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,uint pid);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern bool QueryFullProcessImageNameW(IntPtr h,uint flags,StringBuilder path,ref uint length);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr NewState();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void StateVoid(IntPtr s);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void CreateTable(IntPtr s,int a,int b);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr PushString(IntPtr s,byte[] text);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void RawSet(IntPtr s,int index,long key);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void SetGlobal(IntPtr s,byte[] name);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int Callback(IntPtr s);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void PushClosure(IntPtr s,Callback fn,int up);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void PushBoolean(IntPtr s,int v);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int LoadBuffer(IntPtr s,byte[] text,UIntPtr length,byte[] name,IntPtr mode);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int PCall(IntPtr s,int args,int results,int error,IntPtr ctx,IntPtr continuation);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr LuaToString(IntPtr s,int index,out UIntPtr length);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate long ToInteger(IntPtr s,int index,IntPtr isnum);
    static byte[] Utf(string s) {return Encoding.UTF8.GetBytes(s+"\0");}
    static string Json(string s) {return "\""+s.Replace("\\","\\\\").Replace("\"","\\\"").Replace("\r","\\r").Replace("\n","\\n")+"\"";}
    static T Api<T>(IntPtr dll,string name) where T:class {
        IntPtr fn=GetProcAddress(dll,name);
        if(fn==IntPtr.Zero) throw new Exception("Missing KKWE Lua API: "+name);
        return Marshal.GetDelegateForFunctionPointer(fn,typeof(T)) as T;
    }
    static int Main(string[] args) {
        if(args.Length!=6) {Console.Error.WriteLine("bin script game command loader ipc required");return 2;}
        IntPtr state=IntPtr.Zero;StateVoid close=null;
        try {
            Console.OutputEncoding=Encoding.UTF8;
            SetDllDirectoryW(args[0]);
            IntPtr dll=LoadLibraryW(Path.Combine(args[0],"luacore.dll"));
            if(dll==IntPtr.Zero) throw new Exception("Cannot load KKWE luacore.dll: "+Marshal.GetLastWin32Error());
            state=Api<NewState>(dll,"luaL_newstate")();
            if(state==IntPtr.Zero) throw new Exception("Lua state allocation failed");
            close=Api<StateVoid>(dll,"lua_close");
            Api<StateVoid>(dll,"luaL_openlibs")(state);
            CreateTable table=Api<CreateTable>(dll,"lua_createtable");
            PushString push=Api<PushString>(dll,"lua_pushstring");
            RawSet raw=Api<RawSet>(dll,"lua_rawseti");
            SetGlobal global=Api<SetGlobal>(dll,"lua_setglobal");
            PushClosure closure=Api<PushClosure>(dll,"lua_pushcclosure");
            PushBoolean boolean=Api<PushBoolean>(dll,"lua_pushboolean");
            table(state,5,0);
            string[] values={args[0],args[2],args[3],args[4],args[5]};
            for(int i=0;i<values.Length;i++) {push(state,Utf(values[i]));raw(state,-2,i+1);}
            global(state,Utf("arg"));
            // Lua's DLL search uses narrow Windows paths; filesystem arguments stay UTF-8.
            push(state,Encoding.Default.GetBytes(Path.Combine(args[0],"modules","?.dll")+";\0"));
            global(state,Utf("host_module_cpath"));
            Callback sleep=delegate(IntPtr s) {Thread.Sleep(50);return 0;};
            Callback stop=delegate(IntPtr s) {boolean(s,File.Exists(Path.Combine(args[5],"launcher.stop"))?1:0);return 1;};
            ToInteger integer=Api<ToInteger>(dll,"lua_tointegerx");
            Callback record=delegate(IntPtr s) {
                uint pid=(uint)integer(s,1,IntPtr.Zero);
                IntPtr h=OpenProcess(0x1000,false,pid);
                int error=Marshal.GetLastWin32Error();string path=null;
                if(h!=IntPtr.Zero) {
                    uint n=32768;StringBuilder b=new StringBuilder((int)n);
                    if(QueryFullProcessImageNameW(h,0,b,ref n)) {path=b.ToString();error=0;} else error=Marshal.GetLastWin32Error();
                    CloseHandle(h);
                }
                string data="{\"pid\":"+pid+",\"actual_executable\":"+(path==null?"null":Json(path))+",\"query_error\":"+error+",\"source\":\"QueryFullProcessImageNameW immediately after KKWE create\"}";
                File.WriteAllText(Path.Combine(args[5],"game-process.json"),data,new UTF8Encoding(false));return 0;
            };
            closure(state,sleep,0);global(state,Utf("host_sleep"));
            closure(state,stop,0);global(state,Utf("host_should_stop"));
            closure(state,record,0);global(state,Utf("host_record_process"));
            byte[] source=Encoding.UTF8.GetBytes(File.ReadAllText(args[1],Encoding.UTF8));
            int code=Api<LoadBuffer>(dll,"luaL_loadbufferx")(state,source,(UIntPtr)source.Length,Utf("@kkwe_launcher.lua"),IntPtr.Zero);
            if(code==0) code=Api<PCall>(dll,"lua_pcallk")(state,0,-1,0,IntPtr.Zero,IntPtr.Zero);
            GC.KeepAlive(sleep);GC.KeepAlive(stop);GC.KeepAlive(record);
            if(code!=0) {
                UIntPtr length;IntPtr text=Api<LuaToString>(dll,"lua_tolstring")(state,-1,out length);
                byte[] bytes=new byte[(int)length.ToUInt32()];if(text!=IntPtr.Zero) Marshal.Copy(text,bytes,0,bytes.Length);
                Console.Error.WriteLine(Encoding.UTF8.GetString(bytes));return 1;
            }
            return 0;
        } catch(Exception e) {Console.Error.WriteLine(e.Message);return 1;}
        finally {if(state!=IntPtr.Zero && close!=null) close(state);}
    }
}
