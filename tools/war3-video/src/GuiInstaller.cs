using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Reflection;
using System.Collections.Generic;
using System.Text.RegularExpressions;

public static class GuiInstaller {
    public static string Resolve(string target) {
        string path=Path.GetFullPath(target);
        if(File.Exists(path))path=Path.GetDirectoryName(path);
        if(Directory.Exists(Path.Combine(path,"jass"))&&Directory.Exists(Path.Combine(path,"bin"))&&File.Exists(Path.Combine(path,"share/mpq/config")))return path;
        var candidates=new List<string>();
        for(int i=0;i<3&&path!=null;i++,path=Path.GetDirectoryName(path)){
            candidates.Add(path);
            foreach(string child in new[]{"KKWE插件","KKWE","YDWE"})candidates.Add(Path.Combine(path,child));
        }
        var matches=candidates.Distinct(StringComparer.OrdinalIgnoreCase).Where(p=>Directory.Exists(Path.Combine(p,"jass"))&&Directory.Exists(Path.Combine(p,"bin"))&&File.Exists(Path.Combine(p,"share/mpq/config"))).ToList();
        if(matches.Count!=1)throw new IOException(matches.Count==0?"未找到支持的编辑器目录（需要 bin、jass 和 share/mpq/config）。请选择 KKWE/YDWE 安装目录或启动程序。":"发现多个编辑器，请直接选择其中一个安装目录。");
        return matches[0];
    }
    public static string Detect(string root){return File.Exists(Path.Combine(root,"KKWE.exe"))||root.IndexOf("KKWE",StringComparison.OrdinalIgnoreCase)>=0?"KKWE":"YDWE";}
    static byte[] Resource(string name){using(var s=Assembly.GetExecutingAssembly().GetManifestResourceStream("gui."+name)){if(s==null)throw new IOException("工具缺少内置触发器动作文件："+name);using(var m=new MemoryStream()){s.CopyTo(m);return m.ToArray();}}}
    // Latin-1 is a lossless byte view: preserve UTF-8/ANSI, BOM and original lines.
    static readonly Encoding Bytes=Encoding.GetEncoding(28591);
    static readonly Regex Registration=new Regex(@"(?m)(?:^|(?<=\xEF\xBB\xBF))[ \t]*War3VideoGUI[ \t]*(?:\r?\n|$)",RegexOptions.IgnoreCase);
    static void Write(string path,byte[] data){Directory.CreateDirectory(Path.GetDirectoryName(path));string temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";try{File.WriteAllBytes(temp,data);if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);}finally{if(File.Exists(temp))File.Delete(temp);}}
    public static string Install(string target,string kind){
        if(kind!="KKWE"&&kind!="YDWE")throw new ArgumentException("编辑器类型必须为 KKWE 或 YDWE。");
        string root=Resolve(target),mpq=Path.Combine(root,"share/mpq"),config=Path.Combine(mpq,kind=="KKWE"?"config.user":"config");
        var writes=new Dictionary<string,byte[]>();
        foreach(string name in new[]{"action.txt","call.txt","define.txt"})writes[Path.Combine(mpq,"War3VideoGUI",name)]=Resource(name);
        foreach(string name in new[]{"War3VideoGUI.j","War3VideoGUI.cfg"})writes[Path.Combine(root,"jass",name)]=Resource(name);
        byte[] oldConfig=File.Exists(config)?File.ReadAllBytes(config):new byte[0];if(oldConfig.Contains((byte)0))throw new IOException("配置编码不受支持：请使用 UTF-8 或 ANSI。");string text=Bytes.GetString(oldConfig);
        if(!Registration.IsMatch(text))text+=(text.Length>0&&!text.EndsWith("\n")?"\r\n":"")+"War3VideoGUI\r\n";
        writes[config]=Bytes.GetBytes(text);
        if(kind=="KKWE"){
            string baseConfig=Path.Combine(mpq,"config");string original=Bytes.GetString(File.ReadAllBytes(baseConfig));
            if(Registration.IsMatch(original))writes[baseConfig]=Bytes.GetBytes(Registration.Replace(original,""));
        }
        Apply(writes);
        return kind+" 视频触发器动作已安装。\r\n目标："+root+"\r\n注册："+Path.GetFileName(config)+"\r\n请重启编辑器，在触发动作的“视频播放”分类使用。\r\n将视频 MIX 放到玩家实际启动的魔兽根目录，填写包内视频文件名即可。";
    }
    public static string Uninstall(string target,string kind){
        if(kind!="KKWE"&&kind!="YDWE")throw new ArgumentException("编辑器类型必须为 KKWE 或 YDWE。");
        string root=Resolve(target),mpq=Path.Combine(root,"share/mpq");var changes=new Dictionary<string,byte[]>();
        foreach(string name in (kind=="KKWE"?new[]{"config","config.user"}:new[]{"config"})){
            string path=Path.Combine(mpq,name);if(!File.Exists(path))continue;byte[] data=File.ReadAllBytes(path);
            if(data.Contains((byte)0))throw new IOException("配置编码不受支持：请使用 UTF-8 或 ANSI。");
            string text=Bytes.GetString(data);if(Registration.IsMatch(text))changes[path]=Bytes.GetBytes(Registration.Replace(text,""));
        }
        foreach(string name in new[]{"action.txt","call.txt","define.txt"})changes[Path.Combine(mpq,"War3VideoGUI",name)]=null;
        foreach(string name in new[]{"War3VideoGUI.j","War3VideoGUI.cfg"})changes[Path.Combine(root,"jass",name)]=null;
        Apply(changes);
        return kind+" 视频触发器动作已卸载。\r\n目标："+root+"\r\n请重启编辑器；已使用视频动作的地图需先删除或替换相关动作。\r\n其他模块、地图、MIX 和视频未改动，已有 .bak 备份保留。";
    }
    static void Apply(Dictionary<string,byte[]> writes){
        var previous=new Dictionary<string,byte[]>();var changed=new List<string>();
        try{
            foreach(var job in writes){byte[] old=File.Exists(job.Key)?File.ReadAllBytes(job.Key):null;previous[job.Key]=old;if(old==null&&job.Value==null||old!=null&&job.Value!=null&&old.SequenceEqual(job.Value))continue;
                if(old!=null&&!File.Exists(job.Key+".bak"))File.WriteAllBytes(job.Key+".bak",old);
                if(job.Value==null)File.Delete(job.Key);else Write(job.Key,job.Value);changed.Add(job.Key);
            }
            foreach(var job in writes)if(job.Value==null?File.Exists(job.Key):!File.ReadAllBytes(job.Key).SequenceEqual(job.Value))throw new IOException("文件校验失败："+job.Key);
        }catch{foreach(string path in changed.AsEnumerable().Reverse()){if(previous[path]==null){if(File.Exists(path))File.Delete(path);}else Write(path,previous[path]);}throw;}
    }
}
