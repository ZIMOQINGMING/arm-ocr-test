#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
资料检索器 - 启动脚本（零依赖，Python 标准库）
用法：python3 start_search.py
作用：扫描同目录所有 .txt，起本地服务，自动打开浏览器检索界面。
"""
import os, json, threading, webbrowser, socketserver
from http.server import SimpleHTTPRequestHandler
from urllib.parse import unquote

DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8765

class Handler(SimpleHTTPRequestHandler):
    # 支持中文文件名（UTF-8 解码 URL 路径）
    def translate_path(self, path):
        path = unquote(path.split('?', 1)[0])
        path = path.lstrip('/')
        return os.path.join(DIR, path)
    def log_message(self, *a):
        pass  # 关闭访问日志刷屏

def gen_index():
    files = sorted(f for f in os.listdir(DIR) if f.lower().endswith('.txt'))
    with open(os.path.join(DIR, '_files.json'), 'w', encoding='utf-8') as fp:
        json.dump(files, fp, ensure_ascii=False)
    return files

def main():
    files = gen_index()
    print('=' * 40)
    print(f'发现 {len(files)} 个 txt 文件：')
    for f in files:
        print('  -', f)
    print('=' * 40)

    os.chdir(DIR)
    httpd = socketserver.ThreadingTCPServer(('127.0.0.1', PORT), Handler)
    httpd.daemon_threads = True
    url = f'http://127.0.0.1:{PORT}/检索器.html'
    print(f'服务已启动：{url}')
    print('浏览器将自动打开，若没打开请手动访问上面的地址')
    print('按 Ctrl+C 停止服务')
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')

if __name__ == '__main__':
    main()
