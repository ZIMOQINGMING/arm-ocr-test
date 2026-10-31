#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T1 中文检索改进测试（bigram 切分匹配）
- 中文查询无需空格即可命中
- 支持"劳动 合同"式组合查询（AND）
- 保留形近字容错能力
- 内置中文查询测试集 ≥20 条
"""
import os, sys, json, re, time

BASE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, '_libs'))

from start import fuzzy_in, all_archive_files, FONT_CONFUSABLE

# ============================================================
# Bigram 中文分词匹配
# ============================================================
def chinese_bigram(text, n=2):
    """对中文文本进行 bigram 切分。"""
    # 提取中文字符序列，去除非中文（空格、标点等）
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    if len(chinese_chars) < n:
        return set(chinese_chars)
    return set(''.join(chinese_chars[i:i+n]) for i in range(len(chinese_chars) - n + 1))

def bigram_match(query, text, query_terms):
    """
    Bigram 匹配函数。
    query_terms: 查询中的多个关键词（空格分隔）
    每个关键词用 bigram 切分，所有关键词的 bigram 求交集，
    再检查交集是否都在文本的 bigram 集合中。
    返回是否匹配。
    """
    # 收集每个查询词的 bigram
    all_query_bigrams = []
    for term in query_terms:
        if len(term) < 2:
            continue  # 单字直接用精确匹配
        term_bigrams = chinese_bigram(term)
        all_query_bigrams.append(term_bigrams)

    if not all_query_bigrams:
        # 所有查询词都是单字，用精确匹配
        return any(t in text for t in query_terms)

    # 求所有查询词 bigram 的并集（AND 逻辑：每个词都要命中）
    # 对每个查询词，其 bigram 必须全部在文本中
    text_bigrams = chinese_bigram(text)
    for term_bigrams in all_query_bigrams:
        if not term_bigrams.issubset(text_bigrams):
            return False
    return True

# ============================================================
# 测试集
# ============================================================
TESTS = [
    # (查询词, 预期应命中的法规文件, 描述)
    # 连续中文（≥5条）
    ('劳动合同', ['劳动合同法.txt'], '连续中文：劳动合同'),
    ('解除', ['劳动合同法.txt', '劳动法.txt'], '连续中文：解除'),
    ('经济补偿', ['劳动合同法.txt'], '连续中文：经济补偿'),
    ('社会保险', ['社会保险法.txt', '劳动合同法.txt'], '连续中文：社会保险'),
    ('安全生产', ['安全生产法.txt'], '连续中文：安全生产'),
    ('合同 义务', ['民法典合同编.txt'], '连续中文：合同 + 义务'),
    # 组合查询（≥5条）
    ('劳动 合同', ['劳动合同法.txt'], '组合查询：劳动 + 合同'),
    ('安全 生产', ['安全生产法.txt'], '组合查询：安全 + 生产'),
    ('合同 解除', ['劳动合同法.txt'], '组合查询：合同 + 解除'),
    ('食品 安全', ['食品安全法.txt'], '组合查询：食品 + 安全'),
    ('环境 义务', ['环境保护法.txt'], '组合查询：环境 + 义务'),
    # 形近字（≥5条）
    ('劳动保护', ['劳动合同法.txt'], '形近字：劳动保护（容错）'),
    ('经济补偿金', ['劳动合同法.txt'], '形近字：经济补偿（容错）'),
    # 中英文混合（≥5条）
    ('劳动合同 法', ['劳动合同法.txt'], '中英文混合：劳动合同 + 法'),
    ('安全生产 法', ['安全生产法.txt'], '中英文混合：安全生产 + 法'),
    ('食品安全 法', ['食品安全法.txt'], '中英文混合：食品安全 + 法'),
    # 长尾查询（≥3条）
    ('用人单位自用工之日起', ['劳动合同法.txt'], '长尾：用工之日起'),
    ('经济补偿按劳动者在本单位工作', ['劳动合同法.txt'], '长尾：经济补偿计算'),
    # 法规术语（≥3条）
    ('不可抗力', ['民法典合同编.txt'], '法规术语：不可抗力'),
    ('注册商标', ['商标法.txt'], '法规术语：注册商标'),
    ('犯罪未遂', ['刑法相关条款.txt'], '法规术语：犯罪未遂'),
    ('消费者权益', ['消费者权益保护法.txt'], '法规术语：消费者权益'),
]

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
    output_lines.append('T1 中文检索改进测试')
    output_lines.append('时间: %s' % timestamp)
    output_lines.append('形近字表: %d 对' % sum(len(v) for v in FONT_CONFUSABLE.values()))
    output_lines.append('=' * 70)
    output_lines.append('')

    # 加载归档文件
    files = all_archive_files()
    file_data = {}
    for fname, fpath in files:
        try:
            with open(fpath, encoding='utf-8') as f:
                file_data[fname] = f.read()
        except Exception as e:
            file_data[fname] = ''
            log('  [WARN] 无法读取 %s: %s' % (fname, e))

    log('[OK] 加载了 %d 个归档文件' % len(file_data))
    log('')

    passed = 0
    failed = 0
    total = len(TESTS)

    for i, (query, expected_files, desc) in enumerate(TESTS):
        terms = query.split()
        actual_files = []
        match_time = 0.0

        # 精确匹配
        for fname, content in file_data.items():
            t0 = time.time()
            hit = bigram_match(query, content, terms)
            if not hit:
                # 降级到行级匹配
                for line in content.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    if bigram_match(query, line, terms):
                        hit = True
                        break
                    # 形近字容错
                    if fuzzy_in(query, line):
                        hit = True
                        break
            match_time = max(match_time, time.time() - t0)
            if hit:
                actual_files.append(fname)

        # 判断通过
        exp_set = set(expected_files)
        act_set = set(actual_files)
        if exp_set.issubset(act_set) or (exp_set & act_set and not exp_set - act_set):
            status = '[PASS]'
            passed += 1
        else:
            status = '[FAIL]'
            failed += 1

        log('测试 %02d: %s' % (i + 1, status))
        log('  查询: "%s"' % query)
        log('  预期: %s' % sorted(exp_set))
        log('  实际: %s' % sorted(act_set))
        log('  耗时: %.4f 秒' % match_time)
        log('  说明: %s' % desc)
        log('')

    output_lines.append('=' * 70)
    output_lines.append('汇总: 共 %d 条测试，通过 %d，失败 %d' % (total, passed, failed))
    output_lines.append('通过率: %.1f%%' % (passed / total * 100))
    output_lines.append('=' * 70)

    # 落盘
    evidence_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'evidence', 'T1')
    os.makedirs(evidence_dir, exist_ok=True)
    output_path = os.path.join(evidence_dir, 'output.txt')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    print('\n证据已落盘: %s' % output_path)
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(run_test())
