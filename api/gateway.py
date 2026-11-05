"""Stable local gateway. Atomic routing switch; in-flight requests retain their backend."""
import argparse
import http.client
import json
import os
from pathlib import Path
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE=Path('/state/active.json')
HOP={'connection','transfer-encoding','keep-alive','proxy-authenticate','proxy-authorization','te','trailer','upgrade'}

def active():
    return json.loads(STATE.read_text())['backend']

def switch(backend):
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+',backend): raise ValueError('Invalid backend')
    temporary=STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps({'backend':backend}),encoding='utf-8')
    temporary.replace(STATE)

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def forward(self):
        connection=None
        try:
            backend=active()
            connection=http.client.HTTPConnection(backend,8000,timeout=15)
            body=self.rfile.read(int(self.headers.get('Content-Length','0')))
            headers={k:v for k,v in self.headers.items() if k.lower() not in HOP|{'host'}}
            headers['Host']='127.0.0.1:8000'
            connection.request(self.command,self.path,body=body,headers=headers)
            response=connection.getresponse();payload=response.read()
            self.send_response(response.status)
            for key,value in response.getheaders():
                if key.lower() not in HOP|{'content-length','server','date'}: self.send_header(key,value)
            self.send_header('Content-Length',str(len(payload)));self.end_headers()
            if self.command!='HEAD': self.wfile.write(payload)
        except Exception as error:
            payload=json.dumps({'error':'gateway_backend_unavailable','detail':str(error)}).encode()
            self.send_response(502);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
        finally:
            if connection: connection.close()
    do_GET=forward
    do_POST=forward
    do_HEAD=forward
    do_OPTIONS=forward

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--switch');parser.add_argument('--active',action='store_true');args=parser.parse_args()
    if args.switch: switch(args.switch)
    elif args.active: print(active())
    else:
        if not STATE.exists(): switch(os.environ['INITIAL_BACKEND'])
        ThreadingHTTPServer(('0.0.0.0',8000),Handler).serve_forever()
