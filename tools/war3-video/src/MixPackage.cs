using System;
using System.IO;
using System.Text;
using System.Collections.Generic;

public class MixEntry {
    public string Name, Source;
    public long Offset, Length;
    public MixEntry(string name,string source,long offset,long length){Name=name;Source=source;Offset=offset;Length=length;}
}
public class MixPackage {
    public const int FooterSize=56;
    public string PathName, Id;
    public long PlayerOffset, PlayerLength;
    public List<MixEntry> Entries=new List<MixEntry>();
    static byte[] Magic=Encoding.ASCII.GetBytes("WVMIX001");
    public static bool ValidName(string name){return !String.IsNullOrEmpty(name)&&name.Length<=120&&name.EndsWith(".mp4",StringComparison.OrdinalIgnoreCase)&&name.IndexOfAny(Path.GetInvalidFileNameChars())<0&&Path.GetFileName(name)==name;}
    static void Range(long offset,long length,long end){if(offset<0||length<=0||offset>end||length>end-offset)throw new InvalidDataException("视频包数据范围无效。");}
    public static MixPackage Open(string path) {
        path=Path.GetFullPath(path);
        using(var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read))using(var reader=new BinaryReader(file,Encoding.UTF8)) {
            if(file.Length<FooterSize)throw new InvalidDataException("不是 War3 视频 MIX 包。");
            long footer=file.Length-FooterSize;file.Position=footer;
            if(Encoding.ASCII.GetString(reader.ReadBytes(8))!="WVMIX001")throw new InvalidDataException("不是 War3 视频 MIX 包，请用本工具新建。");
            var result=new MixPackage{PathName=path,PlayerOffset=reader.ReadInt64(),PlayerLength=reader.ReadInt64()};
            long index=reader.ReadInt64(),size=reader.ReadInt64();byte[] id=reader.ReadBytes(16);
            result.Id=BitConverter.ToString(id).Replace("-","").ToLowerInvariant();
            Range(result.PlayerOffset,result.PlayerLength,index);Range(index,size,footer);
            if(size>1024*1024||index+size!=footer||result.PlayerOffset<1024)throw new InvalidDataException("视频包索引无效。");
            file.Position=index;int count=reader.ReadInt32();if(count<0||count>4096)throw new InvalidDataException("视频条目数量无效。");
            var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            long previous=result.PlayerOffset+result.PlayerLength;
            for(int i=0;i<count;i++) {
                int n=reader.ReadUInt16();if(n==0||n>480)throw new InvalidDataException("文件名无效。");
                string name=new UTF8Encoding(false,true).GetString(reader.ReadBytes(n));
                long offset=reader.ReadInt64(),length=reader.ReadInt64();
                if(!ValidName(name)||!names.Add(name)||offset<previous)throw new InvalidDataException("视频文件名或布局无效。");
                Range(offset,length,index);previous=offset+length;result.Entries.Add(new MixEntry(name,path,offset,length));
                if(file.Position>index+size)throw new InvalidDataException("索引越界。");
            }
            if(file.Position!=footer)throw new InvalidDataException("索引长度无效。");
            return result;
        }
    }
    public static void Copy(Stream source,Stream output,long length) {
        byte[] buffer=new byte[1024*1024];
        while(length>0){int n=source.Read(buffer,0,(int)Math.Min(buffer.Length,length));if(n<=0)throw new EndOfStreamException("视频数据不完整。");output.Write(buffer,0,n);length-=n;}
    }
    public static void Export(MixEntry entry,string destination) {
        string temp=destination+"."+Guid.NewGuid().ToString("N")+".tmp";
        try {
            using(var input=new FileStream(entry.Source,FileMode.Open,FileAccess.Read,FileShare.Read))using(var output=File.Create(temp)){input.Position=entry.Offset;Copy(input,output,entry.Length);}
            if(File.Exists(destination))File.Replace(temp,destination,null);else File.Move(temp,destination);
        }finally{if(File.Exists(temp))File.Delete(temp);}
    }
    public string Resolve(string name,string cache) {
        if(!name.EndsWith(".mp4",StringComparison.OrdinalIgnoreCase))name+=".mp4";
        if(!ValidName(name))return null;
        MixEntry entry=Entries.Find(e=>e.Name.Equals(name,StringComparison.OrdinalIgnoreCase));if(entry==null)return null;
        string folder=Path.Combine(cache,Id,"clips");Directory.CreateDirectory(folder);
        string path=Path.Combine(folder,entry.Name);
        if(!File.Exists(path)||new FileInfo(path).Length!=entry.Length) {
            try{Export(entry,path);}
            catch(IOException){if(!File.Exists(path)||new FileInfo(path).Length!=entry.Length)throw;}
            // A second client may have atomically completed the same cache file.
        }
        return path;
    }
    public static void Build(string destination,Stream bootstrap,Stream player,IList<MixEntry> entries) {
        if(entries.Count>4096)throw new InvalidDataException("最多4096段视频。");
        var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach(var e in entries){if(!ValidName(e.Name)||!names.Add(e.Name)||e.Length<=0)throw new InvalidDataException("视频名重复或文件无效。");}
        destination=Path.GetFullPath(destination);string temp=destination+"."+Guid.NewGuid().ToString("N")+".tmp";
        try {
            using(var file=File.Create(temp))using(var writer=new BinaryWriter(file,Encoding.UTF8)) {
                Copy(bootstrap,file,bootstrap.Length);long exeOffset=file.Position;Copy(player,file,player.Length);long exeLength=file.Position-exeOffset;
                var packed=new List<MixEntry>();
                foreach(var entry in entries) {
                    long offset=file.Position;
                    using(var input=new FileStream(entry.Source,FileMode.Open,FileAccess.Read,FileShare.Read)){input.Position=entry.Offset;Copy(input,file,entry.Length);}
                    packed.Add(new MixEntry(entry.Name,destination,offset,entry.Length));
                }
                long index=file.Position;writer.Write(packed.Count);
                foreach(var e in packed){byte[] name=Encoding.UTF8.GetBytes(e.Name);writer.Write((ushort)name.Length);writer.Write(name);writer.Write(e.Offset);writer.Write(e.Length);}
                long size=file.Position-index;
                writer.Write(Magic);writer.Write(exeOffset);writer.Write(exeLength);writer.Write(index);writer.Write(size);writer.Write(Guid.NewGuid().ToByteArray());writer.Flush();file.Flush(true);
            }
            Open(temp); // Reject malformed output before replacing the working package.
            if(File.Exists(destination))File.Replace(temp,destination,destination+".bak");else File.Move(temp,destination);
        }finally{if(File.Exists(temp))File.Delete(temp);}
    }
}
