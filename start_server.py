#!/usr/bin/env python3
# Minimal service starter for T5 test
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Clear proxy env vars to avoid interference
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    os.environ.pop(key, None)
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

import webbrowser
webbrowser.open = lambda *a, **k: None

from start import _init_index_manager, Handler
from start import ThreadingTCPServer, PORT

class ReuseServer(ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

_init_index_manager()
httpd = ReuseServer(('127.0.0.1', PORT), Handler)
print(f'ARM-TEST serving on port {PORT}')
httpd.serve_forever()
