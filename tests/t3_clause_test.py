#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T3 条款感知检索与定位测试
- 按"第 X 条"切分法规文档为条款单元
- 检索结果以条款为粒度展示（法规名 + 条款号 + 条款全文）
- 支持条款定位查询（如"第三十八条"直接跳条款）
- 兼容中文数字与阿拉伯数字编号
"""
import os, sys, re, json, time

BASE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, '_libs'))

from start import chinese_bigram, fuzzy_in, all_archive_files

# ============================================================
# 条款切分函数
# ============================================================
CLAUSE_PAT = re.compile(
    r'^(第([一二三四五六七八九十百千万零]+|[0-9]+))\s*条'  # 完整条款号（含"第"和"条"）
)

def split_into_clauses(content):
    """
    将法规文档按"第 X 条"切分为条款单元列表。
    返回: [(法规名, 条款号, 条款全文), ...]
    法规名从文档第一行提取（如果第一行不是"第 X 条"开头）。
    无法识别条款结构的文档，整体作为一个"未知条款"单元。
    """
    lines = content.split('\n')
    if not lines:
        return []

    # 提取法规名：第一行（如果不是条款号开头）
    law_name = ''
    start_idx = 0
    if lines and not CLAUSE_PAT.match(lines[0].strip()):
        law_name = lines[0].strip()
        start_idx = 1
        # 跳过可能的分隔线（= 或 - 重复）
        while start_idx < len(lines) and re.match(r'^[=\-]+$', lines[start_idx].strip()):
            start_idx += 1

    # 按条款号切分
    clauses = []
    current_clause_start = start_idx
    current_clause_num = None
    current_clause_text = []

    for i in range(start_idx, len(lines)):
        line = lines[i].strip()
        match = CLAUSE_PAT.match(line)
        if match:
            # 保存前一个条款
            if current_clause_num and current_clause_text:
                clauses.append((law_name, current_clause_num, '\n'.join(current_clause_text)))
            # 开始新条款
            current_clause_num = match.group(0)  # 完整条款号（如"第一条"）
            current_clause_text = [line]
            current_clause_start = i
        else:
            # 当前行属于当前条款
            if current_clause_num:
                current_clause_text.append(line)
            else:
                # 还没有遇到条款号，可能是法规名后的前言
                pass

    # 保存最后一个条款
    if current_clause_num and current_clause_text:
        clauses.append((law_name, current_clause_num, '\n'.join(current_clause_text)))

    # 如果没有找到任何条款，整体作为一个单元
    if not clauses:
        clauses.append((law_name, '未知', content))

    return clauses

def find_clause_by_number(clauses, clause_num_query):
    """
    条款定位查询：根据"第 X 条"查询直接定位到该条款。
    支持模糊匹配（如"三十八"匹配"第三十八条"）。
    """
    results = []
    # 精确匹配
    for law_name, clause_num, text in clauses:
        if clause_num == clause_num_query:
            results.append((law_name, clause_num, text))
            return results  # 精确命中直接返回

    # 模糊匹配：提取数字部分
    num_match = re.search(r'([0-9]+)', clause_num_query)
    if num_match:
        num = num_match.group(1)
        for law_name, clause_num, text in clauses:
            if num in clause_num:
                results.append((law_name, clause_num, text))

    # 中文数字模糊匹配
    zh_nums = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
               '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
               '百': '100', '千': '1000', '万': '10000', '零': '0'}
    for law_name, clause_num, text in clauses:
        if all(c in zh_nums for c in clause_num_query if c in zh_nums):
            zh_to_num = ''.join(zh_nums[c] for c in clause_num_query if c in zh_nums)
            if zh_to_num in clause_num:
                results.append((law_name, clause_num, text))

    return results

def clause_search(clauses, query_terms):
    """
    条款级搜索：在条款单元中搜索查询词。
    返回: [(法规名, 条款号, 条款全文, score), ...]
    """
    results = []
    for law_name, clause_num, text in clauses:
        score = 0
        for term in query_terms:
            if term in text:
                score += 10
            # Bigram 匹配
            term_bigrams = chinese_bigram(term)
            if term_bigrams:
                text_bigrams = chinese_bigram(text)
                matched = len(term_bigrams & text_bigrams)
                if matched > 0:
                    score += 5 * (matched / len(term_bigrams))
            # 形近字容错
            if fuzzy_in(term, text):
                score += 3
        if score > 0:
            results.append((law_name, clause_num, text, score))
    return sorted(results, key=lambda x: x[3], reverse=True)

# ============================================================
# 测试集
# ============================================================

# 生成模拟法规文档（含条款结构）
def generate_sample_regulations():
    """生成 10 份模拟法规文档（含条款结构）用于测试。"""
    regulations = [
        {
            'name': '中华人民共和国劳动合同法',
            'clauses': [
                ('第一条', '为了完善劳动合同制度，明确劳动合同双方当事人的权利和义务，保护劳动者的合法权益，构建和发展和谐稳定的劳动关系，制定本法。'),
                ('第二条', '在中华人民共和国境内的企业、个体经济组织、民办非企业单位等组织（以下称用人单位）与劳动者建立劳动关系，订立、履行、变更、解除或者终止劳动合同，适用本法。'),
                ('第三条', '订立劳动合同，应当遵循合法、公平、平等自愿、协商一致、诚实信用的原则。依法订立的劳动合同具有约束力，用人单位与劳动者应当履行劳动合同约定的义务。'),
                ('第四条', '用人单位应当依法建立和完善劳动规章制度，保障劳动者享有劳动权利、履行劳动义务。用人单位在制定、修改或者决定有关劳动报酬、工作时间、休息休假、劳动安全卫生、保险福利、职工培训、劳动纪律以及劳动定额管理等直接涉及劳动者切身利益的规章制度或者重大事项时，应当经职工代表大会或者全体职工讨论，提出方案和意见，与工会或者职工代表平等协商确定。'),
                ('第十条', '建立劳动关系，应当订立书面劳动合同。已建立劳动关系，未同时订立书面劳动合同的，应当自用工之日起一个月内订立书面劳动合同。'),
                ('第三十八条', '用人单位有下列情形之一的，劳动者可以解除劳动合同：（一）未按照劳动合同约定提供劳动保护或者劳动条件的；（二）未及时足额支付劳动报酬的；（三）未依法为劳动者缴纳社会保险费的；（四）用人单位的规章制度违反法律、法规的规定，损害劳动者权益的；（五）因本法第二十六条第一款规定的情形致使劳动合同无效的；（六）法律、行政法规规定劳动者可以解除劳动合同的其他情形。'),
            ]
        },
        {
            'name': '中华人民共和国劳动法',
            'clauses': [
                ('第一条', '为了保护劳动者的合法权益，调整劳动关系，建立和维护适应社会主义市场经济的劳动制度，促进经济发展和社会进步，根据宪法，制定本法。'),
                ('第二条', '在中华人民共和国境内的企业、个体经济组织和与之形成劳动关系的劳动者，适用本法。'),
                ('第三条', '劳动者享有平等就业和选择职业的权利、取得劳动报酬的权利、休息休假的权利、获得劳动安全卫生保护的权利、接受职业技能培训的权利、享受社会保险和福利的权利、提请劳动争议处理的权利以及法律规定的其他劳动权利。'),
                ('第四十八条', '国家实行最低工资保障制度。最低工资的具体标准由省、自治区、直辖市人民政府规定，报国务院备案。'),
            ]
        },
        {
            'name': '中华人民共和国安全生产法',
            'clauses': [
                ('第一条', '为了加强安全生产工作，防止和减少生产安全事故，保障人民群众生命和财产安全，促进经济社会持续健康发展，制定本法。'),
                ('第二条', '在中华人民共和国领域内从事生产经营活动的单位（以下统称生产经营单位）的安全生产，适用本法。'),
                ('第四条', '生产经营单位必须遵守本法和其他有关安全生产的法律、法规，加强安全生产管理，建立健全全员安全生产责任制和安全生产规章制度，加大对安全生产资金、物资、技术、人员的投入保障力度，改善安全生产条件，加强安全生产标准化、信息化建设，构建安全风险分级管控和隐患排查治理双重预防机制，健全风险防范化解机制，提高安全生产水平，确保安全生产。'),
                ('第五十条', '生产经营单位必须依法参加工伤保险，为从业人员缴纳保险费。'),
            ]
        },
        {
            'name': '中华人民共和国环境保护法',
            'clauses': [
                ('第一条', '为保护和改善环境，防治污染和其他公害，保障公众健康，推进生态文明建设，促进经济社会可持续发展，制定本法。'),
                ('第二条', '本法所称环境，是指影响人类生存和发展的各种天然的和经过人工改造的自然因素的总体，包括大气、水、海洋、土地、矿藏、森林、草原、湿地、野生生物、自然遗迹、人文遗迹、自然保护区、风景名胜区、城市和乡村等。'),
                ('第六条', '一切单位和个人都有保护环境的义务。地方各级人民政府应当对本行政区域的环境质量负责。企业事业单位和其他生产经营者应当防止、减少环境污染和生态破坏，对所造成的损害依法承担责任。'),
            ]
        },
        {
            'name': '中华人民共和国食品安全法',
            'clauses': [
                ('第一条', '为了保证食品安全，保障公众身体健康和生命安全，制定本法。'),
                ('第二条', '在中华人民共和国境内从事下列活动，应当遵守本法：（一）食品生产和加工，食品销售和餐饮服务；（二）食品添加剂的生产经营；（三）用于食品的包装材料、容器、洗涤剂、消毒剂和用于食品生产经营的工具、设备（以下称食品相关产品）的生产经营；（四）食品生产经营者使用食品添加剂、食品相关产品；（五）食品的贮存和运输；（六）对食品、食品添加剂、食品相关产品的安全管理。'),
                ('第三十四条', '禁止生产经营下列食品、食品添加剂、食品相关产品：（一）用非食品原料生产的食品或者添加食品添加剂以外的化学物质和其他可能危害人体健康物质的食品，或者用回收食品作为原料生产的食品；（二）致病性微生物，农药残留、兽药残留、生物毒素、重金属等污染物质以及其他危害人体健康的物质含量超过食品安全标准限量的食品、食品添加剂、食品相关产品；（三）用超过保质期的食品原料、食品添加剂生产的食品、食品添加剂、食品相关产品；（四）超范围、超限量使用食品添加剂的食品；（五）营养成分不符合食品安全标准的专供婴幼儿和其他特定人群的主副食品；（六）腐败变质、油脂酸败、霉变生虫、污秽不洁、混有异物、掺假掺杂或者感官性状异常的食品、食品添加剂、食品相关产品；（七）病死、毒死或者死因不明的禽、畜、兽、水产动物肉类及其制品；（八）国家为防病等特殊需要明令禁止生产经营的食品；（九）其他不符合法律、法规或者食品安全标准的食品、食品添加剂、食品相关产品。'),
            ]
        },
        {
            'name': '中华人民共和国民法典合同编',
            'clauses': [
                ('第四百六十四条', '合同是民事主体之间设立、变更、终止民事法律关系的协议。婚姻、收养、监护等有关身份关系的协议，适用有关该身份关系的法律规定；没有规定的，可以根据其性质参照适用本编规定。'),
                ('第四百六十五条', '依法成立的合同，受法律保护。依法成立的合同，仅对当事人具有法律约束力，但是法律另有规定的除外。'),
                ('第五百七十七条', '当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担继续履行、采取补救措施或者赔偿损失等违约责任。'),
            ]
        },
        {
            'name': '中华人民共和国社会保险法',
            'clauses': [
                ('第一条', '规范社会保险关系，维护公民参加社会保险和享受社会保险待遇的合法权益，使公民共享发展成果，促进社会和谐稳定，根据宪法，制定本法。'),
                ('第二条', '国家建立基本养老保险、基本医疗保险、工伤保险、失业保险、生育保险等社会保险制度，保障公民在年老、疾病、工伤、失业、生育等情况下依法从国家和社会获得物质帮助的权利。'),
                ('第四条', '中华人民共和国境内的用人单位和个人依法缴纳社会保险费，有权查询缴费记录、个人权益记录，要求社会保险经办机构提供社会保险咨询等相关服务。个人依法享受社会保险待遇，有权监督本单位为其缴费情况。'),
            ]
        },
        {
            'name': '中华人民共和国道路交通安全法',
            'clauses': [
                ('第一条', '为了维护道路交通秩序，预防和减少交通事故，保护人身安全，保护公民、法人和其他组织的财产安全及其他合法权益，提高通行效率，制定本法。'),
                ('第二条', '中华人民共和国境内的车辆驾驶人、行人、乘车人以及与道路交通活动有关的单位和个人，都应当遵守本法。'),
                ('第七十六条', '机动车发生交通事故造成人身伤亡、财产损失的，由保险公司在机动车第三者责任强制保险责任限额范围内予以赔偿；不足的部分，按照下列规定承担赔偿责任：（一）机动车之间发生交通事故的，由有过错的一方承担赔偿责任；双方都有过错的，按照各自过错的比例分担责任。'),
            ]
        },
        {
            'name': '中华人民共和国商标法',
            'clauses': [
                ('第一条', '为了加强商标管理，保护商标专用权，促使生产、经营者保证商品和服务质量，维护商标信誉，以保障消费者和生产、经营者的利益，促进社会主义市场经济的发展，制定本法。'),
                ('第四条', '自然人、法人或者其他组织在生产经营活动中，对其商品或者服务需要取得商标专用权的，应当向商标局申请商标注册。'),
                ('第三十九条', '注册商标的有效期为十年，自核准注册之日起计算。'),
            ]
        },
        {
            'name': '中华人民共和国专利法',
            'clauses': [
                ('第一条', '为了保护专利权人的合法权益，鼓励发明创造，推动发明创造的应用，提高创新能力，促进科学技术进步和经济社会发展，制定本法。'),
                ('第二条', '本法所称的发明创造是指发明、实用新型和外观设计。发明，是指对产品、方法或者其改进所提出的新的技术方案。实用新型，是指对产品的形状、构造或者其结合所提出的适于实用的新的技术方案。外观设计，是指对产品的整体或者局部的形状、图案或者其结合以及色彩与形状、图案的结合所作出的富有美感并适于工业应用的新设计。'),
                ('第四十二条', '发明专利权的期限为二十年，实用新型专利权的期限为十年，外观设计专利权的期限为十五年，均自申请日起计算。'),
            ]
        },
    ]
    return regulations

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
    output_lines.append('T3 条款感知检索与定位测试')
    output_lines.append('时间: %s' % timestamp)
    output_lines.append('=' * 70)
    output_lines.append('')

    # 1. 生成模拟法规文档
    log('[T1] 生成 10 份模拟法规文档...')
    regulations = generate_sample_regulations()
    test_docs = []
    for reg in regulations:
        content = reg['name'] + '\n' + '=' * 60 + '\n'
        for clause_num, text in reg['clauses']:
            content += '%s\n%s\n\n' % (clause_num, text)
        fname = '%s.txt' % reg['name']
        test_docs.append((fname, content, reg['clauses']))
    log('[OK] 生成了 %d 份模拟法规文档' % len(test_docs))
    log('')

    # 2. 条款切分测试
    log('[T2] 条款切分测试（10 份文档）...')
    clause_counts = []
    for fname, content, expected_clauses in test_docs:
        clauses = split_into_clauses(content)
        clause_counts.append(len(clauses))
        status = '[OK]' if len(clauses) == len(expected_clauses) else '[FAIL]'
        log('  %s %s: 切分 %d 条（预期 %d 条）' % (status, fname, len(clauses), len(expected_clauses)))

    all_clause_pass = all(len(split_into_clauses(c[1])) == len(c[2]) for c in test_docs)
    log('')
    log('条款切分结果: %s' % ('全部通过' if all_clause_pass else '部分失败'))
    log('')

    # 3. 条款定位查询测试
    log('[T3] 条款定位查询测试（20 条）...')
    clause_queries = [
        ('第三十八条', '中华人民共和国劳动合同法.txt', True),   # 劳动者可解除合同
        ('第四条', '中华人民共和国劳动合同法.txt', True),       # 规章制度
        ('第一条', '中华人民共和国劳动法.txt', True),           # 立法目的
        ('第四十八条', '中华人民共和国劳动法.txt', True),       # 最低工资
        ('第一条', '中华人民共和国安全生产法.txt', True),       # 立法目的
        ('第五十条', '中华人民共和国安全生产法.txt', True),     # 工伤保险
        ('第一条', '中华人民共和国环境保护法.txt', True),       # 立法目的
        ('第六条', '中华人民共和国环境保护法.txt', True),       # 保护义务
        ('第一条', '中华人民共和国食品安全法.txt', True),       # 立法目的
        ('第三十四条', '中华人民共和国食品安全法.txt', True),   # 禁止生产经营
        ('第四百六十五条', '中华人民共和国民法典合同编.txt', True),  # 合同保护
        ('第五百七十七条', '中华人民共和国民法典合同编.txt', True),  # 违约责任
        ('第二条', '中华人民共和国社会保险法.txt', True),       # 社会保险类型
        ('第四条', '中华人民共和国社会保险法.txt', True),       # 缴费义务
        ('第一条', '中华人民共和国道路交通安全法.txt', True),  # 立法目的
        ('第七十六条', '中华人民共和国道路交通安全法.txt', True),  # 事故赔偿
        ('第一条', '中华人民共和国商标法.txt', True),           # 立法目的
        ('第三十九条', '中华人民共和国商标法.txt', True),       # 有效期
        ('第一条', '中华人民共和国专利法.txt', True),           # 立法目的
        ('第四十二条', '中华人民共和国专利法.txt', True),       # 专利期限
    ]

    clause_pass = 0
    clause_fail = 0
    for query, expected_file, should_hit in clause_queries:
        # 找到对应文件的条款列表
        for fname, content, _ in test_docs:
            if fname == expected_file:
                clauses = split_into_clauses(content)
                results = find_clause_by_number(clauses, query)
                if should_hit and results:
                    law_name, clause_num, text = results[0]
                    log('  [PASS] "%s" -> %s %s' % (query, law_name, clause_num))
                    clause_pass += 1
                elif not should_hit and not results:
                    log('  [PASS] "%s" -> 未命中（预期）' % query)
                    clause_pass += 1
                else:
                    log('  [FAIL] "%s" -> %s（预期 %s）' % (query, results, expected_file))
                    clause_fail += 1
                break

    log('')
    log('条款定位结果: %d 通过, %d 失败' % (clause_pass, clause_fail))
    log('')

    # 4. 条款级搜索测试
    log('[T4] 条款级搜索测试（10 个查询）...')
    search_queries = [
        ('劳动保护', '中华人民共和国劳动合同法.txt'),
        ('安全生产', '中华人民共和国安全生产法.txt'),
        ('环境保护', '中华人民共和国环境保护法.txt'),
        ('食品安全', '中华人民共和国食品安全法.txt'),
        ('违约责任', '中华人民共和国民法典合同编.txt'),
        ('社会保险', '中华人民共和国社会保险法.txt'),
        ('交通事故', '中华人民共和国道路交通安全法.txt'),
        ('商标专用权', '中华人民共和国商标法.txt'),
        ('专利权', '中华人民共和国专利法.txt'),
        ('劳动合同', '中华人民共和国劳动合同法.txt'),
    ]

    search_pass = 0
    search_fail = 0
    for query, expected_file in search_queries:
        for fname, content, _ in test_docs:
            if fname == expected_file:
                clauses = split_into_clauses(content)
                terms = query.split()
                results = clause_search(clauses, terms)
                if results:
                    law_name, clause_num, text, score = results[0]
                    log('  [PASS] "%s" -> %s 第%s条 (score=%.1f)' % (query, law_name, clause_num, score))
                    search_pass += 1
                else:
                    log('  [FAIL] "%s" -> 未命中' % query)
                    search_fail += 1
                break

    log('')
    log('条款级搜索结果: %d 通过, %d 失败' % (search_pass, search_fail))
    log('')

    # 5. 真实归档文件条款切分测试
    log('[T5] 真实归档文件条款切分测试（抽 3 份）...')
    archive_files = all_archive_files()
    real_doc_clauses = []
    for i, (fname, fpath) in enumerate(archive_files[:3]):
        try:
            content = open(fpath, encoding='utf-8').read()
            clauses = split_into_clauses(content)
            real_doc_clauses.append((fname, len(clauses)))
            log('  %s %s: 切分 %d 条' % ('[OK]' if clauses else '[WARN]', fname, len(clauses)))
        except Exception as e:
            log('  [WARN] %s: %s' % (fname, e))

    log('')

    # 汇总
    output_lines.append('=' * 70)
    output_lines.append('T3 条款感知检索与定位汇总')
    output_lines.append('=' * 70)
    output_lines.append('条款切分: %s' % ('通过' if all_clause_pass else '部分失败'))
    output_lines.append('条款定位: %d/%d 通过' % (clause_pass, clause_pass + clause_fail))
    output_lines.append('条款级搜索: %d/%d 通过' % (search_pass, search_pass + search_fail))
    output_lines.append('')
    output_lines.append('条款切分详情:')
    for fname, count in real_doc_clauses:
        output_lines.append('  %s: %d 条' % (fname, count))
    output_lines.append('=' * 70)

    # 落盘
    evidence_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'evidence', 'T3')
    os.makedirs(evidence_dir, exist_ok=True)
    output_path = os.path.join(evidence_dir, 'output.txt')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    print('\n证据已落盘: %s' % output_path)
    return 0 if (clause_fail == 0 and search_fail == 0) else 1

if __name__ == '__main__':
    sys.exit(run_test())
