"""Bounded fixed-message startup through an existing retained native owner.
Acks prove message dispatch only; caller must verify host, map and timer handshake.
"""
import json
import time
from pathlib import Path


def read_complete(path):
    try:return json.loads(path.read_text(encoding='utf8'))
    except (FileNotFoundError,json.JSONDecodeError):return None


class OwnedBootstrap:
    def __init__(self, owner, session, *, clock=time.monotonic, lan_ready=None):
        self.owner=Path(owner)
        self.session=session
        self.clock=clock
        self.lan_ready=lan_ready
        self.pid=None
        self.sent={}
        self.lan_at=None
        self.identity_at=None
        self.attempts={}
        self.issued_at={}

    def issue(self, action):
        self.attempts[action]=self.attempts.get(action,0)+1
        self.issued_at[action]=self.clock()
        nonce=self.session+'-startup-'+action
        nonce+='-'+str(self.attempts[action])
        path=self.owner/('window.'+action)
        temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(nonce,encoding='ascii')
        temp.replace(path)
        self.sent[action]=nonce

    def ack(self, action):
        result=read_complete(self.owner/('window-'+action+'-result.json'))
        if not result or result.get('id')!=self.sent.get(action):return False
        if result.get('action')!=action or result.get('pid')!=self.pid:
            raise RuntimeError('Native owner reply identity differs for '+action)
        if not result.get('ok'):
            limit=5 if action=='activate' else 3
            if self.attempts[action]<limit:
                if self.clock()-self.issued_at[action]>=1:self.issue(action)
                return False
            raise RuntimeError('Native owner rejected '+action+': '+str(result.get('error')))
        return True

    def tick(self):
        identity=read_complete(self.owner/'game-process.json')
        if not identity:return
        pid=identity.get('pid')
        if not isinstance(pid,int) or isinstance(pid,bool) or pid<=0:
            raise RuntimeError('Invalid native owner game PID')
        if self.pid is not None and self.pid!=pid:
            raise RuntimeError('Native owner game PID changed during bootstrap')
        self.pid=pid
        if self.identity_at is None:self.identity_at=self.clock()
        # Successful native startup evidence places these menu actions at
        # roughly 3/8/12 seconds. Fast polling must not collapse those phases.
        # These are minimum settling guards, not proof of menu readiness.
        if self.clock()-self.identity_at<3:return
        if 'activate' not in self.sent:self.issue('activate')
        if 'lan' not in self.sent and self.ack('activate') and self.clock()-self.issued_at['activate']>=4:
            self.issue('lan');self.lan_at=self.clock()
        if 'lan' in self.sent and 'join' not in self.sent and self.ack('lan') and self.clock()-self.lan_at>=3.5:
            if self.lan_ready is not None and not self.lan_ready(self.pid):
                if self.attempts['lan']>=3:
                    raise RuntimeError('Owned client LAN receiver not observed after bounded menu requests')
                self.issue('lan');self.lan_at=self.clock()
                return
            self.issue('join')
        if 'join' in self.sent:self.ack('join')
