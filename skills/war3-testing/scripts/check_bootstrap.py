"""Coordinator contract checks; temporary files only, no game or UI actions."""
import json
from pathlib import Path
import tempfile
from owned_bootstrap import OwnedBootstrap


def main():
    checks=[]
    def check(value,label):
        if not value:raise AssertionError(label)
        checks.append(label)
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp);clock=[0]
        b=OwnedBootstrap(folder,'test-session',clock=lambda:clock[0])
        b.tick();check(not b.sent,'Absent identity sends no message')
        identity=folder/'game-process.json'
        identity.write_text(json.dumps({'pid':123}))
        b.tick();check(not b.sent,'Fast polling cannot dispatch during initial settling')
        clock[0]=3;b.tick();check(set(b.sent)=={'activate'},'Native identity permits activation dispatch after settling')
        def ack(action,**override):
            value={'id':b.sent[action],'action':action,'pid':123,'ok':True}
            value.update(override)
            (folder/('window-'+action+'-result.json')).write_text(json.dumps(value))
        ack('activate',id='old-nonce');b.tick();check('lan' not in b.sent,'Stale reply cannot advance')
        ack('activate',pid=124)
        try:b.tick()
        except RuntimeError:checks.append('Foreign PID rejected')
        else:raise AssertionError('Foreign PID accepted')
        clock[0]=3;ack('activate',ok=False);b.tick();check(b.attempts['activate']==1,'Failed activation does not retry immediately')
        clock[0]=4;b.tick();check(b.attempts['activate']==2,'Failed activation retries with a new nonce')
        ack('activate');clock[0]=8;b.tick();check('lan' in b.sent,'Valid activation advances to LAN')
        ack('lan');clock[0]=9;b.tick();check('join' not in b.sent,'Join waits for LAN settling')
        clock[0]=12;b.tick();check('join' in b.sent,'Join issued after settling')
        for value in (13,14):
            ack('join',ok=False);clock[0]=value;b.tick()
        ack('join',ok=False);clock[0]=15
        try:b.tick()
        except RuntimeError:checks.append('Repeated native failure exhausts finite retry bound')
        else:raise AssertionError('Native rejection ignored')
        ack('join');b.tick()
        identity.write_text(json.dumps({'pid':124}))
        try:b.tick()
        except RuntimeError:checks.append('PID change rejected')
        else:raise AssertionError('Changed game PID accepted')
    result={'passed':True,'checks':checks,'scope':'Contract only; no real menu or LAN proof'}
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':main()
