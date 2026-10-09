using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Drawing;
using System.Diagnostics;

class MixManager : Form {
    List<MixEntry> entries=new List<MixEntry>();string current;bool dirty,busy;
    ListView list=new ListView{Dock=DockStyle.Fill,View=View.Details,FullRowSelect=true,MultiSelect=true,HideSelection=false};
    Label info=new Label{Dock=DockStyle.Fill,Padding=new Padding(0,6,0,0)};
    FlowLayoutPanel buttons=new FlowLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(5),WrapContents=false};
    Button save;
    Panel editorBar=new Panel{Dock=DockStyle.Fill};
    TextBox editorPath=new TextBox{ReadOnly=true,Dock=DockStyle.Fill};
    ComboBox editorKind=new ComboBox{DropDownStyle=ComboBoxStyle.DropDownList,Width=80};
    Label editorHint=new Label{AutoSize=true,Text="完成后重启编辑器",Margin=new Padding(12,6,0,0)};
    void SelectEditor(bool folder){
        string path=null;
        if(folder){using(var dialog=new FolderBrowserDialog{Description="选择 KKWE / YDWE 安装目录"})if(dialog.ShowDialog(this)==DialogResult.OK)path=dialog.SelectedPath;}
        else{using(var dialog=new OpenFileDialog{Filter="编辑器启动程序|*.exe",Title="选择 KKWE / YDWE 启动程序"})if(dialog.ShowDialog(this)==DialogResult.OK)path=dialog.FileName;}
        if(path==null)return;
        try{editorPath.Text=GuiInstaller.Resolve(path);editorKind.SelectedItem=GuiInstaller.Detect(editorPath.Text);editorHint.Text="已识别目录；确认类型后点击安装，完成后重启编辑器。";}
        catch(Exception e){MessageBox.Show(this,e.Message,"无法识别编辑器");}
    }
    async void InstallGui(bool uninstall){
        if(busy)return;
        if(editorPath.Text==""){MessageBox.Show(this,"先选择编辑器程序或安装目录。");return;}
        string target=editorPath.Text,kind=(string)editorKind.SelectedItem,operation=uninstall?"卸载":"安装";
        if(uninstall&&MessageBox.Show(this,"卸载此编辑器的视频触发器动作？\r\n"+target+"\r\n已使用视频动作的地图需先删除或替换相关动作。", "卸载触发器动作",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes)return;
        busy=true;buttons.Enabled=false;editorBar.Enabled=false;list.Enabled=false;editorHint.Text="正在"+operation+"视频触发器动作…";
        try{string result=await Task.Run(()=>uninstall?GuiInstaller.Uninstall(target,kind):GuiInstaller.Install(target,kind));editorHint.Text=kind+" "+operation+"完成，请重启编辑器。";MessageBox.Show(this,result,operation+"完成",MessageBoxButtons.OK,MessageBoxIcon.Information);}
        catch(Exception e){editorHint.Text=operation+"失败："+e.Message;MessageBox.Show(this,e.Message+"\r\n若提示访问被拒绝，请以管理员身份运行本工具。","触发器动作"+operation+"失败");}
        finally{busy=false;buttons.Enabled=true;editorBar.Enabled=true;list.Enabled=true;}
    }
    Button AddButton(string text,EventHandler handler){var b=new Button{Text=text,AutoSize=true,Height=28};b.Click+=handler;buttons.Controls.Add(b);return b;}
    void RefreshList(){list.Items.Clear();foreach(var e in entries){var item=new ListViewItem(e.Name);item.SubItems.Add((e.Length/1048576.0).ToString("0.00")+" MB");item.Tag=e;list.Items.Add(item);}Text="War3 MIX 视频管理器 v"+AppVersion.Number+(current==null?" — 新包":" — "+Path.GetFileName(current))+(dirty?" *":"");info.Text="内置DLL和播放器 · "+entries.Count+" 段视频 · "+(entries.Sum(e=>e.Length)/1048576.0).ToString("0.00")+" MB · 只分发一个 MIX";}
    bool Discard(){return !dirty || MessageBox.Show(this,"放弃尚未保存的修改？","未保存修改",MessageBoxButtons.YesNo,MessageBoxIcon.Question)==DialogResult.Yes;}
    void OpenPackage(string path){if(!Discard())return;try{var package=MixPackage.Open(path);entries=package.Entries;current=package.PathName;dirty=false;RefreshList();}catch(Exception e){MessageBox.Show(this,e.Message,"打开失败");}}
    void Import(string[] files) {
        foreach(string file in files){string name=Path.GetFileName(file);if(!MixPackage.ValidName(name)){MessageBox.Show(this,"仅支持MP4，文件名不超过120字符："+name);continue;}
            var existing=entries.Find(e=>e.Name.Equals(name,StringComparison.OrdinalIgnoreCase));
            if(existing!=null && MessageBox.Show(this,"替换包中的 "+name+"？","同名视频",MessageBoxButtons.YesNo)==DialogResult.No)continue;
            long size=new FileInfo(file).Length;if(size==0){MessageBox.Show(this,"文件为空："+name);continue;}
            if(existing!=null)entries.Remove(existing);entries.Add(new MixEntry(name,Path.GetFullPath(file),0,size));dirty=true;
        }RefreshList();
    }
    async Task Work(Action action,string text) {
        if(busy)return;busy=true;buttons.Enabled=false;editorBar.Enabled=false;list.Enabled=false;info.Text=text;
        try{await Task.Run(action);}catch(Exception e){MessageBox.Show(this,e.Message+"\n若游戏正在使用此MIX，请先退出游戏。","操作失败");}
        finally{busy=false;buttons.Enabled=true;editorBar.Enabled=true;list.Enabled=true;RefreshList();}
    }
    async void SavePackage(bool saveAs) {
        string dest=current;
        if(saveAs||dest==null){using(var dialog=new SaveFileDialog{Filter="War3 视频包|*.mix",FileName=current==null?"War3Video.mix":Path.GetFileName(current)}){if(dialog.ShowDialog(this)!=DialogResult.OK)return;dest=dialog.FileName;}}
        string target=dest;var snapshot=entries.ToList();
        await Work(delegate {
            var assembly=Assembly.GetExecutingAssembly();
            using(var dll=assembly.GetManifestResourceStream("bootstrap"))using(var player=assembly.GetManifestResourceStream("player"))MixPackage.Build(target,dll,player,snapshot);
            var package=MixPackage.Open(target);entries=package.Entries;current=package.PathName;dirty=false;
        },"正在封装视频，请稍候…");
    }
    async void ExportSelected() {
        var chosen=list.SelectedItems.Cast<ListViewItem>().Select(i=>(MixEntry)i.Tag).ToList();if(chosen.Count==0){MessageBox.Show(this,"先选择需要导出的视频，可多选。");return;}
        var jobs=new List<KeyValuePair<MixEntry,string>>();
        if(chosen.Count==1){using(var dialog=new SaveFileDialog{Filter="MP4视频|*.mp4",FileName=chosen[0].Name}){if(dialog.ShowDialog(this)!=DialogResult.OK)return;jobs.Add(new KeyValuePair<MixEntry,string>(chosen[0],dialog.FileName));}}
        else {using(var dialog=new FolderBrowserDialog{Description="选择导出文件夹"}){if(dialog.ShowDialog(this)!=DialogResult.OK)return;foreach(var e in chosen){string path=Path.Combine(dialog.SelectedPath,e.Name);if(File.Exists(path)&&MessageBox.Show(this,"覆盖 "+e.Name+"？","导出",MessageBoxButtons.YesNo)==DialogResult.No)continue;jobs.Add(new KeyValuePair<MixEntry,string>(e,path));}}}
        await Work(delegate{foreach(var job in jobs){if(Path.GetFullPath(job.Value).Equals(Path.GetFullPath(job.Key.Source),StringComparison.OrdinalIgnoreCase))throw new IOException("不能覆盖视频源文件或正在读取的包。");MixPackage.Export(job.Key,job.Value);}},"正在导出视频…");
    }
    MixManager() {
        Text="War3 MIX 视频管理器 v"+AppVersion.Number;ClientSize=new Size(940,620);MinimumSize=new Size(900,650);StartPosition=FormStartPosition.CenterScreen;Font=new Font("Microsoft YaHei UI",9);AutoScaleMode=AutoScaleMode.Dpi;
        var layout=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(12),ColumnCount=1,RowCount=4};
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,62));layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,110));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,28));Controls.Add(layout);
        var packGroup=new GroupBox{Text="视频包",Dock=DockStyle.Fill};packGroup.Controls.Add(buttons);layout.Controls.Add(packGroup,0,0);
        var body=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=2,RowCount=1,Margin=new Padding(0,8,0,8)};
        body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));body.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,280));layout.Controls.Add(body,0,1);
        var clipsGroup=new GroupBox{Text="包内视频 · 支持拖入 MP4",Dock=DockStyle.Fill,Padding=new Padding(8)};clipsGroup.Controls.Add(list);body.Controls.Add(clipsGroup,0,0);
        list.Columns.Add("视频文件名",400);list.Columns.Add("大小",105);
        list.Resize+=delegate{if(list.ClientSize.Width>140)list.Columns[0].Width=list.ClientSize.Width-125;};
        var helpGroup=new GroupBox{Text="使用说明",Dock=DockStyle.Fill,Padding=new Padding(12),Margin=new Padding(8,3,0,3)};body.Controls.Add(helpGroup,1,0);
        var helpLayout=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=1,RowCount=3};helpLayout.RowStyles.Add(new RowStyle(SizeType.Percent,100));helpLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,52));helpLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,26));helpGroup.Controls.Add(helpLayout);
        var help=new Label{Dock=DockStyle.Fill,Text="作者使用\r\n新建 MIX 自带启动器和播放器，导入 MP4（含音轨）、保存后分发给玩家。\r\n选择编辑器目录安装触发器动作，重启后在“视频播放”分类填写文件名。\r\n\r\n玩家使用\r\n把 MIX 包放到魔兽根目录即可。\r\n\r\n播放方式\r\n在魔兽窗口上覆盖视频，只做本地表现，不回写同步状态。触发器动作需同步调用；视频音量不受游戏内声音设置影响。\r\n未安装视频包会自动跳过播放。"};helpLayout.Controls.Add(help,0,0);
        helpLayout.Controls.Add(new Label{Dock=DockStyle.Fill,Text="作者：半盏丶时光\r\n由 GPT-6 制作\r\nQQ：1076755135"},0,1);
        var github=new LinkLabel{Text="GitHub · 源码",AutoSize=true};github.LinkClicked+=delegate{try{Process.Start(new ProcessStartInfo("https://github.com/Bzsga/war3-command-bridge/tree/main/tools/war3-video"){UseShellExecute=true});}catch(Exception e){MessageBox.Show(this,e.Message,"无法打开 GitHub");}};helpLayout.Controls.Add(github,0,2);
        var editorGroup=new GroupBox{Text="地图作者 · 为编辑器安装触发器动作",Dock=DockStyle.Fill,Padding=new Padding(8)};editorGroup.Controls.Add(editorBar);layout.Controls.Add(editorGroup,0,2);layout.Controls.Add(info,0,3);
        var editorLayout=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=1,RowCount=2};editorLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,32));editorLayout.RowStyles.Add(new RowStyle(SizeType.Percent,100));editorBar.Controls.Add(editorLayout);
        var targetRow=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=3,RowCount=1,Margin=new Padding(0)};targetRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));targetRow.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,100));targetRow.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,120));editorLayout.Controls.Add(targetRow,0,0);targetRow.Controls.Add(editorPath,0,0);
        editorKind.Items.AddRange(new object[]{"KKWE","YDWE"});editorKind.SelectedIndex=0;
        var directory=new Button{Text="选择目录…",AutoSize=true};directory.Click+=delegate{SelectEditor(true);};targetRow.Controls.Add(directory,1,0);
        var choose=new Button{Text="选择启动程序…",AutoSize=true};choose.Click+=delegate{SelectEditor(false);};targetRow.Controls.Add(choose,2,0);
        var editorActions=new FlowLayoutPanel{Dock=DockStyle.Fill,Margin=new Padding(0)};editorLayout.Controls.Add(editorActions,0,1);editorActions.Controls.Add(editorKind);
        var install=new Button{Text="安装触发器动作",AutoSize=true};install.Click+=delegate{InstallGui(false);};editorActions.Controls.Add(install);
        var uninstall=new Button{Text="卸载触发器动作",AutoSize=true};uninstall.Click+=delegate{InstallGui(true);};editorActions.Controls.Add(uninstall);editorActions.Controls.Add(editorHint);
        AddButton("新建",delegate{if(Discard()){entries.Clear();current=null;dirty=false;RefreshList();}});
        AddButton("打开 MIX…",delegate{using(var dialog=new OpenFileDialog{Filter="War3 视频包|*.mix"})if(dialog.ShowDialog(this)==DialogResult.OK)OpenPackage(dialog.FileName);});
        AddButton("导入 MP4…",delegate{using(var dialog=new OpenFileDialog{Filter="MP4视频|*.mp4",Multiselect=true})if(dialog.ShowDialog(this)==DialogResult.OK)Import(dialog.FileNames);});
        AddButton("导出所选…",delegate{ExportSelected();});
        AddButton("移除所选",delegate{foreach(ListViewItem item in list.SelectedItems)entries.Remove((MixEntry)item.Tag);dirty=true;RefreshList();});
        save=AddButton("保存",delegate{SavePackage(false);});AddButton("另存为…",delegate{SavePackage(true);});
        list.AllowDrop=true;list.DragEnter+=delegate(object s,DragEventArgs e){if(!busy&&e.Data.GetDataPresent(DataFormats.FileDrop))e.Effect=DragDropEffects.Copy;};
        list.DragDrop+=delegate(object s,DragEventArgs e){var files=(string[])e.Data.GetData(DataFormats.FileDrop);if(files.Length==1&&Path.GetExtension(files[0]).Equals(".mix",StringComparison.OrdinalIgnoreCase))OpenPackage(files[0]);else Import(files);};
        FormClosing+=delegate(object s,FormClosingEventArgs e){if(busy||!Discard())e.Cancel=true;};
        RefreshList();
    }
    [STAThread] static int Main(string[] args) {
        // CLI shares the same streaming archive engine for repeatable automation.
        if(args.Length>0&&args[0].StartsWith("--")) {
            try {
                var assembly=Assembly.GetExecutingAssembly();
                if(args[0]=="--install-gui"&&args.Length==3){GuiInstaller.Install(args[1],args[2]);return 0;}
                if(args[0]=="--uninstall-gui"&&args.Length==3){GuiInstaller.Uninstall(args[1],args[2]);return 0;}
                if(args[0]=="--pack"&&args.Length>=2){var entries=new List<MixEntry>();foreach(string p in args.Skip(2))entries.Add(new MixEntry(Path.GetFileName(p),Path.GetFullPath(p),0,new FileInfo(p).Length));using(var dll=assembly.GetManifestResourceStream("bootstrap"))using(var player=assembly.GetManifestResourceStream("player"))MixPackage.Build(args[1],dll,player,entries);}
                else if((args[0]=="--import"||args[0]=="--remove")&&args.Length>=4){var p=MixPackage.Open(args[1]);foreach(string value in args.Skip(3)){string name=Path.GetFileName(value);p.Entries.RemoveAll(e=>e.Name.Equals(name,StringComparison.OrdinalIgnoreCase));if(args[0]=="--import")p.Entries.Add(new MixEntry(name,Path.GetFullPath(value),0,new FileInfo(value).Length));}using(var dll=assembly.GetManifestResourceStream("bootstrap"))using(var player=assembly.GetManifestResourceStream("player"))MixPackage.Build(args[2],dll,player,p.Entries);}
                else if(args[0]=="--refresh"&&args.Length==3){var p=MixPackage.Open(args[1]);using(var dll=assembly.GetManifestResourceStream("bootstrap"))using(var player=assembly.GetManifestResourceStream("player"))MixPackage.Build(args[2],dll,player,p.Entries);}
                else if(args[0]=="--export"&&args.Length==3){var pack=MixPackage.Open(args[1]);Directory.CreateDirectory(args[2]);foreach(var entry in pack.Entries){string path=Path.Combine(args[2],entry.Name);if(File.Exists(path))throw new IOException("导出目标已存在："+path);MixPackage.Export(entry,path);}}
                else if(args[0]=="--list"&&args.Length==3){var p=MixPackage.Open(args[1]);File.WriteAllLines(args[2],p.Entries.Select(e=>e.Name+"\t"+e.Length));}
                else throw new ArgumentException("参数：--pack 输出.mix [视频.mp4…]；--import 输入.mix 输出.mix 视频.mp4…；--remove 输入.mix 输出.mix 文件名…；--export 输入.mix 新目录；--list 输入.mix 清单.txt");
                return 0;
            }catch(Exception e){File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"mix-manager-error.log"),e.ToString());return 1;}
        }
        Application.EnableVisualStyles();var window=new MixManager();if(args.Length==1)window.OpenPackage(args[0]);Application.Run(window);return 0;
    }
}
