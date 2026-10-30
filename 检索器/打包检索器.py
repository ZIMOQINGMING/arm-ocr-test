#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包检索器：把同目录所有 .txt 打成一个「内嵌数据的单文件 HTML」。
生成后，双击 检索器.html 即可在浏览器里搜索，考试机无需 Python。
用法：python3 打包检索器.py
"""
import os, json, glob

# 完整 HTML 模板（搜索逻辑内嵌，数据用 __DATA__ 占位）
HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>资料检索器</title>
<style>
  :root { --bg:#f5f6f8; --card:#fff; --text:#1a1a1a; --sub:#666; --line:#e5e7eb;
          --accent:#1f6feb; --accent-soft:#e8f0fe; --hit:#fff3cd; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:-apple-system,"Microsoft YaHei","PingFang SC",sans-serif;
         background:var(--bg); color:var(--text); padding:24px; }
  .wrap { max-width:920px; margin:0 auto; }
  h1 { font-size:20px; margin-bottom:4px; }
  .sub { color:var(--sub); font-size:13px; margin-bottom:16px; }
  .searchbar { position:sticky; top:0; background:var(--bg); padding:12px 0; z-index:10; }
  .searchbar input { width:100%; padding:14px 18px; font-size:16px; border:1px solid var(--line);
    border-radius:10px; outline:none; }
  .searchbar input:focus { border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); }
  .stats { color:var(--sub); font-size:13px; margin:8px 0 16px; }
  .file-block { background:var(--card); border:1px solid var(--line); border-radius:10px;
    margin-bottom:14px; overflow:hidden; }
  .file-head { display:flex; justify-content:space-between; align-items:center;
    padding:12px 16px; cursor:pointer; border-bottom:1px solid var(--line); }
  .file-head:hover { background:#fafbfc; }
  .file-name { font-weight:600; font-size:14px; }
  .file-count { color:var(--sub); font-size:12px; white-space:nowrap; margin-left:12px; }
  .hits { padding:8px 16px; }
  .hit { padding:10px 0; border-bottom:1px dashed var(--line); font-size:14px; line-height:1.7; }
  .hit:last-child { border-bottom:none; }
  .hit .ln { color:#9aa0a6; font-size:12px; margin-right:8px; user-select:none; }
  .hit mark { background:var(--hit); color:inherit; padding:0 2px; border-radius:2px; }
  .empty { text-align:center; color:var(--sub); padding:60px 0; }
  .collapsed .hits { display:none; }
</style>
</head>
<body>
<div class="wrap">
  <h1>资料检索器</h1>
  <div class="sub">输入关键词检索（空格分隔多关键词，全部命中的行才显示）。数据已内置，可离线双击使用。</div>
  <div class="searchbar"><input id="q" placeholder="例如：违约责任  或  合同 解除" autofocus></div>
  <div class="stats" id="stats"></div>
  <div id="results"><div class="empty">等待输入关键词…</div></div>
</div>
<script>
window.DATA = __DATA__;
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function highlight(line,terms){var out=esc(line);for(var i=0;i<terms.length;i++){var t=terms[i];
  if(!t)continue;out=out.split(esc(t)).join('<mark>'+esc(t)+'</mark>');}return out;}
function search(){
  var q=document.getElementById('q').value.trim();
  var res=document.getElementById('results'),stats=document.getElementById('stats');
  if(!q){res.innerHTML='<div class="empty">等待输入关键词…</div>';stats.textContent='';return;}
  var terms=q.split(/\\s+/).filter(Boolean);
  var totalFiles=0,totalHits=0,html='';
  for(var i=0;i<window.DATA.length;i++){
    var f=window.DATA[i],lines=f.lines,matched=[];
    for(var j=0;j<lines.length;j++){
      var line=lines[j],ok=true;
      for(var k=0;k<terms.length;k++){if(line.indexOf(terms[k])<0){ok=false;break;}}
      if(ok)matched.push({n:j+1,line:line});
    }
    if(matched.length){
      totalFiles++;totalHits+=matched.length;
      var show=matched.slice(0,200);
      html+='<div class="file-block"><div class="file-head" onclick="this.parentNode.classList.toggle('collapsed')">'
        +'<span class="file-name">'+esc(f.name)+'</span>'
        +'<span class="file-count">命中 '+matched.length+' 处'+(matched.length>200?'（显示前200）':'')+'</span>'
        +'</div><div class="hits">';
      for(var m=0;m<show.length;m++){
        html+='<div class="hit"><span class="ln">'+show[m].n+'</span>'+highlight(show[m].line,terms)+'</div>';
      }
      html+='</div></div>';
    }
  }
  stats.textContent='共 '+totalFiles+' 个文件命中 '+totalHits+' 处';
  res.innerHTML=html||'<div class="empty">没有找到匹配的内容</div>';
}
document.getElementById('q').addEventListener('input',function(){
  clearTimeout(this._t);this._t=setTimeout(search,200);
});
</script>
</body>
</html>'''

def main():
    files = sorted(glob.glob('*.txt'))
    if not files:
        print('当前目录没有 .txt 文件')
        return
    data = []
    for f in files:
        try:
            lines = open(f, encoding='utf-8').read().split('\n')
        except Exception as e:
            print(f'读取 {f} 失败: {e}')
            continue
        data.append({'name': f, 'lines': lines})
    js = json.dumps(data, ensure_ascii=False)
    html = HTML.replace('__DATA__', js)
    out = '检索器.html'
    open(out, 'w', encoding='utf-8').write(html)
    total_chars = sum(len('\n'.join(d['lines'])) for d in data)
    print(f'打包完成：{len(data)} 个文件 → {out}')
    print(f'总字数约 {total_chars}，HTML 大小 {len(html)//1024} KB')
    print('把「检索器.html」拷到考试机，双击即可搜索（无需 Python）')

if __name__ == '__main__':
    main()
