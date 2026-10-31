#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T2 SQLite 索引与结果排序测试
- SQLite 存储元数据（文件名、大小、行数、SHA256）
- 文件级 bigram 匹配 + 相关性排序
- 分页（每页 20 条）
- 300 份文档基准库，单次检索 < 1 秒
"""
import os, sys, json, time, sqlite3, re, hashlib

BASE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, '_libs'))

from start import all_archive_files, fuzzy_in, chinese_bigram

# ============================================================
# SQLite 元数据索引 + bigram 搜索
# ============================================================
class IndexManager:
    """SQLite 元数据索引管理器 + bigram 搜索。"""

    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS archive_meta (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE,
                file_size INTEGER,
                line_count INTEGER,
                sha256 TEXT,
                indexed_at TEXT
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS line_index (
                doc_id INTEGER,
                line_num INTEGER,
                content TEXT,
                bigrams TEXT,  -- 存储该行的 bigram 集合（JSON 数组）
                FOREIGN KEY (doc_id) REFERENCES archive_meta(rowid)
            )
        ''')
        print('[OK] SQLite 索引管理器就绪')

    def _file_sha256(self, path):
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()

    def add_document(self, filename, content, file_size=0, sha256=''):
        """添加文档到索引。"""
        lines = content.split('\n')
        doc_id = None

        # 插入元数据
        cursor = self.conn.execute(
            "SELECT rowid FROM archive_meta WHERE filename=?", (filename,))
        row = cursor.fetchone()
        if row:
            doc_id = row[0]
            self.conn.execute(
                "UPDATE archive_meta SET file_size=?, line_count=?, sha256=?, indexed_at=? WHERE rowid=?",
                (file_size, len(lines), sha256, time.strftime('%Y-%m-%d %H:%M:%S'), doc_id))
        else:
            cur = self.conn.execute(
                "INSERT INTO archive_meta(filename, file_size, line_count, sha256, indexed_at) "
                "VALUES(?, ?, ?, ?, ?)",
                (filename, file_size, len(lines), sha256, time.strftime('%Y-%m-%d %H:%M:%S')))
            doc_id = cur.lastrowid

        # 清除旧行索引
        self.conn.execute("DELETE FROM line_index WHERE doc_id=?", (doc_id,))

        # 插入行索引 + bigram
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            bigrams = chinese_bigram(line)
            self.conn.execute(
                "INSERT INTO line_index(doc_id, line_num, content, bigrams) VALUES(?, ?, ?, ?)",
                (doc_id, i + 1, line, json.dumps(list(bigrams), ensure_ascii=False)))

        return doc_id

    def rebuild(self, docs):
        """重建索引（docs: [(filename, content, file_size, sha256), ...]）。"""
        self.conn.execute("DELETE FROM line_index")
        self.conn.execute("DELETE FROM archive_meta")
        self.conn.commit()

        for item in docs:
            if len(item) == 2:
                fname, content = item
                self.add_document(fname, content)
            else:
                fname, content, size, sha = item
                self.add_document(fname, content, size, sha)

        print('[OK] 重建了 %d 个文档的索引' % len(docs))

    def search(self, query, page=1, page_size=20):
        """
        Bigram 搜索 + 相关性排序 + 分页。
        query: "劳动 合同"（空格分隔多关键词）
        返回: (results, total)
        """
        terms = [t.strip() for t in query.split() if t.strip()]
        if not terms:
            return [], 0

        # 为每个查询词构建 bigram
        query_bigrams = []
        for term in terms:
            if len(term) >= 2:
                query_bigrams.append(('bigram', chinese_bigram(term)))
            else:
                query_bigrams.append(('char', term))

        # 使用 SQLite 匹配 bigrams
        conditions = []
        params = []
        for mode, value in query_bigrams:
            if mode == 'bigram':
                # BIGRAM: 查询词的所有 bigram 必须全部在文档 bigram 中
                bg_list = list(value)
                if bg_list:
                    placeholders = ','.join(['?' for _ in bg_list])
                    conditions.append(
                        "(SELECT count(DISTINCT b) FROM json_each(line_index.bigrams) WHERE json_each.value IN (%s)) = %d"
                        % (placeholders, len(bg_list)))
                    params.extend(bg_list)
            else:
                # CHAR: 单字精确匹配
                conditions.append("line_index.content LIKE ?")
                params.append('%%%s%%' % value)

        if not conditions:
            return self._search_file_based(terms, page, page_size)

        # 简化版：直接文件级搜索 + SQLite 元数据过滤
        results, total = self._search_file_based(terms, page, page_size)

        # 按 bigram 重新排序
        results = sorted(results, key=lambda x: x.get('score', 0), reverse=True)

        # 分页
        start = (page - 1) * page_size
        end = start + page_size

        return results[start:end], total

    def _search_file_based(self, terms, page=1, page_size=20):
        """文件级 bigram 搜索。"""
        # 获取所有文档
        cursor = self.conn.execute(
            "SELECT rowid, filename FROM archive_meta")
        docs = cursor.fetchall()

        results = []
        for doc_id, filename in docs:
            score = 0
            for term in terms:
                # 精确匹配
                cursor = self.conn.execute(
                    "SELECT COUNT(*) FROM line_index WHERE doc_id=? AND content LIKE ?",
                    (doc_id, '%%%s%%' % term))
                if cursor.fetchone()[0] > 0:
                    score += 10

                # Bigram 匹配
                term_bigrams = chinese_bigram(term)
                if term_bigrams:
                    cursor = self.conn.execute(
                        '''
                        SELECT COUNT(DISTINCT b)
                        FROM (SELECT json_each.value as b FROM line_index, json_each(line_index.bigrams)
                              WHERE line_index.doc_id=?
                              AND json_each.value IN (%s))
                        ''' % ','.join(['?' for _ in term_bigrams]),
                        [doc_id] + list(term_bigrams)
                    )
                    matched = cursor.fetchone()[0]
                    if matched > 0:
                        score += 5 * (matched / len(term_bigrams))

            if score > 0:
                results.append({
                    'filename': filename,
                    'score': score,
                    'doc_id': doc_id
                })

        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        total = len(results)

        # 分页
        start = (page - 1) * page_size
        return results[start:start + page_size], total

    def get_total_docs(self):
        cursor = self.conn.execute("SELECT COUNT(*) FROM archive_meta")
        return cursor.fetchone()[0]

    def close(self):
        self.conn.close()


# ============================================================
# 生成测试语料
# ============================================================
def generate_test_corpus(count=300):
    """生成测试用法规文档（300 份）。"""
    corpus = []
    law_titles = [
        '中华人民共和国劳动合同法', '中华人民共和国劳动法', '中华人民共和国社会保险法',
        '中华人民共和国安全生产法', '中华人民共和国民法典合同编', '中华人民共和国公司法',
        '中华人民共和国食品安全法', '中华人民共和国环境保护法', '中华人民共和国道路交通安全法',
        '中华人民共和国专利法', '中华人民共和国商标法', '中华人民共和国刑法',
    ]

    clause_templates = [
        ('第一条', '为了规范{topic}管理，保护{entity}合法权益，制定本法。'),
        ('第二条', '在中华人民共和国境内{topic}，适用本法。'),
        ('第三条', '{entity}应当遵守{topic}法律法规，依法{action}。'),
        ('第四条', '{entity}享有{topic}相关权利，履行{topic}相关义务。'),
        ('第五条', '国家鼓励{entity}在{topic}领域进行创新。'),
        ('第六条', '{entity}发现{topic}违法行为的，有权向有关部门举报。'),
        ('第七条', '有关部门应当及时依法处理{topic}举报，并保护举报人信息安全。'),
        ('第八条', '国家建立{topic}信用体系，将{entity}信用状况作为{topic}管理的重要参考。'),
        ('第九条', '{entity}应当建立健全{topic}管理制度，明确管理责任。'),
        ('第十条', '任何组织和个人不得违反{topic}法律法规，损害{entity}权益。'),
    ]

    topics = ['劳动', '安全', '环保', '食品', '市场', '质量', '价格', '交通', '教育', '医疗', '科技', '文化']
    entities = ['用人单位', '劳动者', '企业', '个人', '消费者', '经营者', '生产者', '运输者']
    actions = ['遵守', '管理', '监督', '服务', '支持']

    for i in range(count):
        title = law_titles[i % len(law_titles)]
        topic = topics[i % len(topics)]
        entity = entities[i % len(entities)]

        clauses = []
        for j, (num, template) in enumerate(clause_templates):
            text = template.format(topic=topic, entity=entity, action=actions[j % len(actions)])
            if i > 0:
                text += '（第%d次修订）' % (i % 5 + 1)
            clauses.append((num, text))

        fname = '法规测试_%04d.txt' % (i + 1)
        content = title + '\n' + '=' * 60 + '\n'
        for num, text in clauses:
            content += '第%s\n%s\n\n' % (num, text)
        corpus.append((fname, content))

    return corpus


# ============================================================
# 主测试
# ============================================================
def run_test():
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    output_lines = []

    def log(msg):
        output_lines.append(msg)
        print(msg)

    output_lines.append('=' * 70)
    output_lines.append('T2 SQLite 索引与结果排序基准测试')
    output_lines.append('时间: %s' % timestamp)
    output_lines.append('=' * 70)
    output_lines.append('')

    # 使用临时数据库
    db_path = os.path.join(BASE, 'tests', 'test_archive_index.db')
    if os.path.exists(db_path):
        os.remove(db_path)

    log('[INFO] 测试索引: %s' % db_path)
    log('')

    # 1. 生成测试语料
    log('[T1] 生成测试语料（300 份文档）...')
    test_corpus = generate_test_corpus(300)
    log('[OK] 生成了 %d 份测试文档' % len(test_corpus))
    log('')

    # 2. 重建索引
    log('[T2] 重建索引...')
    idx = IndexManager(db_path)
    t0 = time.time()
    idx.rebuild(test_corpus)
    rebuild_time = time.time() - t0
    log('[OK] 索引重建完成，耗时 %.3f 秒，索引 %d 个文档' % (rebuild_time, idx.get_total_docs()))
    log('')

    # 3. 基准测试
    log('[T3] 检索基准测试（300 份文档，10 次取均值）...')
    test_queries = [
        '劳动 合同',
        '安全 生产',
        '环境保护',
        '食品安全',
        '用人单位',
        '劳动者权益',
        '违法举报',
        '信用体系',
        '创新支持',
        '管理责任',
    ]

    bench_results = []
    for query in test_queries:
        times = []
        results_count = 0
        for _ in range(10):
            t0 = time.time()
            results, total = idx.search(query, page=1, page_size=20)
            elapsed = time.time() - t0
            times.append(elapsed)
            results_count = len(results)

        avg_time = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)
        status = '[OK]' if avg_time < 1.0 else '[WARN]'
        bench_results.append({
            'query': query,
            'avg_ms': avg_time * 1000,
            'max_ms': max_time * 1000,
            'min_ms': min_time * 1000,
            'total': results_count,
            'status': status,
        })
        log('  %s 查询: "%s" 平均 %.2fms (min=%.2fms, max=%.2fms) 命中 %d 条' % (
            status, query, avg_time * 1000, min_time * 1000, max_time * 1000, results_count))

    log('')

    # 4. 分页测试
    log('[T4] 分页测试...')
    query = test_queries[0]
    for page in [1, 2, 3, 4, 5]:
        results, total = idx.search(query, page=page, page_size=20)
        log('  第%d页: 返回 %d 条 (总计 %d)' % (page, len(results), total))

    log('')

    # 5. 排序验证
    log('[T5] 排序验证...')
    query = test_queries[0]
    results, total = idx.search(query, page=1, page_size=10)
    if results:
        log('  前10条结果（按相关性排序）:')
        for i, r in enumerate(results[:10]):
            log('    %d. %s (score=%.1f)' % (i + 1, r['filename'], r.get('score', 0)))
    else:
        log('  [INFO] 无结果')
    log('')

    total_docs = idx.get_total_docs()
    idx.close()

    # 汇总
    output_lines.append('=' * 70)
    output_lines.append('基准测试汇总')
    output_lines.append('=' * 70)
    output_lines.append('索引重建耗时: %.3f 秒' % rebuild_time)
    output_lines.append('索引文档数: %d' % total_docs)
    output_lines.append('')
    output_lines.append('检索性能:')
    output_lines.append('%-20s %12s %12s %12s %8s' % ('查询词', '平均(ms)', '最小(ms)', '最大(ms)', '状态'))
    output_lines.append('-' * 70)
    all_pass = True
    for r in bench_results:
        status = 'OK' if r['avg_ms'] < 1000 else 'SLOW'
        if r['avg_ms'] >= 1000:
            all_pass = False
        output_lines.append('%-20s %12.2f %12.2f %12.2f %8s' % (
            r['query'], r['avg_ms'], r['min_ms'], r['max_ms'], status))
    output_lines.append('')
    output_lines.append('结论: %s' % ('全部检索 < 1 秒 ✓' if all_pass else '部分检索 > 1 秒 ✗'))
    output_lines.append('=' * 70)

    # 落盘
    evidence_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'evidence', 'T2')
    os.makedirs(evidence_dir, exist_ok=True)
    output_path = os.path.join(evidence_dir, 'benchmark.txt')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    print('\n证据已落盘: %s' % output_path)

    # 清理测试 DB
    if os.path.exists(db_path):
        os.remove(db_path)

    return 0 if all_pass else 1

if __name__ == '__main__':
    sys.exit(run_test())
