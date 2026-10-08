"""Replay only the owned host's verified GAMEINFO to the local War3 client.

Capture before the client starts, then close the receiver so it never competes
for the client's UDP port. No game binary, registry, desktop or UI changes.
"""
import json
from pathlib import Path
import re
import socket
import struct
import threading
import time


def own_gameinfo(packet,name,port):
    if len(packet)<24 or packet[:2]!=b'\xf7\x30':return False
    if struct.unpack_from('<H',packet,2)[0]!=len(packet):return False
    end=packet.find(b'\0',20)
    return end>=20 and packet[20:end]==name.encode('ascii') and struct.unpack_from('<H',packet,len(packet)-2)[0]==port


class LocalDiscovery:
    def __init__(self,session):
        self.folder=Path(session['folder']);self.name='WB-'+session['session'][:8]
        self.report={'scope':'Owned local LAN room discovery only; client UDP receiver never shared','sent':0,'errors':[]}
        self.stop=threading.Event();self.thread=None
    def persist(self):
        (self.folder/'local-discovery.json').write_text(json.dumps(self.report,indent=2),encoding='utf8')
    def start_host(self,original,session,root,kkwe,run_checked):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as receiver:
            # Exclusive bind: refuse conflicts rather than steal a game's packets.
            receiver.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            receiver.bind(('0.0.0.0',6112));receiver.settimeout(.3)
            config=original(session,root,kkwe,run_checked)
            text=(Path(config['cwd'])/'host.log').read_text(encoding='utf8',errors='replace')
            port=int(re.search(r' listening on port (\d+)',text)[1])
            deadline=time.monotonic()+8;payload=None
            while time.monotonic()<deadline:
                try:packet,sender=receiver.recvfrom(65535)
                except socket.timeout:continue
                if own_gameinfo(packet,self.name,port):
                    payload=packet;self.report.update(captured_sender=list(sender),host_port=port,packet_bytes=len(packet));break
            if payload is None:
                self.report['errors'].append('owned_host_broadcast_not_observed');self.persist()
                raise RuntimeError('Owned host GAMEINFO not observed before client startup; see local-discovery.json')
            (self.folder/'own-gameinfo.bin').write_bytes(payload)
        def replay():
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
                while not self.stop.is_set():
                    try:sender.sendto(payload,('127.0.0.1',6112));self.report['sent']+=1
                    except OSError as error:self.report['errors'].append(str(error))
                    self.persist();self.stop.wait(.5)
        self.thread=threading.Thread(target=replay,daemon=True);self.thread.start()
        return config
    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=2)
        self.report['stopped']=True;self.persist()
