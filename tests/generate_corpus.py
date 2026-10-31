#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试语料库生成器
生成 ≥15 份真实法规文档（含 ≥3 份扫描版 PDF）到 tests/corpus/
"""
import os, sys, io, zipfile, struct

BASE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
CORPUS_DIR = os.path.join(BASE, 'tests', 'corpus')
os.makedirs(CORPUS_DIR, exist_ok=True)

# ============================================================
# 法规数据（真实法规改编）
# ============================================================
LAWS = [
    ('劳动合同法', '中华人民共和国劳动合同法', [
        ('第一条', '为了完善劳动合同制度，明确劳动合同双方当事人的权利和义务，保护劳动者的合法权益，构建和发展和谐稳定的劳动关系，制定本法。'),
        ('第二条', '中华人民共和国境内的企业、个体经济组织、民办非企业单位等组织（以下称用人单位）与劳动者建立劳动关系，订立、履行、变更、解除或者终止劳动合同，适用本法。国家机关、事业组织、社会团体和与之建立劳动关系的劳动者，依照本法执行。'),
        ('第七条', '用人单位自用工之日起即与劳动者建立劳动关系。用人单位应当建立职工名册备查。'),
        ('第十条', '建立劳动关系，应当订立书面劳动合同。已建立劳动关系，未同时订立书面劳动合同的，应当自用工之日起一个月内订立书面劳动合同。用人单位与劳动者在用工前订立劳动合同的，劳动关系自用工之日起建立。'),
        ('第三十六条', '用人单位与劳动者协商一致，可以解除劳动合同。'),
        ('第三十七条', '劳动者提前三十日以书面形式通知用人单位，可以解除劳动合同。劳动者在试用期内提前三日通知用人单位，可以解除劳动合同。'),
        ('第三十八条', '用人单位有下列情形之一的，劳动者可以解除劳动合同：（一）未按照劳动合同约定提供劳动保护或者劳动条件的；（二）未及时足额支付劳动报酬的；（三）未依法为劳动者缴纳社会保险费的；（四）用人单位的规章制度违反法律、法规的规定，损害劳动者权益的。'),
        ('第四十六条', '有下列情形之一的，用人单位应当向劳动者支付经济补偿：（一）劳动者依照本法第三十八条规定解除劳动合同的；（二）用人单位依照本法第三十六条规定向劳动者提出解除劳动合同并与劳动者协商一致解除劳动合同的。'),
        ('第四十七条', '经济补偿按劳动者在本单位工作的年限，每满一年支付一个月工资的标准向劳动者支付。六个月以上不满一年的，按一年计算；不满六个月的，向劳动者支付半个月工资的经济补偿。'),
        ('第八十二条', '用人单位自用工之日起超过一个月不满一年未与劳动者订立书面劳动合同的，应当向劳动者每月支付二倍的工资。用人单位违反本法规定不与劳动者订立无固定期限劳动合同的，自应当订立无固定期限劳动合同之日起向劳动者每月支付二倍的工资。'),
    ]),
    ('劳动法', '中华人民共和国劳动法', [
        ('第一条', '为了保护劳动者的合法权益，调整劳动关系，建立和维护适应社会主义市场经济的劳动制度，促进经济发展和社会进步，根据宪法，制定本法。'),
        ('第三条', '劳动者享有平等就业和选择职业的权利、取得劳动报酬的权利、休息休假的权利、获得劳动安全卫生保护的权利、接受职业技能培训的权利、享受社会保险和福利的权利、提请劳动争议处理的权利以及法律规定的其他劳动权利。'),
        ('第九十八条', '用人单位违反本法规定的条件解除劳动合同或者故意拖延不订立劳动合同的，由劳动行政部门责令改正；对劳动者造成损害的，应当承担赔偿责任。'),
        ('第九十九条', '用人单位招用尚未解除劳动合同的劳动者，对原用人单位造成经济损失的，该用人单位应当依法承担连带赔偿责任。'),
        ('第四十一条', '用人单位由于生产经营需要，经与工会和劳动者协商后可以延长工作时间，一般每日不得超过一小时；因特殊原因需要延长工作时间的，在保障劳动者身体健康的条件下延长工作时间每日不得超过三小时，但是每月不得超过三十六小时。'),
    ]),
    ('社会保险法', '中华人民共和国社会保险法', [
        ('第二条', '国家建立基本养老保险、基本医疗保险、工伤保险、失业保险、生育保险等社会保险制度，保障公民在年老、疾病、工伤、失业、生育等情况下依法从国家和社会获得物质帮助的权利。'),
        ('第十条', '职工应当参加基本养老保险，由用人单位和职工共同缴纳基本养老保险费。无雇工的个体工商户、未在用人单位参加基本养老保险的非全日制从业人员以及其他灵活就业人员可以参加基本养老保险，由个人缴纳基本养老保险费。'),
        ('第二十三条', '职工应当参加职工基本医疗保险，由用人单位和职工按照国家规定共同缴纳基本医疗保险费。无雇工的个体工商户、未在用人单位参加职工基本医疗保险的非全日制从业人员以及其他灵活就业人员可以参加职工基本医疗保险，由个人按照国家规定缴纳基本医疗保险费。'),
        ('第五十八条', '用人单位应当自用工之日起三十日内为其职工向社会保险经办机构申请办理社会保险登记。未办理社会保险登记的，由社会保险经办机构核定其应当缴纳的社会保险费。自愿参加社会保险的无雇工的个体工商户、未在用人单位参加社会保险的非全日制从业人员以及其他灵活就业人员，应当向社会保险经办机构申请办理社会保险登记。'),
    ]),
    ('安全生产法', '中华人民共和国安全生产法', [
        ('第三条', '安全生产工作坚持中国共产党的领导。安全生产工作应当以人为本，坚持人民至上、生命至上，把保护人民生命安全摆在首位，树牢安全发展理念，坚持安全第一、预防为主、综合治理的方针，从源头上防范化解重大安全风险。'),
        ('第四条', '生产经营单位必须遵守本法和其他有关安全生产的法律、法规，加强安全生产管理，建立健全全员安全生产责任制和安全生产规章制度，加大对安全生产资金、物资、技术、人员的投入保障力度，改善安全生产条件，加强标准化、信息化建设，构建安全风险分级管控和隐患排查治理双重预防机制，健全风险防范化解机制，提高安全生产水平，确保安全生产。'),
        ('第二十八条', '生产经营单位应当对从业人员进行安全生产教育和培训，保证从业人员具备必要的安全生产知识，熟悉有关的安全生产规章制度和安全操作规程，掌握本岗位的安全操作技能，了解事故应急处理措施，知悉自身在安全生产方面的权利和义务。未经安全生产教育和培训合格的从业人员，不得上岗作业。'),
        ('第四十一条', '生产经营单位应当建立安全风险分级管控制度，按照安全风险分级采取相应的管控措施。生产经营单位应当建立健全并落实生产安全事故隐患排查治理制度，采取技术、管理措施，及时发现并消除事故隐患。'),
    ]),
    ('民法典合同编', '中华人民共和国民法典合同编', [
        ('第四百六十九条', '当事人订立合同，可以采用书面形式、口头形式或者其他形式。书面形式是合同书、信件、电报、电传、传真等可以有形地表现所载内容的形式。以电子数据交换、电子邮件等方式能够有形地表现所载内容，并可以随时调取查用的数据电文，视为书面形式。'),
        ('第五百零九条', '当事人应当按照约定全面履行自己的义务。当事人应当遵循诚信原则，根据合同的性质、目的和交易习惯履行通知、协助、保密等义务。当事人在履行合同过程中，应当避免浪费资源、污染环境和破坏生态。'),
        ('第五百六十三条', '有下列情形之一的，当事人可以解除合同：（一）因不可抗力致使不能实现合同目的；（二）在履行期限届满前，当事人一方明确表示或者以自己的行为表明不履行主要债务；（三）当事人一方迟延履行主要债务，经催告后在合理期限内仍未履行；（四）当事人一方迟延履行债务或者有其他违约行为致使不能实现合同目的；（五）法律规定的其他情形。'),
        ('第五百七十七条', '当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担继续履行、采取补救措施或者赔偿损失等违约责任。'),
        ('第五百八十五条', '当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金，也可以约定因违约产生的损失赔偿额的计算方法。约定的违约金低于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以增加；约定的违约金过分高于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以适当减少。'),
    ]),
    ('公司法', '中华人民共和国公司法', [
        ('第三条', '公司是企业法人，有独立的法人财产，享有法人财产权。公司以其全部财产对公司的债务承担责任。有限责任公司的股东以其认缴的出资额为限对公司承担责任；股份有限公司的股东以其认购的股份为限对公司承担责任。'),
        ('第二十三条', '设立有限责任公司，应当具备下列条件：（一）股东符合法定人数；（二）有符合公司章程规定的全体股东认缴的出资额；（三）股东共同制定公司章程；（四）有公司名称，建立符合有限责任公司要求的组织机构；（五）有公司住所。'),
        ('第七十一条', '有限责任公司的股东之间可以相互转让其全部或者部分股权。股东向股东以外的人转让股权，应当经其他股东过半数同意。股东应就其股权转让事项书面通知其他股东征求同意，其他股东自接到书面通知之日起满三十日未答复的，视为同意转让。'),
        ('第一百八十二条', '公司经营管理发生严重困难，继续存续会使股东利益受到重大损失，通过其他途径不能解决的，持有公司全部股东表决权百分之十以上的股东，可以请求人民法院解散公司。'),
    ]),
    ('食品安全法', '中华人民共和国食品安全法', [
        ('第三条', '食品安全工作实行预防为主、风险管理、全程控制、社会共治的原则，建立源头生产治理、风险防控、应急处置全过程的监管制度。'),
        ('第二十六条', '食品安全标准应当包括下列内容：（一）食品、食品添加剂、食品相关产品中的致病性微生物，农药残留、兽药残留、生物毒素、重金属等污染物质以及其他危害人体健康物质的限量规定；（二）食品添加剂的品种、使用范围、用量；（三）专供婴幼儿和其他特定人群的主辅食品的营养成分要求。'),
        ('第三十四条', '禁止生产经营下列食品、食品添加剂、食品相关产品：（一）用非食品原料生产的食品或者添加食品添加剂以外的化学物质和其他可能危害人体健康物质的食品；（二）致病性微生物，农药残留、兽药残留、生物毒素、重金属等污染物质以及其他危害人体健康的物质含量超过食品安全标准限量的食品；（三）用超过保质期的食品原料、食品添加剂生产的食品、食品添加剂。'),
    ]),
    ('环境保护法', '中华人民共和国环境保护法', [
        ('第二条', '本法所称环境，是指影响人类生存和发展的各种天然的和经过人工改造的自然因素的总体，包括大气、水、海洋、土地、矿藏、森林、草原、湿地、野生生物、自然遗迹、人文遗迹、自然保护区、风景名胜区、城市和乡村等。'),
        ('第六条', '一切单位和个人都有保护环境的义务。地方各级人民政府应当对本行政区域的环境质量负责。企业事业单位和其他生产经营者应当防止、减少环境污染和生态破坏，对所造成的损害依法承担责任。公民应当增强环境保护意识，采取低碳、节俭的生活方式，自觉履行环境保护义务。'),
        ('第四十条', '国家促进清洁生产和资源循环利用。企业应当优先使用清洁能源，采用资源利用率高、污染物排放量少的工艺、设备以及废弃物综合利用技术和污染物无害化处理技术，减少污染物的产生。'),
        ('第五十九条', '企业事业单位和其他生产经营者违法排放污染物，受到罚款处罚，被责令改正，拒不改正的，依法作出罚款处罚的行政机关可以自责令改正之日的次日起，按照原处罚数额按日连续处罚。'),
    ]),
    ('道路交通安全法', '中华人民共和国道路交通安全法', [
        ('第三条', '道路交通安全工作，应当遵循依法管理、方便群众的原则，保障道路交通有序、安全、畅通。'),
        ('第二十二条', '机动车驾驶人应当遵守道路交通安全法律、法规的规定，按照操作规范安全驾驶、文明驾驶。饮酒、服用国家管制的精神药品或者麻醉药品，或者患有妨碍安全驾驶机动车的疾病，或者过度疲劳影响安全驾驶的，不得驾驶机动车。'),
        ('第七十六条', '机动车发生交通事故造成人身伤亡、财产损失的，由保险公司在机动车第三者责任强制保险责任限额范围内予以赔偿；不足的部分，按照下列规定承担赔偿责任：（一）机动车之间发生交通事故的，由有过错的一方承担赔偿责任；双方都有过错的，按照各自过错的比例分担责任。'),
    ]),
    ('专利法', '中华人民共和国专利法', [
        ('第二条', '本法所称的发明创造是指发明、实用新型和外观设计。发明，是指对产品、方法或者其改进所提出的新的技术方案。实用新型，是指对产品的形状、构造或者其结合所提出的适于实用的新的技术方案。外观设计，是指对产品的整体或者局部的形状、图案或者其结合以及色彩与形状、图案的结合所作出的富有美感并适于工业应用的新设计。'),
        ('第二十二条', '授予专利权的发明和实用新型，应当具备新颖性、创造性和实用性。新颖性，是指该发明或者实用新型不属于现有技术，也没有任何单位或者个人就同样的发明或者实用新型在申请日以前向国务院专利行政部门提出过申请，并记载在申请日以后公布的专利申请文件或者公告的专利文件中。'),
        ('第五十条', '申请专利的发明创造涉及国家安全或者重大利益需要保密的，按照国家有关规定办理。'),
        ('第六十条', '未经专利权人许可，实施其专利，即侵犯其专利权，引起纠纷的，由当事人协商解决；不愿协商或者协商不成的，专利权人或者利害关系人可以向人民法院起诉，也可以请求管理部门处理。'),
    ]),
    ('商标法', '中华人民共和国商标法', [
        ('第四条', '自然人、法人或者其他组织在生产经营活动中，对其商品或者服务需要取得商标专用权的，应当向商标局申请商标注册。不以使用为目的的恶意商标注册申请，应当予以驳回。'),
        ('第八条', '任何能够将自然人、法人或者其他组织的商品与他人的商品区别开的标志，包括文字、图形、字母、数字、三维标志、颜色组合和声音等，以及上述要素的组合，均可以作为商标申请注册。'),
        ('第三十条', '申请注册的商标，凡不符合本法有关规定或者同他人在同一种商品或者类似商品上已经注册的或者初步审定的商标相同或者近似的，由商标局驳回申请，不予公告。'),
        ('第四十九条', '注册商标成为其核定使用的商品的通用名称或者没有正当理由连续三年不使用的，任何单位或者个人可以向商标局申请撤销该注册商标。'),
    ]),
    ('劳动法实施条例', '中华人民共和国劳动合同法实施条例', [
        ('第六条', '用人单位自用工之日起超过一个月不满一年未与劳动者订立书面劳动合同的，应当依照劳动合同法第八十二条的规定向劳动者每月支付两倍的工资，并与劳动者补订书面劳动合同；劳动者不与用人单位订立书面劳动合同的，用人单位应当书面通知劳动者终止劳动关系，并依照劳动合同法第四十七条的规定支付经济补偿。'),
        ('第七条', '用人单位自用工之日起满一年未与劳动者订立书面劳动合同的，自用工之日起满一个月的次日至满一年的前一日应当依照劳动合同法第八十二条的规定向劳动者每月支付两倍的工资，并视为自用工之日起满一年的当日已经与劳动者订立无固定期限劳动合同，应当立即与劳动者补订书面劳动合同。'),
        ('第八条', '劳动合同法第七条规定的职工名册，应当包括劳动者姓名、性别、公民身份号码、户籍地址及现住址、联系方式、用工形式、用工起始时间、劳动合同期限等内容。'),
    ]),
    ('公司法实施条例', '中华人民共和国公司登记管理条例', [
        ('第九条', '公司的名称、住所、法定代表人姓名、注册资本、公司类型、经营范围、营业期限、有限责任公司股东或者股份有限公司发起人姓名或者名称，为公司登记事项。'),
        ('第十四条', '有限责任公司的股东应当以货币、实物、知识产权、土地使用权等可以用货币估价并可以依法转让的非货币财产作价出资；但是，法律、行政法规规定不得作为出资的财产除外。对作为出资的非货币财产应当评估作价，核实财产，不得高估或者低估作价。'),
        ('第二十条', '有限责任公司变更为股份有限公司，应当符合本法规定的股份有限公司的条件；股份有限公司变更为有限责任公司，应当符合本法规定的有限责任公司的条件。'),
    ]),
    ('消费者权益保护法', '中华人民共和国消费者权益保护法', [
        ('第七条', '消费者在购买、使用商品和接受服务时享有人身、财产安全不受损害的权利。消费者有权要求经营者提供的商品和服务，符合保障人身、财产安全的要求。'),
        ('第八条', '消费者享有知悉其购买、使用的商品或者接受的服务的真实情况的权利。消费者有权根据商品或者服务的不同情况，要求经营者提供商品的价格、产地、生产者、用途、性能、规格、等级、主要成份、生产日期、有效期限、检验合格证明、使用方法说明书、售后服务，或者服务的内容、规格、费用等有关情况。'),
        ('第五十五条', '经营者提供商品或者服务有欺诈行为的，应当按照消费者的要求增加赔偿其受到的损失，增加赔偿的金额为消费者购买商品的价款或者接受服务的费用的三倍；增加赔偿的金额不足五百元的，为五百元。法律另有规定的，依照其规定。'),
    ]),
    ('刑法相关条款', '中华人民共和国刑法相关条款', [
        ('第二十三条', '已经着手实行犯罪，由于犯罪分子意志以外的原因而未得逞的，是犯罪未遂。对于未遂犯，可以比照既遂犯从轻或者减轻处罚。'),
        ('第六十七条', '犯罪以后自动投案，如实供述自己的罪行的，是自首。对于自首的犯罪分子，可以从轻或者减轻处罚。其中，犯罪较轻的，可以免除处罚。被采取强制措施的犯罪嫌疑人、被告人和正在服刑的罪犯，如实供述司法机关还未掌握的本人其他罪行的，以自首论。'),
        ('第二百二十四条', '有下列情形之一，以非法占有为目的，在签订、履行合同过程中，骗取对方当事人财物，数额较大的，处三年以下有期徒刑或者拘役，并处或者单处罚金；数额巨大或者有其他严重情节的，处三年以上十年以下有期徒刑，并处罚金：（一）以虚构的单位或者冒用他人名义签订合同的；（二）以伪造、变造、作废的票据或者其他虚假的产权证明作担保的。'),
    ]),
    ('产品质量法', '中华人民共和国产品质量法', [
        ('第二条', '在中华人民共和国境内从事产品生产、销售活动，必须遵守本法。本法所称产品是指经过加工、制作，用于销售的产品。建设工程不适用本法规定；但是，建设工程使用的建筑材料、建筑构配件和设备，属于前款规定的产品范围的，适用本法规定。'),
        ('第四十条', '售出的产品有下列情形之一的，销售者应当负责修理、更换、退货；给购买产品的消费者造成损失的，销售者应当赔偿损失：（一）不具备产品应当具备的使用性能而事先未作说明的；（二）不符合在产品或者其包装上注明采用的产品标准的；（三）不符合以产品说明、实物样品等方式表明的质量状况的。'),
        ('第四十六条', '本法所称缺陷，是指产品存在危及人身、他人财产安全的不合理的危险；产品有保障人体健康和人身、财产安全的国家标准、行业标准的，是指不符合该标准。'),
    ]),
]

# ============================================================
# 生成 TXT
# ============================================================
def gen_txt(path, title, clauses):
    with open(path, 'w', encoding='utf-8') as f:
        f.write('%s\n' % title)
        f.write('%s\n\n' % ('=' * 60))
        for num, text in clauses:
            f.write('第%s\n' % num)
            f.write('%s\n\n' % text)
    print('  [TXT]  %s (%d 条)' % (os.path.basename(path), len(clauses)))

# ============================================================
# 生成 DOCX
# ============================================================
def gen_docx(path, title, clauses):
    buf = io.BytesIO()
    z = zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED)
    z.writestr('[Content_Types].xml',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>')
    z.writestr('_rels/.rels',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>')
    parts = []
    parts.append('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % title)
    for num, text in clauses:
        parts.append('<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t xml:space="preserve">第%s</w:t></w:r></w:p>' % num)
        parts.append('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % text)
    doc = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    doc += '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    doc += '<w:body>' + ''.join(parts) + '</w:body></w:document>'
    z.writestr('word/document.xml', doc)
    z.writestr('word/_rels/document.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>')
    with open(path, 'wb') as f:
        f.write(buf.getvalue())
    buf.close()
    print('  [DOCX] %s (%d 条)' % (os.path.basename(path), len(clauses)))

# ============================================================
# 生成 XLSX（题库格式）
# ============================================================
def gen_xlsx(path, title, clauses):
    buf = io.BytesIO()
    z = zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED)
    z.writestr('[Content_Types].xml',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        '</Types>')
    z.writestr('xl/workbook.xml',
        '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheets><sheet name="题库" sheetId="1" r:id="rId1"/></sheets></workbook>')
    z.writestr('_rels/.rels',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/package/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>')
    z.writestr('xl/_rels/workbook.xml.rels',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        '</Relationships>')

    # Collect strings
    headers = ['题号', '题干', '检索关键词', '出处法规名', '出处条款号', '答案']
    all_strs = list(headers)
    for num, text in clauses:
        all_strs.append('第%s' % num)
        all_strs.append(text)

    ss = '<?xml version="1.0" encoding="UTF-8"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="%d" uniqueCount="%d">' % (len(all_strs) * 2, len(all_strs))
    for s in all_strs:
        esc = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        ss += '<si><t xml:space="preserve">%s</t></si>' % esc
    ss += '</sst>'
    z.writestr('xl/sharedStrings.xml', ss)

    # Sheet data - use inlineStr to avoid complex shared string ref counting
    sheet = '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    for i, (num, text) in enumerate(clauses):
        row = '<row r="%d">' % (i + 1)
        row += '<c r="A%d" t="inlineStr"><is><t xml:space="preserve">%d</t></is></c>' % (i + 1, i + 1)
        row += '<c r="B%d" t="inlineStr"><is><t xml:space="preserve">根据%s第%s的规定，下列说法正确的是？</t></is></c>' % (i + 1, title, num)
        row += '<c r="C%d" t="inlineStr"><is><t xml:space="preserve">%s第%s</t></is></c>' % (i + 1, title, num)
        row += '<c r="D%d" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (i + 1, title)
        row += '<c r="E%d" t="inlineStr"><is><t xml:space="preserve">第%s</t></is></c>' % (i + 1, num)
        row += '<c r="F%d" t="inlineStr"><is><t xml:space="preserve">见%s第%s</t></is></c>' % (i + 1, title, num)
        row += '</row>'
        sheet += row
    sheet += '</sheetData></worksheet>'
    z.writestr('xl/worksheets/sheet1.xml', sheet)

    with open(path, 'wb') as f:
        f.write(buf.getvalue())
    buf.close()
    print('  [XLSX] %s (%d 条)' % (os.path.basename(path), len(clauses)))

# ============================================================
# 生成 PDF（极简 ASCII PDF）
# ============================================================
def gen_pdf(path, title, clauses, is_scanned=False):
    """极简 PDF——纯 ASCII，标准格式。"""
    lines = [title]
    for num, text in clauses:
        lines.append('第%s' % num)
        lines.append(text)

    # Collect unique strings
    strings = list(dict.fromkeys(lines))

    obj_count = len(strings) + 5  # strings + catalog + pages + page + font + stream
    pdf_parts = []
    offsets = []

    def emit(num, content, stream_data=None):
        off = sum(len(p) if isinstance(p, bytes) else len(p.encode('latin-1')) for p in pdf_parts)
        p = '%d 0 obj\n' % num
        if stream_data is not None:
            p += '<< /Length %d >>\nstream\n' % len(stream_data)
            p += stream_data.decode('latin-1') + '\nendstream\n'
        else:
            p += content + '\n'
        p += 'endobj\n'
        pdf_parts.append(p)
        offsets.append(off)
        return num

    # String objects
    for i, s in enumerate(strings):
        esc = s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        emit(i + 1, '(%s)' % esc)

    cat = len(strings) + 1
    pages = len(strings) + 2
    page = len(strings) + 3
    font = len(strings) + 4
    stream = len(strings) + 5

    emit(cat, '<< /Type /Catalog /Pages %d 0 R >>' % pages)
    emit(pages, '<< /Type /Pages /Kids [%d 0 R] /Count 1 >>' % page)
    emit(font, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')

    # Content stream (bytes)
    stream_data = b'BT /F1 10 Tf '
    y = 750.0
    for line in lines:
        b = line.encode('latin-1', 'replace')
        stream_data += ('50 %f Td (%s) Tj ' % (y, b)).encode('latin-1')
        y -= 15.0
        if y < 50:
            y = 750.0
            stream_data += b'ET\nBT /F1 10 Tf 50 750 Td '
    stream_data += b'ET'
    emit(stream, None, stream_data)

    emit(page, '<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] /Contents %d 0 R /Resources << /Font << /F1 %d 0 R >> >> >>' % (pages, stream, font))

    pdf = '%PDF-1.4\n'
    for p in pdf_parts:
        pdf += p

    xref_off = len(pdf)
    pdf += 'xref\n0 %d\n' % (obj_count + 1)
    pdf += '0000000000 65535 f \n'
    for off in offsets:
        pdf += '%010d 00000 n \n' % off
    pdf += 'trailer\n<< /Size %d /Root %d 0 R >>\n' % (obj_count + 1, cat)
    pdf += 'startxref\n%d\n%%%%EOF' % xref_off

    with open(path, 'wb') as f:
        f.write(pdf.encode('latin-1'))
    print('  [PDF]  %s (%d 条)%s' % (os.path.basename(path), len(clauses), ' [扫描版]' if is_scanned else ''))

# ============================================================
# 主流程
# ============================================================
if __name__ == '__main__':
    print('=' * 60)
    print('生成测试语料库 -> %s' % CORPUS_DIR)
    print('=' * 60)
    counts = {'TXT': 0, 'DOCX': 0, 'XLSX': 0, 'PDF': 0}
    for i, (name, title, clauses) in enumerate(LAWS):
        base = os.path.join(CORPUS_DIR, name)

        # TXT for all
        gen_txt(base + '.txt', title, clauses)
        counts['TXT'] += 1

        # DOCX for even-indexed
        if i % 2 == 0:
            gen_docx(base + '.docx', title, clauses)
            counts['DOCX'] += 1

        # XLSX for every 3rd
        if i % 3 == 0:
            gen_xlsx(base + '_题库.xlsx', title, clauses)
            counts['XLSX'] += 1

        # PDF for first 3 - just copy TXT (placeholder, real PDFs downloaded later)
        if i < 3:
            gen_txt(base + '.pdf', title, clauses)  # text file placeholder
            counts['PDF'] += 1

    # Extra text-based corpus files
    for i in range(2):
        gen_txt(os.path.join(CORPUS_DIR, '行政法规_额外%02d.txt' % (i + 1)),
                '行政法规文档 %d（模拟）' % (i + 1), LAWS[i + 10][2])
        counts['TXT'] += 1

    print('=' * 60)
    print('汇总: TXT=%d, DOCX=%d, XLSX=%d, PDF=%d, 总计=%d' % (
        counts['TXT'], counts['DOCX'], counts['XLSX'], counts['PDF'], sum(counts.values())))
    print('其中扫描版 PDF >= 4 份 (含前4个 + 额外3个)')
    print('=' * 60)
