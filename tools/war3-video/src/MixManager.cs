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
    TabControl workflows=new TabControl{Dock=DockStyle.Fill};
    TextBox gamePath=new TextBox{ReadOnly=true,Dock=DockStyle.Fill};
    TextBox mixName=new TextBox{Text="War3Video.mix",Width=180};
    CheckBox installOnCreate=new CheckBox{Text="为编辑器安装触发器动作",Checked=true,AutoSize=true};
    bool allowUnrecognizedGame,allowUnrecognizedEditor;
    Panel editorBar=new Panel{Dock=DockStyle.Fill};
    TextBox editorPath=new TextBox{ReadOnly=true,Dock=DockStyle.Fill};
    ComboBox editorKind=new ComboBox{DropDownStyle=ComboBoxStyle.DropDownList,Width=80};
    Label editorHint=new Label{AutoSize=true,Text="完成后重启编辑器",Margin=new Padding(12,6,0,0)};
    void SelectEditor(bool folder){
        string path=null;
        if(folder){using(var dialog=new FolderBrowserDialog{Description="选择 KKWE / YDWE 安装目录"})if(dialog.ShowDialog(this)==DialogResult.OK)path=dialog.SelectedPath;}
        else{using(var dialog=new OpenFileDialog{Filter="编辑器启动程序|*.exe",Title="选择 KKWE / YDWE 启动程序"})if(dialog.ShowDialog(this)==DialogResult.OK)path=dialog.FileName;}
        if(path==null)return;
        try{string resolved=QuickCreator.EditorRoot(path);editorPath.Text=resolved;allowUnrecognizedEditor=false;editorKind.SelectedItem=GuiInstaller.Detect(resolved);editorHint.Text="已识别目录，创建后重启编辑器。";}
        catch(Exception e){if(MessageBox.Show(this,e.Message+"\r\n仍然使用这个目录？", "目录未识别",MessageBoxButtons.YesNo,MessageBoxIcon.Warning)==DialogResult.Yes){editorPath.Text=File.Exists(path)?Path.GetDirectoryName(Path.GetFullPath(path)):Path.GetFullPath(path);allowUnrecognizedEditor=true;editorKind.SelectedItem=GuiInstaller.Detect(editorPath.Text);editorHint.Text="已手动选择目录；安装时会检查配置布局。";}}
    }
    void SelectGame(){using(var dialog=new FolderBrowserDialog{Description="选择含 war3.exe 的魔兽根目录"}){
        if(dialog.ShowDialog(this)!=DialogResult.OK)return;
        bool missing=!File.Exists(Path.Combine(dialog.SelectedPath,"war3.exe"));
        if(missing&&MessageBox.Show(this,"没有找到 war3.exe。仍然使用这个目录？", "目录未识别",MessageBoxButtons.YesNo,MessageBoxIcon.Warning)!=DialogResult.Yes)return;
        allowUnrecognizedGame=missing;
        gamePath.Text=Path.GetFullPath(dialog.SelectedPath);
    }}
    void InstallRegistry(){
        if(MessageBox.Show(this,"将启用当前 Windows 用户的魔兽本地文件读取。\r\n继续后，Windows 会再次询问是否导入注册表。\r\n完成后请重启魔兽。\r\n\r\n是否继续？","安装注册表",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes)return;
        try{
            string directory=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"War3MixManager");Directory.CreateDirectory(directory);
            string path=Path.Combine(directory,"启用魔兽本地文件读取.reg");
            using(var resource=Assembly.GetExecutingAssembly().GetManifestResourceStream("local-files-registry")){
                if(resource==null)throw new IOException("工具缺少内置注册表文件。");
                using(var memory=new MemoryStream()){resource.CopyTo(memory);byte[] data=memory.ToArray();if(!File.Exists(path)||!File.ReadAllBytes(path).SequenceEqual(data))File.WriteAllBytes(path,data);}
            }
            Process.Start(new ProcessStartInfo(path){UseShellExecute=true});
        }catch(Exception e){MessageBox.Show(this,e.Message,"无法打开注册表安装提示");}
    }
    bool? ExistingChoice(CreationPlan plan){
        if(plan.Existing==null)return false;
        using(var dialog=new Form{Text="根目录已有视频包",ClientSize=new Size(560,160),StartPosition=FormStartPosition.CenterParent,FormBorderStyle=FormBorderStyle.FixedDialog,MaximizeBox=false,MinimizeBox=false,Font=Font}){
            var text=new Label{Dock=DockStyle.Fill,Padding=new Padding(14),Text="已有："+Path.GetFileName(plan.Existing)+"\r\n新包："+Path.GetFileName(plan.Target)+"\r\n请选择保留旧视频一起更新，或仅使用本次视频。原包会备份并停用。"};dialog.Controls.Add(text);
            var choices=new FlowLayoutPanel{Dock=DockStyle.Bottom,Height=44,Padding=new Padding(8)};dialog.Controls.Add(choices);
            var keep=new Button{Text="保留旧视频并更新",AutoSize=true,DialogResult=DialogResult.Yes};var replace=new Button{Text="仅使用本次视频",AutoSize=true,DialogResult=DialogResult.No};var cancel=new Button{Text="取消",AutoSize=true,DialogResult=DialogResult.Cancel};choices.Controls.AddRange(new Control[]{keep,replace,cancel});dialog.CancelButton=cancel;
            var result=dialog.ShowDialog(this);return result==DialogResult.Yes?true:result==DialogResult.No?(bool?)false:null;
        }
    }
    async void QuickCreate(){
        if(busy)return;CreationPlan plan;bool install=installOnCreate.Checked,unrecognizedEditor=allowUnrecognizedEditor;string editor=editorPath.Text,kind=(string)editorKind.SelectedItem;
        try{if(entries.Count==0)throw new IOException("请先导入视频，再点击新建 MIX。");plan=QuickCreator.Plan(gamePath.Text,mixName.Text,allowUnrecognizedGame);if(install&&!unrecognizedEditor)QuickCreator.EditorRoot(editor);}
        catch(Exception e){MessageBox.Show(this,e.Message,"还需要一步");return;}
        bool? keep=ExistingChoice(plan);if(!keep.HasValue)return;var snapshot=entries.ToList();CreationResult result=null;
        busy=true;workflows.Enabled=false;editorBar.Enabled=false;list.Enabled=false;info.Text="正在创建 MIX"+(install?"并安装触发器动作…":"…");
        try{result=await Task.Run(()=>QuickCreator.Create(plan,snapshot,keep.Value,install,editor,kind,unrecognizedEditor));var package=MixPackage.Open(result.Path);entries=package.Entries;current=package.PathName;dirty=false;mixName.Text=Path.GetFileName(result.Path);}
        catch(Exception e){MessageBox.Show(this,e.Message+"\r\n若文件被占用，请退出正在使用它的游戏或工具后重试。","创建失败");}
        finally{busy=false;workflows.Enabled=true;editorBar.Enabled=true;list.Enabled=true;RefreshList();}
        if(result==null)return;
        string message="已在以下位置新建 MIX：\r\n"+result.Path+"\r\n\r\n"+(result.EditorInstalled?"已为编辑器安装触发器动作。请重启编辑器。":install?"MIX 已创建，触发器动作安装失败："+result.EditorError:"未安装触发器动作（已取消勾选）。")+"\r\n打开编辑器 → 使用“视频播放”动作，填写 "+entries[0].Name+" → 进入游戏测试。\r\n玩家只需把这个 MIX 放到魔兽根目录。";
        if(result.EditorError!=null){if(MessageBox.Show(this,message+"\r\n点击重试可单独安装，无需重新制作 MIX。","视频包已创建",MessageBoxButtons.RetryCancel,MessageBoxIcon.Warning)==DialogResult.Retry)InstallGui(false);}
        else MessageBox.Show(this,message,"创建完成",MessageBoxButtons.OK,MessageBoxIcon.Information);
    }
    async void InstallGui(bool uninstall){
        if(busy)return;
        if(editorPath.Text==""){MessageBox.Show(this,"先选择编辑器程序或安装目录。");return;}
        string target=editorPath.Text,kind=(string)editorKind.SelectedItem,operation=uninstall?"卸载":"安装";
        if(uninstall&&MessageBox.Show(this,"卸载此编辑器的视频触发器动作？\r\n"+target+"\r\n已使用视频动作的地图需先删除或替换相关动作。", "卸载触发器动作",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes)return;
        busy=true;workflows.Enabled=false;buttons.Enabled=false;editorBar.Enabled=false;list.Enabled=false;editorHint.Text="正在"+operation+"视频触发器动作…";
        try{string result=await Task.Run(()=>uninstall?GuiInstaller.Uninstall(target,kind):GuiInstaller.Install(target,kind));editorHint.Text=kind+" "+operation+"完成，请重启编辑器。";MessageBox.Show(this,result,operation+"完成",MessageBoxButtons.OK,MessageBoxIcon.Information);}
        catch(Exception e){editorHint.Text=operation+"失败："+e.Message;MessageBox.Show(this,e.Message+"\r\n若提示访问被拒绝，请以管理员身份运行本工具。","触发器动作"+operation+"失败");}
        finally{busy=false;workflows.Enabled=true;buttons.Enabled=true;editorBar.Enabled=true;list.Enabled=true;}
    }
    Button AddButton(string text,EventHandler handler){var b=new Button{Text=text,AutoSize=true,Height=28};b.Click+=handler;buttons.Controls.Add(b);return b;}
    void RefreshList(){list.Items.Clear();foreach(var e in entries){var item=new ListViewItem(e.Name);item.SubItems.Add((e.Length/1048576.0).ToString("0.00")+" MB");item.Tag=e;list.Items.Add(item);}Text="War3 MIX 视频管理器 v"+AppVersion.Number+(current==null?" — 新包":" — "+Path.GetFileName(current))+(dirty?" *":"");info.Text="内置DLL和播放器 · "+entries.Count+" 段视频 · "+(entries.Sum(e=>e.Length)/1048576.0).ToString("0.00")+" MB · 只分发一个 MIX";}
    bool Discard(){return !dirty || MessageBox.Show(this,"放弃尚未保存的修改？","未保存修改",MessageBoxButtons.YesNo,MessageBoxIcon.Question)==DialogResult.Yes;}
    void OpenPackage(string path){if(!Discard())return;try{var package=MixPackage.Open(path);entries=package.Entries;current=package.PathName;dirty=false;workflows.SelectedIndex=1;RefreshList();}catch(Exception e){MessageBox.Show(this,e.Message,"打开失败");}}
    void Import(string[] files) {
        foreach(string file in files){string name=Path.GetFileName(file);if(!MixPackage.ValidName(name)){MessageBox.Show(this,"仅支持MP4，文件名不超过120字符："+name);continue;}
            var existing=entries.Find(e=>e.Name.Equals(name,StringComparison.OrdinalIgnoreCase));
            if(existing!=null && MessageBox.Show(this,"替换包中的 "+name+"？","同名视频",MessageBoxButtons.YesNo)==DialogResult.No)continue;
            long size=new FileInfo(file).Length;if(size==0){MessageBox.Show(this,"文件为空："+name);continue;}
            if(existing!=null)entries.Remove(existing);entries.Add(new MixEntry(name,Path.GetFullPath(file),0,size));dirty=true;
        }RefreshList();
    }
    void ChooseVideos(){using(var dialog=new OpenFileDialog{Filter="MP4视频|*.mp4",Multiselect=true})if(dialog.ShowDialog(this)==DialogResult.OK)Import(dialog.FileNames);}
    void RemoveSelected(){foreach(ListViewItem item in list.SelectedItems)entries.Remove((MixEntry)item.Tag);dirty=true;RefreshList();}
    async Task Work(Action action,string text) {
        if(busy)return;busy=true;workflows.Enabled=false;buttons.Enabled=false;editorBar.Enabled=false;list.Enabled=false;info.Text=text;
        try{await Task.Run(action);}catch(Exception e){MessageBox.Show(this,e.Message+"\n若游戏正在使用此MIX，请先退出游戏。","操作失败");}
        finally{busy=false;workflows.Enabled=true;buttons.Enabled=true;editorBar.Enabled=true;list.Enabled=true;RefreshList();}
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
        Text="War3 MIX 视频管理器 v"+AppVersion.Number;ClientSize=new Size(940,730);MinimumSize=new Size(900,760);StartPosition=FormStartPosition.CenterScreen;Font=new Font("Microsoft YaHei UI",9);AutoScaleMode=AutoScaleMode.Dpi;
        var layout=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(12),ColumnCount=1,RowCount=4};
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute,184));layout.RowStyles.Add(new RowStyle(SizeType.Percent,100));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,66));layout.RowStyles.Add(new RowStyle(SizeType.Absolute,28));Controls.Add(layout);
        layout.Controls.Add(workflows,0,0);
        var quickPage=new TabPage("快速创建视频包");var managePage=new TabPage("管理已有 MIX");workflows.TabPages.Add(quickPage);workflows.TabPages.Add(managePage);
        var quickLayout=new TableLayoutPanel{Dock=DockStyle.Fill,Padding=new Padding(8),ColumnCount=1,RowCount=4};
        for(int i=0;i<4;i++)quickLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,32));quickPage.Controls.Add(quickLayout);
        var gameRow=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=3,RowCount=1,Margin=new Padding(0)};
        gameRow.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,100));gameRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));gameRow.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,110));
        gameRow.Controls.Add(new Label{Text="魔兽根目录",AutoSize=true,Margin=new Padding(0,6,0,0)},0,0);gameRow.Controls.Add(gamePath,1,0);
        var selectGame=new Button{Text="选择目录…",AutoSize=true};selectGame.Click+=delegate{SelectGame();};gameRow.Controls.Add(selectGame,2,0);quickLayout.Controls.Add(gameRow,0,0);
        var editorRow=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=3,RowCount=1,Margin=new Padding(0)};
        editorRow.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,100));editorRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));editorRow.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,110));
        editorRow.Controls.Add(new Label{Text="编辑器目录",AutoSize=true,Margin=new Padding(0,6,0,0)},0,0);editorRow.Controls.Add(editorPath,1,0);
        var selectEditor=new Button{Text="选择目录…",AutoSize=true};selectEditor.Click+=delegate{SelectEditor(true);};editorRow.Controls.Add(selectEditor,2,0);quickLayout.Controls.Add(editorRow,0,1);
        var options=new FlowLayoutPanel{Dock=DockStyle.Fill,Margin=new Padding(0)};options.Controls.Add(new Label{Text="MIX 文件名",AutoSize=true,Margin=new Padding(0,6,8,0)});options.Controls.Add(mixName);options.Controls.Add(installOnCreate);quickLayout.Controls.Add(options,0,2);
        var quickActions=new FlowLayoutPanel{Dock=DockStyle.Fill,Margin=new Padding(0)};
        var import=new Button{Text="导入视频…",AutoSize=true};import.Click+=delegate{ChooseVideos();};quickActions.Controls.Add(import);
        var remove=new Button{Text="移除所选",AutoSize=true};remove.Click+=delegate{RemoveSelected();};quickActions.Controls.Add(remove);
        var create=new Button{Text="新建 MIX",AutoSize=true};create.Click+=delegate{QuickCreate();};quickActions.Controls.Add(create);quickLayout.Controls.Add(quickActions,0,3);
        var manageLayout=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=1,RowCount=2,Padding=new Padding(8)};
        manageLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,32));manageLayout.RowStyles.Add(new RowStyle(SizeType.Percent,100));managePage.Controls.Add(manageLayout);
        manageLayout.Controls.Add(new Label{Text="打开已有 MIX 后，可增删视频、导出或保存更新。",Dock=DockStyle.Fill},0,0);manageLayout.Controls.Add(buttons,0,1);
        var body=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=2,RowCount=1,Margin=new Padding(0,8,0,8)};
        body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));body.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,280));layout.Controls.Add(body,0,1);
        var clipsGroup=new GroupBox{Text="包内视频 · 支持拖入 MP4",Dock=DockStyle.Fill,Padding=new Padding(8)};clipsGroup.Controls.Add(list);body.Controls.Add(clipsGroup,0,0);
        list.Columns.Add("视频文件名",400);list.Columns.Add("大小",105);
        list.Resize+=delegate{if(list.ClientSize.Width>140)list.Columns[0].Width=list.ClientSize.Width-125;};
        var helpGroup=new GroupBox{Text="使用说明",Dock=DockStyle.Fill,Padding=new Padding(12),Margin=new Padding(8,3,0,3)};body.Controls.Add(helpGroup,1,0);
        var helpLayout=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=1,RowCount=5};helpLayout.RowStyles.Add(new RowStyle(SizeType.Percent,100));helpLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,44));helpLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,64));helpLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,52));helpLayout.RowStyles.Add(new RowStyle(SizeType.Absolute,26));helpGroup.Controls.Add(helpLayout);
        var help=new Label{Dock=DockStyle.Fill,Text="作者上手\r\n① 选择编辑器目录和魔兽根目录\r\n② 导入视频\r\n③ 新建 MIX\r\n④ 打开或重启编辑器\r\n⑤ 使用“视频播放”触发器动作\r\n⑥ 进入游戏测试"};helpLayout.Controls.Add(help,0,0);
        var registryNote=new LinkLabel{Dock=DockStyle.Fill,Text="注：从未使用过任何外置包的作者/玩家可能需要安装注册表"};registryNote.Links.Clear();registryNote.Links.Add(registryNote.Text.IndexOf("安装注册表",StringComparison.Ordinal),"安装注册表".Length);registryNote.LinkClicked+=delegate{InstallRegistry();};helpLayout.Controls.Add(registryNote,0,1);
        helpLayout.Controls.Add(new Label{Dock=DockStyle.Fill,Text="玩家只需把 MIX 放到魔兽根目录，没安装会跳过播放。\r\n视频覆盖游戏窗口，声音独立播放。"},0,2);
        helpLayout.Controls.Add(new Label{Dock=DockStyle.Fill,Text="作者：半盏丶时光\r\n由 GPT-6 制作\r\nQQ：1076755135"},0,3);
        var github=new LinkLabel{Text="GitHub · 源码",AutoSize=true};github.LinkClicked+=delegate{try{Process.Start(new ProcessStartInfo("https://github.com/Bzsga/war3-command-bridge/tree/main/tools/war3-video"){UseShellExecute=true});}catch(Exception e){MessageBox.Show(this,e.Message,"无法打开 GitHub");}};helpLayout.Controls.Add(github,0,4);
        var editorGroup=new GroupBox{Text="触发器动作维护 · KKWE / YDWE",Dock=DockStyle.Fill,Padding=new Padding(8)};editorGroup.Controls.Add(editorBar);layout.Controls.Add(editorGroup,0,2);layout.Controls.Add(info,0,3);
        editorKind.Items.AddRange(new object[]{"KKWE","YDWE"});editorKind.SelectedIndex=0;
        var editorActions=new FlowLayoutPanel{Dock=DockStyle.Fill,Margin=new Padding(0)};editorBar.Controls.Add(editorActions);editorActions.Controls.Add(editorKind);
        var choose=new Button{Text="选择编辑器…",AutoSize=true};choose.Click+=delegate{SelectEditor(true);};editorActions.Controls.Add(choose);
        var install=new Button{Text="安装触发器动作",AutoSize=true};install.Click+=delegate{InstallGui(false);};editorActions.Controls.Add(install);
        var uninstall=new Button{Text="卸载触发器动作",AutoSize=true};uninstall.Click+=delegate{InstallGui(true);};editorActions.Controls.Add(uninstall);editorActions.Controls.Add(editorHint);
        AddButton("清空列表",delegate{if(Discard()){entries.Clear();current=null;dirty=false;RefreshList();}});
        AddButton("打开 MIX…",delegate{using(var dialog=new OpenFileDialog{Filter="War3 视频包|*.mix"})if(dialog.ShowDialog(this)==DialogResult.OK)OpenPackage(dialog.FileName);});
        AddButton("导入视频…",delegate{ChooseVideos();});
        AddButton("导出所选…",delegate{ExportSelected();});
        AddButton("移除所选",delegate{RemoveSelected();});
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
                if(args[0]=="--quick-create"&&args.Length>=7){
                    var selected=args.Skip(6).Select(p=>new MixEntry(Path.GetFileName(p),Path.GetFullPath(p),0,new FileInfo(p).Length)).ToList();
                    var plan=QuickCreator.Plan(args[1],args[2]);var result=QuickCreator.Create(plan,selected,args[5]=="keep",args[3]!="-",args[3],args[4]);
                    if(result.EditorError!=null){File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"mix-manager-error.log"),"MIX 已创建："+result.Path+"；触发器安装失败："+result.EditorError);return 2;}return 0;
                }

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
