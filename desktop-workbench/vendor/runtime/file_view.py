"""Explicit client file-view profile; never changes map contents or script hashes."""
from pathlib import Path
import zlib

def apply_file_view(session,config,kkwe,profile='native'):
    if profile=='native':return config
    if profile!='kkwe_8m':raise ValueError('Unsupported file_view profile')
    raw=Path(session['runtime_map']).read_bytes();words=config['hash_words']
    if words[0]!=len(raw) or words[1]!=(zlib.crc32(raw)&0xffffffff):
        raise ValueError('Native file metadata mismatch')
    plugin=(Path(kkwe)/'plugin/warcraft3/yd_size_limit.dll').read_bytes()
    if b'\x81\xfe\xff\xff\x7f\x00' not in plugin or 'storm.dll'.encode('utf-16le') not in plugin:
        raise ValueError('Unrecognized size-limit plugin; independently validate client file view')
    count=min(len(raw),0x7fffff);info=zlib.crc32(raw[:count])&0xffffffff
    path=Path(config['cwd'])/'map.cfg';text=path.read_text(encoding='ascii')
    (path.parent/'map.native.cfg').write_text(text,encoding='ascii')
    def le(value):return ' '.join(str(b) for b in value.to_bytes(4,'little'))
    lines=[('map_size = '+le(count)) if l.startswith('map_size = ') else ('map_info = '+le(info)) if l.startswith('map_info = ') else l for l in text.splitlines()]
    path.write_text('\n'.join(lines)+'\n',encoding='ascii')
    config['client_file_view']={'native_bytes':len(raw),'reported_bytes':count,'native_info':words[1],'reported_info':info,'profile':profile}
    return config
