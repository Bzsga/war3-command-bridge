import json
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import pytest
from workbench.ai import Provider

@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        mode='ok'
        def do_POST(self):
            request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert request['model']=='fixture-model'
            if self.mode=='auth':self.send_response(401);self.end_headers();return
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps({'choices':[{'message':{'content':'invalid JSON' if self.mode=='bad' else '连接成功'}}],'usage':{'total_tokens':5}}).encode())
        def log_message(self,*args):pass
    s=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start()
    yield s,Handler
    s.shutdown();s.server_close()

def test_provider_protocol_auth_usage(server):
    s,h=server;p=Provider({'base_url':f'http://127.0.0.1:{s.server_port}','model':'fixture-model'},'test')
    assert p.test()=='连接成功' and p.tokens==5 and p.requests==1
    h.mode='auth'
    with pytest.raises(RuntimeError,match='密钥无效'):p.test()

def test_invalid_model_output(server):
    s,h=server;h.mode='bad';p=Provider({'base_url':f'http://127.0.0.1:{s.server_port}','model':'fixture-model'},'test')
    with pytest.raises(json.JSONDecodeError):p.propose({})

def test_cancel_and_network():
    e=threading.Event();e.set()
    with pytest.raises(InterruptedError):Provider({'model':'x'},'x',e).test()
    with pytest.raises(RuntimeError,match='网络连接失败'):Provider({'base_url':'http://127.0.0.1:1','model':'x'},'x').test()
