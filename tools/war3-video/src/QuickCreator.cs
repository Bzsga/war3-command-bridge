using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using System.Threading;

public class CreationPlan {
    public string Root,Target,Existing;
    public bool AllowMissingExecutable;
    public long ExistingLength;
    public DateTime ExistingWrite;
}
public class CreationResult {public string Path,EditorError;public bool EditorInstalled;}
public static class QuickCreator {
    static List<string> Packages(string root){
        var found=new List<string>();
        foreach(string path in Directory.GetFiles(root,"*.mix")){
            using(var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete)){
                if(file.Length<56)continue;file.Seek(-56,SeekOrigin.End);byte[] magic=new byte[8];if(file.Read(magic,0,8)!=8||Encoding.ASCII.GetString(magic)!="WVMIX001")continue;
            }
            MixPackage.Open(path);found.Add(path);
        }
        return found;
    }
    public static CreationPlan Plan(string root,string name,bool allowMissingExecutable=false){
        if(String.IsNullOrWhiteSpace(root))throw new IOException("请先选择魔兽根目录。");root=System.IO.Path.GetFullPath(root);
        if(!Directory.Exists(root))throw new IOException("所选目录不存在。");
        if(!allowMissingExecutable&&!File.Exists(System.IO.Path.Combine(root,"war3.exe")))throw new IOException("请选择含 war3.exe 的魔兽根目录。");
        name=name.Trim();if(name.Length==0||name.Length>120||name.IndexOfAny(System.IO.Path.GetInvalidFileNameChars())>=0||System.IO.Path.GetFileName(name)!=name||name.EndsWith(".")||name.EndsWith(" "))throw new IOException("请输入有效的 MIX 文件名，不要填写路径。");
        if(!name.EndsWith(".mix",StringComparison.OrdinalIgnoreCase))name+=".mix";
        string stem=System.IO.Path.GetFileNameWithoutExtension(name).Split('.')[0].ToUpperInvariant();
        if(new[]{"CON","PRN","AUX","NUL","COM1","COM2","COM3","COM4","COM5","COM6","COM7","COM8","COM9","LPT1","LPT2","LPT3","LPT4","LPT5","LPT6","LPT7","LPT8","LPT9"}.Contains(stem))throw new IOException("该文件名被 Windows 保留，请换一个名称。");
        var packages=Packages(root);if(packages.Count>1)throw new IOException("根目录有多个视频包："+String.Join("、",packages.Select(System.IO.Path.GetFileName))+"。请先保留一个，其他包移出根目录，再创建。");
        string target=System.IO.Path.Combine(root,name),old=packages.FirstOrDefault();
        if(File.Exists(target)&&!String.Equals(target,old,StringComparison.OrdinalIgnoreCase))throw new IOException("此名称已被其他文件使用，请换一个 MIX 名称，避免覆盖其他插件。");
        var plan=new CreationPlan{Root=root,Target=target,Existing=old,AllowMissingExecutable=allowMissingExecutable};if(old!=null){var info=new FileInfo(old);plan.ExistingLength=info.Length;plan.ExistingWrite=info.LastWriteTimeUtc;}return plan;
    }
    public static CreationResult Create(CreationPlan plan,IList<MixEntry> selected,bool keepExisting,bool install,string editor,string kind,bool allowUnrecognizedEditor=false){
        if(selected.Count==0)throw new IOException("请先导入至少一个 MP4 视频。");
        if(install){if(allowUnrecognizedEditor){if(String.IsNullOrWhiteSpace(editor)||!Directory.Exists(editor))throw new IOException("请先选择存在的编辑器目录。");}else EditorRoot(editor);}
        string lockName;using(var sha=SHA256.Create())lockName="Local\\War3VideoPackageWriter_"+BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(plan.Root.ToUpperInvariant()))).Replace("-","");
        using(var gate=new Mutex(false,lockName)){
            bool locked;try{locked=gate.WaitOne(0);}catch(AbandonedMutexException){locked=true;}if(!locked)throw new IOException("另一个工具正在操作这个魔兽目录，请稍后重试。");
            string stage=plan.Target+"."+Guid.NewGuid().ToString("N")+".pending",backup=null;bool moved=false;
            try{
                Validate(plan);
                var entries=keepExisting&&plan.Existing!=null?MixPackage.Open(plan.Existing).Entries:new List<MixEntry>();
                foreach(var entry in selected){entries.RemoveAll(e=>e.Name.Equals(entry.Name,StringComparison.OrdinalIgnoreCase));entries.Add(entry);}
                var assembly=Assembly.GetExecutingAssembly();using(var dll=assembly.GetManifestResourceStream("bootstrap"))using(var player=assembly.GetManifestResourceStream("player"))MixPackage.Build(stage,dll,player,entries);
                Validate(plan);
                if(plan.Existing!=null){backup=plan.Existing+".bak";if(File.Exists(backup))backup=plan.Existing+"."+Guid.NewGuid().ToString("N")+".bak";}
                if(String.Equals(plan.Existing,plan.Target,StringComparison.OrdinalIgnoreCase))File.Replace(stage,plan.Target,backup);
                else{if(plan.Existing!=null){File.Move(plan.Existing,backup);moved=true;}try{File.Move(stage,plan.Target);}catch{if(moved){File.Move(backup,plan.Existing);moved=false;}throw;}}
            }finally{if(File.Exists(stage))File.Delete(stage);gate.ReleaseMutex();}
        }
        var result=new CreationResult{Path=plan.Target};
        if(install){try{GuiInstaller.Install(editor,kind);result.EditorInstalled=true;}catch(Exception e){result.EditorError=e.Message;}}
        return result;
    }
    static void Validate(CreationPlan plan){
        var fresh=Plan(plan.Root,System.IO.Path.GetFileName(plan.Target),plan.AllowMissingExecutable);
        if(!String.Equals(fresh.Existing,plan.Existing,StringComparison.OrdinalIgnoreCase)||fresh.ExistingLength!=plan.ExistingLength||fresh.ExistingWrite!=plan.ExistingWrite)throw new IOException("目录中的视频包已变化，请重新创建。");
    }
    public static string EditorRoot(string path){
        if(String.IsNullOrWhiteSpace(path))throw new IOException("请先选择编辑器目录，或取消勾选安装触发器动作。");
        string root=GuiInstaller.Resolve(path);
        if(!File.Exists(System.IO.Path.Combine(root,"WorldEdit.exe"))&&!File.Exists(System.IO.Path.Combine(root,"KKWE.exe")))throw new IOException("编辑器目录需要包含 WorldEdit.exe 或 KKWE.exe。");
        return root;
    }
}
