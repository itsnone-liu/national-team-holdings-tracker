#!/usr/bin/env python3
"""
国家队持仓数据采集系统 V2.6 - 自动同步版
移除不可靠的neodata财务字段，仅保留腾讯API+季报的真实数据
添加信号洞察自动生成 + 数据来源追踪
"""

import os, sys, json, urllib.request, time
from datetime import datetime

for k in list(os.environ):
    if "proxy" in k.lower(): os.environ.pop(k, None)

# ============================================================
NATIONAL_TEAM_ENTITIES = {
    "中央汇金": {
        "entities": ["中央汇金投资有限责任公司","中央汇金资产管理有限责任公司"],
        "color": "#ef4444", "type": "汇金系",
        "desc": "中国投资有限责任公司全资子公司，代表国家行使国有金融资产出资人权利"
    },
    "证金公司": {
        "entities": ["中国证券金融股份有限公司"],
        "color": "#00d4ff", "type": "证金系",
        "desc": "经国务院批准设立的全国性证券类金融机构，承担维护市场稳定职能"
    },
    "社保基金": {
        "entities": ["全国社会保障基金理事会","全国社保基金"],
        "color": "#22c55e", "type": "社保系",
        "desc": "国家战略储备基金，负责管理运营全国社会保障基金"
    },
    "养老金": {
        "entities": ["基本养老保险基金"],
        "color": "#f59e0b", "type": "养老金系",
        "desc": "各省市基本养老保险基金委托全国社保基金理事会投资运营"
    },
    "外管局": {
        "entities": ["梧桐树投资平台有限责任公司","北京凤山投资有限责任公司","北京坤藤投资有限责任公司"],
        "color": "#8b5cf6", "type": "外管局系",
        "desc": "国家外汇管理局旗下投资平台，代表外储进行境内股权投资"
    },
    "国家大基金": {
        "entities": ["国家集成电路产业投资基金股份有限公司","国家集成电路产业投资基金二期股份有限公司"],
        "color": "#14b8a6", "type": "大基金系",
        "desc": "国家集成电路产业投资基金，推动半导体产业自主可控"
    }
}

# ============================================================
# 国家队重仓宽基ETF追踪（每日更新）
# 汇金/证金通过ETF增持宽基指数基金，ETF份额/规模每日公布
# 数据源：腾讯财经实时（份额字段每日更新）
# first_holder字段来自上交所得/深交所得官网ETF季报（汇金公示持仓占比）
# ============================================================
ETF_TRACKING = [
    # 沪深300
    {"code":"510300","name":"沪深300ETF华泰柏瑞","index":"沪深300","category":"宽基/沪深300","note":"汇金核心增持标的",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":82.76,"data_source":"上交所ETF季报"},
    {"code":"510310","name":"沪深300ETF易方达","index":"沪深300","category":"宽基/沪深300","note":"汇金增持标的",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":85.27,"data_source":"上交所ETF季报"},
    {"code":"510330","name":"沪深300ETF华夏","index":"沪深300","category":"宽基/沪深300","note":"汇金增持标的",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":88.62,"data_source":"上交所ETF季报"},
    {"code":"159919","name":"沪深300ETF嘉实","index":"沪深300","category":"宽基/沪深300","note":"汇金增持标的",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":86.97,"data_source":"深交所ETF季报"},
    # 上证50
    {"code":"510050","name":"上证50ETF华夏","index":"上证50","category":"宽基/上证50","note":"汇金增持标的",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":86.05,"data_source":"上交所ETF季报"},
    # 上证180
    {"code":"510180","name":"上证180ETF华安","index":"上证180","category":"宽基/上证180","note":"汇金增持标的",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":91.93,"data_source":"上交所ETF季报"},
    # 中证500
    {"code":"510500","name":"中证500ETF南方","index":"中证500","category":"宽基/中证500","note":"汇金增持标的",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":74.58,"data_source":"上交所ETF季报"},
    {"code":"512500","name":"华夏中证500ETF","index":"中证500","category":"宽基/中证500","note":"汇金增持标的",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":65.76,"data_source":"上交所ETF季报"},
    # 中证1000
    {"code":"512100","name":"中证1000ETF南方","index":"中证1000","category":"宽基/中证1000","note":"汇金增持标的",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":86.43,"data_source":"上交所ETF季报"},
    {"code":"159845","name":"华夏中证1000ETF","index":"中证1000","category":"宽基/中证1000","note":"汇金增持标的",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":86.15,"data_source":"深交所ETF季报"},
    # 创业板 / 科创50
    {"code":"159915","name":"创业板ETF易方达","index":"创业板指","category":"宽基/创业板","note":"汇金增持标的",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":54.03,"data_source":"深交所ETF季报"},
    {"code":"159977","name":"创业板ETF天弘","index":"创业板指","category":"宽基/创业板","note":"汇金2025Q4增持2.31亿份",
     "first_holder_entity":"中央汇金投资有限责任公司","first_holder_share_pct":8.94,"data_source":"深交所ETF季报"},
    {"code":"588080","name":"科创50ETF易方达","index":"科创50","category":"宽基/科创50","note":"汇金增持标的",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":41.95,"data_source":"上交所ETF季报"},
    # 深证100 / 中证1000广发
    {"code":"159901","name":"深证100ETF易方达","index":"深证100","category":"宽基/深证100","note":"汇金资管持仓提升",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":35.12,"data_source":"深交所ETF季报"},
    {"code":"560010","name":"中证1000ETF广发","index":"中证1000","category":"宽基/中证1000","note":"汇金持仓比例>40%",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":41.30,"data_source":"上交所ETF季报"},
    # 中证A500（2024年9月新发，国家队大量认购）
    {"code":"563360","name":"A500ETF华泰柏瑞","index":"中证A500","category":"宽基/中证A500","note":"国家队核心认购",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":31.22,"data_source":"上交所ETF季报"},
    {"code":"159338","name":"中证A500ETF国泰","index":"中证A500","category":"宽基/中证A500","note":"国家队核心认购",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":30.56,"data_source":"深交所ETF季报"},
    {"code":"512050","name":"A500ETF华夏","index":"中证A500","category":"宽基/中证A500","note":"国家队核心认购",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":33.84,"data_source":"上交所ETF季报"},
    {"code":"159351","name":"A500ETF嘉实","index":"中证A500","category":"宽基/中证A500","note":"国家队认购",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":28.47,"data_source":"深交所ETF季报"},
    {"code":"560510","name":"中证A500ETF泰康","index":"中证A500","category":"宽基/中证A500","note":"国家队认购",
     "first_holder_entity":"中央汇金资产管理有限责任公司","first_holder_share_pct":25.93,"data_source":"上交所ETF季报"},
    # 行业主题（华夏汇金资管计划增持）
    {"code":"159852","name":"软件ETF嘉实","index":"中证软件服务","category":"主题/科技","note":"华夏汇金资管增持",
     "first_holder_entity":"华夏-汇金资管单一资管计划","first_holder_share_pct":12.35,"data_source":"深交所ETF季报"},
    {"code":"159865","name":"养殖ETF国泰","index":"中证畜牧养殖","category":"主题/农业","note":"华夏汇金资管增持",
     "first_holder_entity":"华夏-汇金资管单一资管计划","first_holder_share_pct":9.87,"data_source":"深交所ETF季报"},
]

ETF_HISTORY_FILE = "etf_history.json"  # 历史份额存档（每日）

# ============================================================
# 国家队核心持仓（数据报告期: 2026中报）
# ⚠️ 中报(2026H1)披露期 2026-08-31 截止，部分标的已退出前十大需人工核实更新
# 格式: {代码: {name, industry, sector, total_shares_yi, report_date, holders: [...]}}
# report_date: 该标的数据对应的财报报告期
# ============================================================
HOLDINGS_DATA = {
    "601398":{"name":"工商银行","industry":"银行","sector":"金融","total_shares":3564.06,"report_date":"2026中报","holders":[
        {"entity":"中央汇金投资有限责任公司","shares":124004660940,"ratio":34.79,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
        {"entity":"全国社会保障基金理事会","shares":12331645186,"ratio":3.46,"change_qoq":0,"team":"社保基金","team_type":"社保系"},
        {"entity":"中国证券金融股份有限公司","shares":2416131540,"ratio":0.68,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":1013921700,"ratio":0.28,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "601939":{"name":"建设银行","industry":"银行","sector":"金融","total_shares":2500.11,"report_date":"2026中报","holders":[
        {"entity":"中央汇金投资有限责任公司","shares":142857887595,"ratio":54.61,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
        {"entity":"中国证券金融股份有限公司","shares":2189259672,"ratio":0.84,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":496639800,"ratio":0.19,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "601288":{"name":"农业银行","industry":"银行","sector":"金融","total_shares":3499.83,"report_date":"2026中报","holders":[
        {"entity":"中央汇金投资有限责任公司","shares":140488809651,"ratio":40.14,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
        {"entity":"全国社会保障基金理事会","shares":23520968297,"ratio":6.72,"change_qoq":0,"team":"社保基金","team_type":"社保系"},
        {"entity":"中国证券金融股份有限公司","shares":1842751177,"ratio":0.53,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":1255434700,"ratio":0.36,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "601988":{"name":"中国银行","industry":"银行","sector":"金融","total_shares":2943.88,"report_date":"2026中报","holders":[
        {"entity":"中央汇金投资有限责任公司","shares":188791906533,"ratio":58.59,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
        {"entity":"中国证券金融股份有限公司","shares":7941164885,"ratio":2.46,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":1810024500,"ratio":0.56,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "601328":{"name":"交通银行","industry":"银行","sector":"金融","total_shares":883.9,"report_date":"2026中报","holders":[
        {"entity":"全国社会保障基金理事会","shares":11538488900,"ratio":13.05,"change_qoq":0,"team":"社保基金","team_type":"社保系"},
        {"entity":"中国证券金融股份有限公司","shares":1891651202,"ratio":2.14,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
    ]},
    "601318":{"name":"中国平安","industry":"保险","sector":"金融","total_shares":182.1,"report_date":"2026中报","holders":[
        {"entity":"中央汇金资产管理有限责任公司","shares":470302252,"ratio":2.6,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "601628":{"name":"中国人寿","industry":"保险","sector":"金融","total_shares":282.65,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":701686782,"ratio":2.48,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":117165585,"ratio":0.41,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "601601":{"name":"中国太保","industry":"保险","sector":"金融","total_shares":96.2,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":265325067,"ratio":2.76,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
    ]},
    "600030":{"name":"中信证券","industry":"证券","sector":"金融","total_shares":148.2,"report_date":"2026中报","holders":[
        {"entity":"中央汇金资产管理有限责任公司","shares":205146964,"ratio":1.38,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "601857":{"name":"中国石油","industry":"石油石化","sector":"能源","total_shares":1830.21,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":1020150744,"ratio":0.56,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":201695400,"ratio":0.11,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "600028":{"name":"中国石化","industry":"石油石化","sector":"能源","total_shares":1210.71,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":1978558034,"ratio":1.64,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":315223600,"ratio":0.26,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "601088":{"name":"中国神华","industry":"煤炭","sector":"能源","total_shares":198.9,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":583279356,"ratio":2.75,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":106077400,"ratio":0.5,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "601899":{"name":"紫金矿业","industry":"有色金属","sector":"资源","total_shares":265.57,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":437533690,"ratio":1.65,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
    ]},
    "688981":{"name":"中芯国际","industry":"半导体","sector":"科技","total_shares":80.02,"report_date":"2026中报","holders":[
        {"entity":"国家集成电路产业投资基金二期股份有限公司","shares":127458120,"ratio":1.59,"change_qoq":0,"team":"国家大基金","team_type":"大基金系"},
    ]},
    "601668":{"name":"中国建筑","industry":"建筑","sector":"基建","total_shares":413.2,"report_date":"2026中报","holders":[
        {"entity":"中央汇金资产管理有限责任公司","shares":583327120,"ratio":1.41,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
        {"entity":"中国证券金融股份有限公司","shares":289359130,"ratio":0.7,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
    ]},
    "601390":{"name":"中国中铁","industry":"建筑","sector":"基建","total_shares":246.9,"report_date":"2026中报","holders":[
        {"entity":"中央汇金资产管理有限责任公司","shares":230435700,"ratio":0.93,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "601800":{"name":"中国交建","industry":"建筑","sector":"基建","total_shares":162.8,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":383254745,"ratio":2.35,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":95990100,"ratio":0.59,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "601006":{"name":"大秦铁路","industry":"铁路运输","sector":"交运","total_shares":201.5,"report_date":"2026中报","holders":[
        {"entity":"中央汇金资产管理有限责任公司","shares":199894100,"ratio":0.99,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "600048":{"name":"保利发展","industry":"房地产","sector":"地产","total_shares":119.7,"report_date":"2026中报","holders":[
        {"entity":"中央汇金资产管理有限责任公司","shares":175821300,"ratio":1.47,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "000002":{"name":"万科A","industry":"房地产","sector":"地产","total_shares":119.3,"report_date":"2026中报","holders":[
        {"entity":"中央汇金资产管理有限责任公司","shares":185478200,"ratio":1.55,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "600104":{"name":"上汽集团","industry":"汽车","sector":"制造","total_shares":115.75,"report_date":"2026中报","holders":[
        {"entity":"中央汇金资产管理有限责任公司","shares":98585000,"ratio":0.86,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "000625":{"name":"长安汽车","industry":"汽车","sector":"制造","total_shares":99.1,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":352009758,"ratio":3.55,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
    ]},
    "000858":{"name":"五粮液","industry":"白酒","sector":"消费","total_shares":38.82,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":87164419,"ratio":2.25,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":39325400,"ratio":1.01,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "000568":{"name":"泸州老窖","industry":"白酒","sector":"消费","total_shares":14.72,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":32312117,"ratio":2.2,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":13539862,"ratio":0.92,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "600887":{"name":"伊利股份","industry":"食品饮料","sector":"消费","total_shares":63.64,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":126335480,"ratio":2.0,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
    ]},
    "000895":{"name":"双汇发展","industry":"食品饮料","sector":"消费","total_shares":34.65,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":54042598,"ratio":1.56,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":30904989,"ratio":0.89,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
    "000538":{"name":"云南白药","industry":"医药","sector":"医药","total_shares":17.91,"report_date":"2026中报","holders":[
        {"entity":"中国证券金融股份有限公司","shares":33985831,"ratio":1.9,"change_qoq":0,"team":"证金公司","team_type":"证金系"},
        {"entity":"中央汇金资产管理有限责任公司","shares":16617440,"ratio":0.93,"change_qoq":0,"team":"中央汇金","team_type":"汇金系"},
    ]},
}

ETF_HISTORY_FILE = "etf_history.json"  # 历史份额存档（每日）

# ============================================================
# 国家队核心持仓（数据报告期: 2026中报）
# ⚠️ 中报(2026H1)披露期 2026-08-31 截止，部分标的已退出前十大需人工核实更新
# 格式: {代码: {name, industry, sector, total_shares_yi, report_date, holders: [...]}}
# report_date: 该标的数据对应的财报报告期
# ============================================================

# ============================================================
# 腾讯实时行情
# ============================================================
def fetch_tencent_quotes(codes):
    SH_INDEX = {"000300","000905","000016","000688","000852","000010"}
    prefixed, key_of = [], {}
    for c in codes:
        low = c.lower()
        if low.startswith(("sh","sz","bj")): p = low
        elif c.startswith("92"): p = f"bj{c}"
        elif c in SH_INDEX or c.startswith(("5","6","9")): p = f"sh{c}"
        elif c.startswith(("4","8")): p = f"bj{c}"
        else: p = f"sz{c}"
        prefixed.append(p); key_of[p] = c
    results = {}
    for i in range(0, len(prefixed), 50):
        batch = prefixed[i:i+50]
        url = "https://qt.gtimg.cn/q=" + ",".join(batch)
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read().decode("gbk")
        except Exception as e:
            print(f"腾讯行情失败: {e}", file=sys.stderr)
            continue
        for line in data.strip().split(";"):
            if not line.strip() or "=" not in line or '"' not in line: continue
            key = line.split("=")[0].split("_")[-1]
            vals = line.split('"')[1].split("~")
            if len(vals) < 53: continue
            code = key_of.get(key, key[2:])
            try:
                h52 = float(vals[41]) if vals[41] else 0
                l52 = float(vals[42]) if vals[42] else 0
                price = float(vals[3]) if vals[3] else 0
                pos52 = round((price-l52)/(h52-l52)*100,1) if h52>0 and l52>0 and h52!=l52 else 0
                results[code] = {
                    "name": vals[1], "price": price,
                    "last_close": float(vals[4]) if vals[4] else 0,
                    "open": float(vals[5]) if vals[5] else 0,
                    "volume_hands": float(vals[6]) if vals[6] else 0,
                    "change_amount": float(vals[31]) if vals[31] else 0,
                    "change_pct": float(vals[32]) if vals[32] else 0,
                    "high": float(vals[33]) if vals[33] else 0,
                    "low": float(vals[34]) if vals[34] else 0,
                    "amount_wan": float(vals[37]) if vals[37] else 0,
                    "turnover_pct": float(vals[38]) if vals[38] else 0,
                    "pe_ttm": float(vals[39]) if vals[39] else 0,
                    "high_52w": h52, "low_52w": l52,
                    "amplitude": float(vals[43]) if vals[43] else 0,
                    "float_mcap_yi": float(vals[44]) if vals[44] else 0,
                    "mcap_yi": float(vals[45]) if vals[45] else 0,
                    "pb": float(vals[46]) if vals[46] else 0,
                    "limit_up": float(vals[47]) if vals[47] else 0,
                    "limit_down": float(vals[48]) if vals[48] else 0,
                    "volume_ratio": float(vals[49]) if vals[49] else 0,
                    "bid_ask_ratio": float(vals[50]) if vals[50] else 0,
                    "week_52_position": pos52,
                    "source": "腾讯财经实时"
                }
            except: continue
        time.sleep(0.2)
    return results

# ============================================================
# 腾讯ETF行情采集 - 每日份额/规模追踪
# 关键字段: 份额=[72]/[73]/[76]份, 规模=份额×现价(亿元)
# ============================================================
def fetch_etf_quotes(etf_list):
    """获取ETF每日行情+份额，计算规模与每日变化
    返回: {code: {name, price, change_pct, shares_yi, total_value_yi, ...}}
    """
    results = {}
    prefixed = []
    for e in etf_list:
        c = e["code"]
        prefixed.append(f"sh{c}" if c.startswith(("5","6")) else f"sz{c}")

    for i in range(0, len(prefixed), 30):
        batch = prefixed[i:i+30]
        url = "https://qt.gtimg.cn/q=" + ",".join(batch)
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read().decode("gbk")
        except Exception as e:
            print(f"  ETF行情失败: {e}", file=sys.stderr)
            continue

        for line in data.strip().split(";"):
            if not line.strip() or "=" not in line or '"' not in line: continue
            key = line.split("=")[0].split("_")[-1]
            vals = line.split('"')[1].split("~")
            if len(vals) < 80: continue
            code = key[2:] if key.startswith(("sh","sz")) else key
            try:
                price = float(vals[3]) if vals[3] else 0
                # 份额字段（份）
                shares_raw = float(vals[72]) if vals[72] and vals[72] != '' else 0
                shares_yi = round(shares_raw / 1e8, 2) if shares_raw else 0  # 亿份
                total_value_yi = round(shares_yi * price, 2) if price else 0  # 亿元
                results[code] = {
                    "name": vals[1],
                    "price": price,
                    "change_pct": float(vals[32]) if vals[32] else 0,
                    "change_amount": float(vals[31]) if vals[31] else 0,
                    "amount_wan": float(vals[37]) if vals[37] else 0,
                    "high_52w": float(vals[41]) if vals[41] else 0,
                    "low_52w": float(vals[42]) if vals[42] else 0,
                    "turnover_pct": float(vals[38]) if vals[38] else 0,
                    "volume_ratio": float(vals[49]) if vals[49] else 0,
                    "amplitude": float(vals[43]) if vals[43] else 0,
                    "shares_yi": shares_yi,
                    "total_value_yi": total_value_yi,
                    "source": "腾讯财经实时(每日更新)",
                }
            except: continue
        time.sleep(0.2)
    return results

# ============================================================
# ETF份额历史存档与变化倍数计算
# 每日收盘后追加历史份额，计算"今日份额变化倍数"作为信号
# 倍数 = |今日份额变化| / 近20个交易日平均|份额变化|
# ============================================================
def load_etf_history():
    """读取历史份额存档"""
    import os.path
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, ETF_HISTORY_FILE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def save_etf_history(history, etf_data):
    """追加今日份额数据到历史存档（按日期）"""
    import os.path
    today = datetime.now().strftime("%Y-%m-%d")
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, ETF_HISTORY_FILE)
    if today not in history:
        history[today] = {}
    for x in etf_data:
        history[today][x["code"]] = {
            "shares_yi": x["shares_yi"],
            "total_value_yi": x["total_value_yi"],
            "price": x["price"],
        }
    # 只保留近90天历史
    keys = sorted(history.keys())
    if len(keys) > 90:
        for k in keys[:-90]:
            del history[k]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return history

def build_etf_history_trend(history, etf_list):
    """构建ETF份额历史趋势（近30天，用于dashboard图表）
    返回: {code: {name, dates: [...], shares: [...]}}
    """
    dates = sorted(history.keys())
    if not dates:
        return {}
    trend = {}
    for e in etf_list:
        code = e["code"]
        series_dates, series_shares = [], []
        for d in dates:
            rec = history.get(d, {}).get(code)
            if rec and rec.get("shares_yi") is not None:
                series_dates.append(d)
                series_shares.append(rec["shares_yi"])
        if len(series_dates) > 1:
            trend[code] = {
                "name": e["name"],
                "index": e["index"],
                "dates": series_dates[-30:],
                "shares": series_shares[-30:],
            }
    return trend

# ============================================================
# 市场资金面数据采集（A股每日资金流向+两融余额+股指K线）
# 参考"预测高科"指标: 资金流量 = 股指 + 两融余额 - 超大单 - 大单
# ============================================================
def _collect_market_funds_section():
    print(f"\n[5/5] 采集市场资金面数据（A股资金流向+两融余额）...")
    section = {
        "index_klines": {},
        "fund_flow_sh": {},
        "fund_flow_sz": {},
        "margin_balance": {},
        "accumulated_small": 0,  # 累积小单资金（万元）
        "formula_note": "资金流量指标 = 股指 + 两融余额 - 超大单 - 大单（参考:预测高科）",
    }
    try:
        # 1. 指数K线（6个主要指数）
        section["index_klines"] = fetch_index_kline()
        print(f"  指数K线: {len(section['index_klines'])}个指数")
    except Exception as e:
        print(f"  指数K线失败: {e}", file=sys.stderr)

    try:
        # 2. A股每日资金流向（上证市场）
        section["fund_flow_sh"] = fetch_market_fund_flow("1.000001", 60)
        print(f"  沪市资金流向: {len(section['fund_flow_sh'])}天")
    except Exception as e:
        print(f"  沪市资金流向失败: {e}", file=sys.stderr)

    try:
        # 3. A股每日资金流向（深证市场）
        section["fund_flow_sz"] = fetch_market_fund_flow("0.399001", 60)
        print(f"  深市资金流向: {len(section['fund_flow_sz'])}天")
    except Exception as e:
        print(f"  深市资金流向失败: {e}", file=sys.stderr)

    try:
        # 4. 两融余额
        section["margin_balance"] = fetch_margin_balance()
        if section["margin_balance"].get("rows"):
            print(f"  两融余额: {section['margin_balance'].get('source')}, {len(section['margin_balance']['rows'])}天")
        else:
            print(f"  两融余额暂不可用（接口受限）")
    except Exception as e:
        print(f"  两融余额失败: {e}", file=sys.stderr)

    # 5. 写入累积历史（沪市 + 深市 + 两融）
    try:
        margin_today = {}
        if section["margin_balance"].get("rows"):
            first = section["margin_balance"]["rows"][0]
            margin_today["latest"] = {
                "date": first.get("date",""),
                "rzye": first.get("rzye",""),
                "rqye": first.get("rqylje") or first.get("rqye",""),
                "source": section["margin_balance"].get("source",""),
            }
        append_market_funds_history(section.get("fund_flow_sh"), margin_today,
                                    section.get("fund_flow_sz"))
    except Exception as e:
        print(f"  累积历史失败: {e}", file=sys.stderr)

    # 6. 合并历史回 section
    #    免费接口降级后只返回 1 天，直接用会让资金流量页退化成单点图；
    #    这里把 market_funds_history.json 的逐日累积合并进来，形成完整趋势。
    section, n_sh, n_sz = merge_fund_flow_history(section)
    print(f"  资金流历史合并: 沪市 {n_sh}天 | 深市 {n_sz}天")

    # 7. 累积"小单资金"（万元）——文章核心：与两融余额对比判断底部
    small_total = 0
    for d, v in section["fund_flow_sh"].items():
        small_total += v.get("small", 0) / 10000
    section["accumulated_small"] = round(small_total, 2)
    # 明确标注累计天数，避免"这是单日还是区间"的误读
    section["accumulated_small_days"] = n_sh
    section["accumulated_small_note"] = f"沪市小单净额按 {n_sh} 个交易日累计（单位：万元）"

    return section

def compute_etf_change_metrics(etf_data, history):
    """计算每只ETF的份额日变化和倍数信号"""
    today = datetime.now().strftime("%Y-%m-%d")
    keys = sorted(history.keys(), reverse=True)
    yesterday = keys[0] if keys else None  # 最近的（可能是今天/昨天）
    for x in etf_data:
        # 今日 vs 昨日
        prev_shares = 0
        prev_date = None
        if yesterday and yesterday != today:
            prev = history.get(yesterday, {}).get(x["code"])
            if prev: prev_shares = prev["shares_yi"]; prev_date = yesterday
        else:
            # 昨天没数据，找最近一次有数据的日期
            for k in keys:
                if k == today: continue
                prev = history.get(k, {}).get(x["code"])
                if prev: prev_shares = prev["shares_yi"]; prev_date = k; break
        x["prev_shares_yi"] = prev_shares
        x["prev_date"] = prev_date
        x["shares_change_yi"] = round(x["shares_yi"] - prev_shares, 2) if prev_shares else 0
        x["shares_change_pct"] = round((x["shares_change_yi"]/prev_shares*100), 2) if prev_shares else 0

        # 计算20日平均份额变化（绝对值）
        changes = []
        for k in sorted(history.keys()):
            if k == today: continue
            data = history.get(k, {}).get(x["code"])
            if data and len(changes) > 0:
                prev_data = history.get(sorted(history.keys())[sorted(history.keys()).index(k)-1] if sorted(history.keys()).index(k)>0 else k, {}).get(x["code"], {})
                if prev_data and prev_data.get("shares_yi"):
                    changes.append(abs(data["shares_yi"] - prev_data["shares_yi"]))
                if len(changes) >= 20: break
        if not changes and keys:
            # 用所有可用数据
            for i, k in enumerate(sorted(history.keys())[1:21], 1):
                prev_k = sorted(history.keys())[i-1]
                data = history.get(k, {}).get(x["code"])
                prev = history.get(prev_k, {}).get(x["code"])
                if data and prev:
                    changes.append(abs(data["shares_yi"] - prev["shares_yi"]))
        avg_change = sum(changes)/len(changes) if changes else 0
        x["avg_20d_change_yi"] = round(avg_change, 4)
        # 倍数信号
        if avg_change > 0 and x["shares_change_yi"] != 0:
            x["change_multiple"] = round(abs(x["shares_change_yi"]) / avg_change, 1)
        else:
            x["change_multiple"] = 0

    # 找出最强信号（按倍数排序）
    return etf_data

# ============================================================
# 腾讯K线采集 - 每日动量指标
# ============================================================
def code_to_prefixed(code):
    """将6位代码转为带交易所前缀"""
    if code.startswith(("5","6","9")) or code.startswith("000300"):
        return f"sh{code}"
    if code.startswith(("0","3")):
        return f"sz{code}"
    if code.startswith(("4","8")):
        return f"bj{code}"
    return f"sh{code}"

def fetch_kline_metrics(codes, days=260):
    """获取K线数据并计算动量指标（近5日/20日涨跌幅、区间回撤、52周兜底）
    返回: {code: {chg_5d, chg_20d, max_drawdown, kline, week_52_fallback...}}
    """
    results = {}
    for code in codes:
        pref = code_to_prefixed(code)
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={pref},day,,,{days},qfq"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            resp = urllib.request.urlopen(req, timeout=8)
            data = json.loads(resp.read().decode("utf-8"))
            node = data.get("data", {}).get(pref, {})
            days_arr = node.get("qfqday") or node.get("day") or []
            if len(days_arr) < 2:
                results[code] = None
                continue

            closes = [float(d[2]) for d in days_arr]
            last = closes[-1]

            def pct_change(n):
                if len(closes) > n and closes[-1-n] > 0:
                    return round((last / closes[-1-n] - 1) * 100, 2)
                return None

            # 区间最大回撤（基于近20日收盘价）
            window = closes[-21:] if len(closes) > 20 else closes
            peak = window[0]
            max_dd = 0
            for c in window:
                if c > peak: peak = c
                if peak > 0:
                    dd = (c - peak) / peak * 100
                    if dd < max_dd: max_dd = dd

            # 区间最高/最低
            hi_20 = max(window)
            lo_20 = min(window)

            # 52周兜底：基于近250个交易日K线计算52周高/低/位置（用于停牌股）
            window_52w = closes[-250:] if len(closes) > 250 else closes
            hi_52w_fallback = max(window_52w)
            lo_52w_fallback = min(window_52w)
            pos_52w_fallback = round((last - lo_52w_fallback) / (hi_52w_fallback - lo_52w_fallback) * 100, 1) if hi_52w_fallback != lo_52w_fallback else 0

            results[code] = {
                "chg_5d": pct_change(5),
                "chg_20d": pct_change(20),
                "chg_1d": pct_change(1),
                "max_drawdown_20d": round(max_dd, 2),
                "high_20d": hi_20,
                "low_20d": lo_20,
                "week_52_fallback": {
                    "high": round(hi_52w_fallback, 2),
                    "low": round(lo_52w_fallback, 2),
                    "position": pos_52w_fallback,
                },
                "kline": [[d[0], float(d[1]), float(d[2]), float(d[3]), float(d[4])] for d in days_arr[-30:]],
            }
        except Exception as e:
            print(f"  K线获取{code}失败: {e}", file=sys.stderr)
            results[code] = None
        time.sleep(0.12)
    return results

# ============================================================
# A股每日资金流向 + 两融余额（参考"预测高科"资金流量指标公式）
# 核心公式: 资金流量 = 股指 + 两融余额 - 超大单 - 大单
# ============================================================
def _http_get(url, headers=None, timeout=15):
    """带重试的HTTP GET"""
    import urllib.request
    h = {"User-Agent": "Mozilla/5.0"}
    if headers: h.update(headers)
    last_err = None
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=h)
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            last_err = e
            time.sleep(0.5 + i)
    raise last_err

def fetch_index_kline():
    """获取上证指数/沪深300/深证成指/中证1000 的日K线(260天)"""
    targets = {
        "sh000001":"上证指数","sz399001":"深证成指","sh000300":"沪深300",
        "sz399005":"中证500","sh000852":"中证1000","sh000016":"上证50",
    }
    results = {}
    for code, name in targets.items():
        pref = code if code.startswith("sh") else ("sz" if code.startswith("sz") else "sh") + code[2:]
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,260,qfq"
        try:
            data = json.loads(_http_get(url, timeout=10).decode("utf-8"))
            node = data.get("data", {}).get(code, {})
            arr = node.get("qfqday") or node.get("day") or []
            if arr:
                results[code] = {
                    "name": name,
                    "kline": [[d[0], float(d[1]), float(d[2]), float(d[3]), float(d[4])] for d in arr[-180:]],
                }
        except Exception as e:
            print(f"  指数{name}失败: {e}", file=sys.stderr)
    return results

def fetch_market_fund_flow(secid="1.000001", lmt=120):
    """获取A股每日资金流向(超大单/大单/中单/小单) - 多域名轮询
    secid: 1.000001=上证指数, 0.399001=深证成指, 1.000300=沪深300
    主域名push2可返回历史日线；备用push2delay只返回当天(分钟粒度)但更稳定
    返回: {date(YYYY-MM-DD): {super_big, big, medium, small, main}}
    """
    domains = ["push2.eastmoney.com", "push2delay.eastmoney.com", "push2his.eastmoney.com"]
    for domain in domains:
        # fflow/daykline 是日线接口（比 fflow/kline 更准）；push2delay 没这个端点会自动回退
        url = f"https://{domain}/api/qt/stock/fflow/daykline/get?secid={secid}&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56,f57,f58&lmt={lmt}"
        try:
            raw = _http_get(url, headers={"Referer":"https://quote.eastmoney.com/"}, timeout=15)
            data = json.loads(raw.decode("utf-8", errors="ignore"))
            pts = data.get("data", {}).get("klines", [])
            # daykline 也可能为空/失败，回退到原 kline 接口
            if not pts:
                url = f"https://{domain}/api/qt/stock/fflow/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt=101&lmt={lmt}"
                raw = _http_get(url, headers={"Referer":"https://quote.eastmoney.com/"}, timeout=15)
                data = json.loads(raw.decode("utf-8", errors="ignore"))
                pts = data.get("data", {}).get("klines", [])
            if pts:
                result = {}
                for p in pts:
                    parts = p.split(",")
                    if len(parts) >= 6:
                        date = parts[0].strip().split(" ")[0][:10]  # 去时间戳只留日期
                        # 分钟数据同日多条取最后一条
                        result[date] = {
                            "main": float(parts[1]),       # 主力净额(元)
                            "super_big": float(parts[2]),  # 超大单净额
                            "big": float(parts[3]),        # 大单净额
                            "medium": float(parts[4]),     # 中单净额
                            "small": float(parts[5]),      # 小单净额
                        }
                print(f"    资金流来源: {domain} ({len(result)}天)", file=sys.stderr)
                return result
        except Exception as e:
            print(f"    资金流{domain}失败: {str(e)[:60]}", file=sys.stderr)
            continue
    print(f"  资金流向{secid}所有域名失败", file=sys.stderr)
    return {}

def fetch_margin_balance():
    """获取沪深两市两融余额(尝试多个源，失败兜底)
    上交所官方接口可用: 沪市融资余额(rzye)/融券余额(rqylje)
    深交所接口暂不可用，两融数据暂为沪市口径
    """
    import re as _re
    candidates = [
        # 上交所官网两融汇总（沪市） - 最稳定
        ("https://query.sse.com.cn/marketdata/tradedata/queryMargin.do?jsonCallBack=callback&isPagination=true&sqlId=COMMON_SSE_ZZ_MARGIN_SSEKCB_L&type=inparams&REG_PROD_CODE=001&pageHelp.pageSize=5&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.cacheSize=1&_=1690000000",
         lambda r: {"date":_fmt_date(r.get("opDate","")), "rzye":r.get("rzye",""), "rqylje":r.get("rqylje",""), "rzye_change":r.get("rzmre",""), "source":"sse"},
         "https://www.sse.com.cn/"),
        # 东财数据中心 RPT_MMS_RZRQ_ALL
        ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_MMS_RZRQ_ALL&columns=ALL&pageSize=5&pageNumber=1&sortColumns=date&sortTypes=-1",
         lambda r: {"date":r.get("date",""), "rzye":r.get("RZYE",""), "rqye":r.get("RQYE",""), "rzye_change":r.get("RZYE_PREVDAY_DIFF",""), "source":"eastmoney"},
         "https://data.eastmoney.com/"),
    ]
    for url, mapper, referer in candidates:
        try:
            raw = _http_get(url, headers={"Referer":referer}, timeout=10)
            txt = raw.decode("utf-8", errors="ignore")
            rows = []
            if "callback" in txt:
                m = _re.search(r'callback\((.*)\)', txt, _re.S)
                if m:
                    j = json.loads(m.group(1))
                    rows = j.get("result") or j.get("pageHelp", {}).get("data") or []
            else:
                j = json.loads(txt)
                rows = j.get("result", {}).get("data", []) or (j if isinstance(j, list) else [])
            if rows:
                return {"source": "sse_mar", "rows": [mapper(r) for r in rows]}
        except Exception as e:
            print(f"  两融接口试源失败: {str(e)[:60]}", file=sys.stderr)
    return {"source":"unavailable", "rows": []}

def _fmt_date(d):
    """20260821 -> 2026-08-21"""
    if len(d) == 8:
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return d

def append_market_funds_history(market_funds_today, margin_today, sz_today=None):
    """累积A股资金流向/两融余额历史
    文件: market_funds_history.json
    结构（兼容旧存档）:
      { "YYYY-MM-DD": {沪市资金流字段...},      # 沪市（历史沿用扁平结构）
        "__sz__":     { "YYYY-MM-DD": {深市...}}, # 深市（新增，从启用日起累积）
        "__margin__": { "latest": {...} } }
    """
    import datetime as _dt
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "market_funds_history.json")
    history = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except: pass
    # 合并今天沪市数据（只保留纯日期格式 YYYY-MM-DD，过滤分钟数据）
    if market_funds_today:
        for date, vals in market_funds_today.items():
            d = date.strip()[:10]
            if len(d) == 10 and '-' in d:
                history.setdefault(d, {})
                history[d].update(vals)
    # 合并今天深市数据（单独命名空间，避免与沪市扁平结构冲突）
    if sz_today:
        history.setdefault("__sz__", {})
        for date, vals in sz_today.items():
            d = date.strip()[:10]
            if len(d) == 10 and '-' in d:
                history["__sz__"].setdefault(d, {})
                history["__sz__"][d].update(vals)
        # 深市也只保留近500天
        if len(history["__sz__"]) > 500:
            for old in sorted(history["__sz__"].keys())[:-500]:
                del history["__sz__"][old]
    # 合并两融
    if margin_today:
        history.setdefault("__margin__", {})
        history["__margin__"].update(margin_today)
    # 只保留近500天（排除特殊键）
    keys = [k for k in history.keys() if not k.startswith("__")]
    if len(keys) > 600:
        keys.sort()
        for old in keys[:-500]:
            del history[old]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return history


def merge_fund_flow_history(section):
    """把 market_funds_history.json 的历史合并回当日 section。

    背景：免费接口（push2delay 降级后）只返回 1 天数据，若直接用当日结果，
    资金流量页只能画单点。历史存档里已按日累积了沪市/深市资金流，
    这里把历史与当日合并（当日覆盖历史），让页面呈现完整多日趋势。
    """
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "market_funds_history.json")
    if not os.path.exists(path):
        return section, 0, 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        return section, 0, 0

    # 沪市：扁平结构 {date: {...}}
    merged_sh = {}
    for date, vals in history.items():
        if date.startswith("__") or not isinstance(vals, dict):
            continue
        merged_sh[date] = dict(vals)
    merged_sh.update(section.get("fund_flow_sh") or {})   # 当日优先

    # 深市：__sz__ 命名空间
    merged_sz = {}
    sz_hist = history.get("__sz__") or {}
    if isinstance(sz_hist, dict):
        for date, vals in sz_hist.items():
            if isinstance(vals, dict):
                merged_sz[date] = dict(vals)
    merged_sz.update(section.get("fund_flow_sz") or {})   # 当日优先

    if merged_sh:
        section["fund_flow_sh"] = merged_sh
    if merged_sz:
        section["fund_flow_sz"] = merged_sz
    return section, len(merged_sh), len(merged_sz)

# ============================================================
# 信号洞察生成
# ============================================================
def fetch_news_neodata():
    """通过neodata获取国家队相关最新新闻"""
    import subprocess
    NEODATA_SCRIPT = "/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/resources/builtin-skills/neodata-financial-search/scripts/query.py"
    queries = [
        "国家队 汇金 证金 社保 持仓 增持 减持 2026年7月 2026年8月",
        "中央汇金 证金公司 社保基金 调仓 最新",
        "国家队重仓股 国家队动态 国家队持仓变化",
    ]
    results = []
    seen_titles = set()
    for q in queries:
        try:
            proc = subprocess.run(
                [sys.executable, NEODATA_SCRIPT, "--data-type", "doc", "--query", q],
                capture_output=True, text=True, timeout=20
            )
            if proc.returncode == 0 and proc.stdout.strip():
                r = json.loads(proc.stdout)
                for d in r.get("data",{}).get("docData",{}).get("docRecall",[]):
                    for item in d.get("docList",[]):
                        title = item.get("title","")[:80]
                        if title in seen_titles or not title:
                            continue
                        seen_titles.add(title)
                        results.append({
                            "title": title,
                            "source": item.get("source",""),
                            "time": item.get("publishTime",""),
                            "url": item.get("url",""),
                            "summary": (item.get("content","") or item.get("summary",""))[:200]
                        })
                if len(results) >= 10:
                    break
        except Exception as e:
            print(f"  neodata新闻查询失败: {e}", file=sys.stderr)
        time.sleep(0.3)
    return results[:10]


def generate_insights(holdings_detail, stock_summary, team_summary, sector_summary):
    """基于真实数据自动生成分析洞察"""
    insights = []

    # 1. 持仓集中度
    top1 = team_summary[0] if team_summary else None
    total_val = sum(t["total_holding_value"] for t in team_summary)
    if top1 and total_val > 0:
        pct = top1["total_holding_value"] / total_val * 100
        insights.append({
            "type": "concentration",
            "level": "warn" if pct > 80 else "info",
            "title": "持仓高度集中",
            "detail": f"{top1['team']}（{top1['team_type']}）占国家队总持仓 {pct:.0f}%，集中于四大行等金融蓝筹",
        })

    # 2. 银行板块集中度
    bank_val = sum(e["holding_value_yi"] for e in holdings_detail if e["industry"] == "银行")
    if total_val > 0:
        bank_pct = bank_val / total_val * 100
        insights.append({
            "type": "sector_concentration",
            "level": "warn" if bank_pct > 80 else "info",
            "title": f"银行板块占{bank_pct:.0f}%",
            "detail": f"银行板块持仓市值 {bank_val/10000:.1f}万亿，占国家队总持仓 {bank_pct:.0f}%，反映国家队以金融稳定为核心目标",
        })

    # 3. QoQ变动信号（只显示有真实变动的）
    report_label = holdings_detail[0].get("report_date", "2026中报") if holdings_detail else "2026中报"
    changes = []
    for e in holdings_detail:
        chg = e.get("change_qoq", 0)
        chg_pct = e.get("change_pct_qoq", 0)
        if chg != 0 and chg_pct != 0:
            changes.append(e)
    if changes:
        for ch in changes[:5]:
            direction = "增持" if ch["change_qoq"] > 0 else "减持"
            insights.append({
                "type": "position_change",
                "level": "alert" if abs(ch.get("change_pct_qoq",0)) > 10 else "info",
                "title": f"{ch['team']}{report_label}{direction}{ch['name']}",
                "detail": f"{ch['entity']} 在{report_label}{direction}{ch['name']} {abs(ch['change_qoq'])/10000:.0f}万股（{ch.get('change_pct_qoq',0):.1f}%）",
            })
    else:
        insights.append({
            "type": "position_stable",
            "level": "info",
            "title": f"{report_label}持仓整体稳定",
            "detail": f"{report_label}披露显示，国家队核心持仓未发生重大变动，主要仓位持平。",
        })

    # 4. 估值水平分析
    low_pe = [s for s in stock_summary if 0 < s["pe_ttm"] < 10]
    high_52w = [s for s in stock_summary if (s.get("week_52_position") or 0) > 80]
    low_52w = [s for s in stock_summary if 0 < (s.get("week_52_position") or 0) < 20]

    if low_pe:
        insights.append({
            "type": "valuation",
            "level": "info",
            "title": f"{len(low_pe)}只标的PE<10倍",
            "detail": f"低估值标的：{', '.join(s['name'] for s in low_pe[:5])}。银行板块整体PE处于历史低位，国家队持仓以价值蓝筹为主。",
        })
    if high_52w:
        insights.append({
            "type": "technical",
            "level": "warn",
            "title": f"{len(high_52w)}只标的处于52周高位",
            "detail": f"接近52周高点: {', '.join(s['name'] for s in high_52w[:5])}。短期追高风险较大，关注回调机会。",
        })
    if low_52w:
        insights.append({
            "type": "opportunity",
            "level": "opportunity",
            "title": f"{len(low_52w)}只标的处于52周低位",
            "detail": f"接近52周低点: {', '.join(s['name'] for s in low_52w[:5])}。可关注国家队是否在低位加仓。",
        })

    # 5. 今日涨跌统计
    up_stocks = [s for s in stock_summary if s["change_pct"] > 0]
    down_stocks = [s for s in stock_summary if s["change_pct"] < 0]
    insights.append({
        "type": "daily_market",
        "level": "info",
        "title": f"今日{len(up_stocks)}涨{len(down_stocks)}跌",
        "detail": f"国家队持仓标的今日涨跌比 {len(up_stocks)}:{len(down_stocks)}，涨幅最大: {(up_stocks[:1] or [{'name':'无','change_pct':0}])[0]['name']}，跌幅最大: {(down_stocks[:1] or [{'name':'无','change_pct':0}])[0]['name']}",
    })

    # 6. 近20日动量信号（每日更新）
    mom_stocks = [s for s in stock_summary if s.get("chg_20d") is not None]
    if mom_stocks:
        strong = [s for s in mom_stocks if s["chg_20d"] > 10]
        weak = [s for s in mom_stocks if s["chg_20d"] < -10]
        if strong:
            insights.append({
                "type": "momentum_strong",
                "level": "info",
                "title": f"{len(strong)}只标的近20日强势上涨",
                "detail": f"近20日涨幅>10%: {', '.join(s['name']+'({:+.1f}%)'.format(s['chg_20d']) for s in strong[:5])}",
            })
        if weak:
            insights.append({
                "type": "momentum_weak",
                "level": "warn",
                "title": f"{len(weak)}只标的近20日走弱",
                "detail": f"近20日跌幅>10%: {', '.join(s['name']+'({:+.1f}%)'.format(s['chg_20d']) for s in weak[:5])}，关注是否补仓",
            })

    # 7. 最大回撤警示（近20日）
    dd_stocks = [s for s in stock_summary if s.get("max_drawdown_20d") is not None and s["max_drawdown_20d"] < -15]
    if dd_stocks:
        insights.append({
            "type": "drawdown_warn",
            "level": "alert",
            "title": f"{len(dd_stocks)}只标的近20日回撤超15%",
            "detail": f"最大回撤: {', '.join(s['name']+'({:.0f}%)'.format(s['max_drawdown_20d']) for s in dd_stocks[:5])}",
        })

    return insights

# ============================================================
# 主函数
# ============================================================
def main():
    print("=" * 60)
    print("  国家队持仓数据采集 V2.6 (自动同步版)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    codes = list(HOLDINGS_DATA.keys())

    # [1] 腾讯行情
    print(f"\n[1/3] 获取 {len(codes)} 只股票实时行情...")
    quotes = fetch_tencent_quotes(codes)
    print(f"  成功: {len(quotes)} 只")

    # [1.5] 腾讯K线 - 每日动量指标
    print(f"\n[1.5] 获取K线数据计算动量指标（近5/20日涨跌幅、区间回撤）...")
    kline_metrics = fetch_kline_metrics(codes)
    kline_ok = sum(1 for v in kline_metrics.values() if v)
    print(f"  成功: {kline_ok}/{len(codes)} 只")

    # [2] 构建数据集
    print(f"\n[2/3] 构建增强数据集...")
    holdings_detail = []
    for code, info in HOLDINGS_DATA.items():
        q = quotes.get(code, {})
        km = kline_metrics.get(code) or {}
        price = q.get("price", 0)
        for h in info["holders"]:
            if not h["team"]: continue
            holding_val = round(h["shares"] * price / 1e8, 2) if price > 0 else 0
            holdings_detail.append({
                "code": code, "name": info["name"],
                "industry": info["industry"], "sector": info["sector"],
                "entity": h["entity"], "shares": h["shares"],
                "ratio": h["ratio"], "team": h["team"], "team_type": h["team_type"],
                # 报告期（持仓数据的财报期，季度更新）
                "report_date": info.get("report_date", "2026中报"),
                # QoQ变化
                "change_qoq": h.get("change_qoq", 0),
                "change_pct_qoq": h.get("change_pct_qoq", 0),
                # 行情 (来源: 腾讯财经实时)
                "price": price, "change_pct": q.get("change_pct", 0),
                "change_amount": q.get("change_amount", 0),
                "open": q.get("open", 0), "high": q.get("high", 0),
                "low": q.get("low", 0), "amount_wan": q.get("amount_wan", 0),
                "turnover_pct": q.get("turnover_pct", 0),
                "amplitude": q.get("amplitude", 0),
                "volume_ratio": q.get("volume_ratio", 0),
                # 估值 (来源: 腾讯财经实时)
                "pe_ttm": q.get("pe_ttm", 0), "pb": q.get("pb", 0),
                "mcap_yi": q.get("mcap_yi", 0),
                "float_mcap_yi": q.get("float_mcap_yi", 0),
                # 52周 (来源: 腾讯财经实时; 停牌股用K线兜底)
                "high_52w": q.get("high_52w", 0) or (km.get("week_52_fallback") or {}).get("high", 0),
                "low_52w": q.get("low_52w", 0) or (km.get("week_52_fallback") or {}).get("low", 0),
                "week_52_position": q.get("week_52_position", 0) or (km.get("week_52_fallback") or {}).get("position", 0),
                # 限价
                "limit_up": q.get("limit_up", 0),
                "limit_down": q.get("limit_down", 0),
                # 每日动量指标 (来源: 腾讯K线)
                "chg_5d": km.get("chg_5d"),
                "chg_20d": km.get("chg_20d"),
                "max_drawdown_20d": km.get("max_drawdown_20d"),
                "high_20d": km.get("high_20d"),
                "low_20d": km.get("low_20d"),
                "kline": km.get("kline", []),
                # 停牌判定: K线最新日期距今天超过5个交易日(约7天)视为停牌
                "is_suspended": 0,
                # 持仓计算
                "holding_value_yi": holding_val,
                # 数据来源标签
                "data_source": {
                    "price": "腾讯财经实时",
                    "pe_pb": "腾讯财经实时",
                    "kline": "腾讯K线(近30日)",
                    "shares": info.get("report_date", "2026中报"),
                    "holding_value": info.get("report_date", "2026中报") + "持仓×实时价格(估算)",
                }
            })

    # 停牌判定：K线最新日期距今天超过7个自然日视为停牌
    import datetime as _dt
    _today = _dt.date.today()
    for e in holdings_detail:
        kl = e.get("kline", [])
        if kl and len(kl) > 0:
            try:
                last_kline_date = _dt.datetime.strptime(kl[-1][0], "%Y-%m-%d").date()
                if (_today - last_kline_date).days > 7:
                    e["is_suspended"] = 1
            except:
                pass

    # 团队汇总
    team_summary = {}
    for e in holdings_detail:
        t = e["team"]
        if t not in team_summary:
            team_summary[t] = {"team": t, "team_type": e["team_type"],
                "stock_count": 0, "total_holding_value": 0, "stocks": []}
        team_summary[t]["stock_count"] += 1
        team_summary[t]["total_holding_value"] += e["holding_value_yi"]
        if e["name"] not in team_summary[t]["stocks"]:
            team_summary[t]["stocks"].append(e["name"])

    # 行业汇总
    sector_summary = {}
    for e in holdings_detail:
        s = e["sector"]
        if s not in sector_summary:
            sector_summary[s] = {"sector": s, "total_value": 0, "count": 0}
        sector_summary[s]["total_value"] += e["holding_value_yi"]
        sector_summary[s]["count"] += 1

    # 个股汇总
    stock_summary = {}
    for e in holdings_detail:
        c = e["code"]
        if c not in stock_summary:
            stock_summary[c] = {
                "code": c, "name": e["name"], "industry": e["industry"],
                "sector": e["sector"], "price": e["price"],
                "change_pct": e["change_pct"], "pe_ttm": e["pe_ttm"],
                "pb": e["pb"], "mcap_yi": e["mcap_yi"],
                "float_mcap_yi": e["float_mcap_yi"],
                "amount_wan": e["amount_wan"],
                "turnover_pct": e["turnover_pct"],
                "volume_ratio": e["volume_ratio"],
                "amplitude": e["amplitude"],
                "high_52w": e["high_52w"], "low_52w": e["low_52w"],
                "week_52_position": e["week_52_position"],
                "limit_up": e["limit_up"], "limit_down": e["limit_down"],
                # 每日动量指标
                "chg_5d": e.get("chg_5d"),
                "chg_20d": e.get("chg_20d"),
                "max_drawdown_20d": e.get("max_drawdown_20d"),
                "kline": e.get("kline", []),
                "is_suspended": e.get("is_suspended", 0),
                "total_holding_value": 0, "holders": [],
            }
        stock_summary[c]["total_holding_value"] += e["holding_value_yi"]
        stock_summary[c]["holders"].append({
            "entity": e["entity"], "team": e["team"],
            "team_type": e["team_type"], "ratio": e["ratio"],
            "change_qoq": e["change_qoq"],
            "change_pct_qoq": e.get("change_pct_qoq", 0),
            "value_yi": e["holding_value_yi"],
        })

    # 行业×团队矩阵
    industry_team_matrix = {}
    for e in holdings_detail:
        key = f"{e['industry']}|{e['team']}"
        industry_team_matrix[key] = industry_team_matrix.get(key, 0) + e["holding_value_yi"]

    # [3] 生成信号洞察 + 采集新闻
    print(f"\n[3/3] 生成分析信号 + 采集新闻...")
    sorted_team = sorted(team_summary.values(), key=lambda x: x["total_holding_value"], reverse=True)
    sorted_sector = sorted(sector_summary.values(), key=lambda x: x["total_value"], reverse=True)
    sorted_stock = sorted(stock_summary.values(), key=lambda x: x["total_holding_value"], reverse=True)
    sorted_holdings = sorted(holdings_detail, key=lambda x: x["holding_value_yi"], reverse=True)

    insights = generate_insights(sorted_holdings, sorted_stock, sorted_team, sorted_sector)

    # [4] 采集ETF持仓数据（每日更新）
    print(f"\n[4/4] 采集国家队重仓ETF数据...")
    etf_quotes = fetch_etf_quotes(ETF_TRACKING)
    etf_data = []
    for e in ETF_TRACKING:
        q = etf_quotes.get(e["code"])
        if q:
            etf_data.append({
                "code": e["code"], "name": q["name"],
                "index": e["index"], "category": e["category"],
                "note": e["note"],
                "first_holder_entity": e.get("first_holder_entity"),
                "first_holder_share_pct": e.get("first_holder_share_pct"),
                "first_holder_data_source": e.get("data_source"),
                "price": q["price"], "change_pct": q["change_pct"],
                "amount_wan": q["amount_wan"],
                "shares_yi": q["shares_yi"],
                "total_value_yi": q["total_value_yi"],
                "turnover_pct": q["turnover_pct"],
                "volume_ratio": q["volume_ratio"],
                "amplitude": q["amplitude"],
                "high_52w": q["high_52w"], "low_52w": q["low_52w"],
                "source": q["source"],
            })

    # 加载历史并保存今日
    history = load_etf_history()
    etf_data = compute_etf_change_metrics(etf_data, history)
    save_etf_history(history, etf_data)

    total_etf_value = sum(x["total_value_yi"] for x in etf_data)
    has_history = any(x.get("prev_shares_yi", 0) > 0 for x in etf_data)
    print(f"  ETF数据: {len(etf_data)}只 | 总规模 {total_etf_value:.0f}亿元 | 历史{'已初始化' if not has_history else '对比可用'}")
    # 每日申赎信号：当日成交额>规模1%为活跃
    etf_signals = []
    for x in etf_data:
        if x["amount_wan"] > 0 and x["total_value_yi"] > 0:
            turnover_ratio = x["amount_wan"] / 10000 / x["total_value_yi"] * 100
            x["turnover_ratio_pct"] = round(turnover_ratio, 2)
            if turnover_ratio > 3:
                etf_signals.append({
                    "level": "alert",
                    "title": f"{x['name']}今日换手{turnover_ratio:.1f}%",
                    "detail": f"{x['name']}({x['code']})今日成交额{x['amount_wan']/10000:.0f}亿，占规模{turnover_ratio:.1f}%，交投异常活跃",
                })

    # 倍数信号：份额变化倍数>3视为国家队动作
    multiplier_signals = []
    if has_history:
        for x in etf_data:
            if x.get("change_multiple", 0) >= 3 and x.get("shares_change_yi", 0) != 0:
                direction = "赎回" if x["shares_change_yi"] < 0 else "申购"
                multiplier_signals.append({
                    "level": "alert",
                    "title": f"{x['name']}今日{x['change_multiple']:.1f}倍量{direction}",
                    "detail": f"{x['name']}份额{x['shares_change_yi']:+.2f}亿份（{x['shares_change_pct']:+.2f}%），是近20日均值的{x['change_multiple']:.1f}倍",
                })
        if multiplier_signals:
            etf_signals = multiplier_signals + etf_signals
            print(f"  🔴 倍数信号: {len(multiplier_signals)}条")

    # 采集国家队相关新闻
    try:
        news = fetch_news_neodata()
        print(f"  获取 {len(news)} 条国家队相关新闻")
    except Exception as e:
        print(f"  新闻采集失败: {e}", file=sys.stderr)
        news = []
    print(f"  生成 {len(insights)} 条洞察")

    # 保留主力资金流数据（由 update_fund_flow.py 通过腾讯自选股MCP采集固化，
    # 资金流直连接口均不可用，本脚本重建 data.json 时原样保留避免丢失）
    _prev_ff = None
    # 保留板块主力资金监控数据（由 collect_sector_flow.py 采集，新浪日级口径，
    # 重建 data.json 时同样原样保留）
    _prev_sf = None
    try:
        _prev_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
        with open(_prev_path, "r", encoding="utf-8") as _f:
            _prev_data = json.load(_f)
            _prev_ff = _prev_data.get("main_force_flow")
            _prev_sf = _prev_data.get("sector_flow")
    except Exception:
        _prev_ff = None
        _prev_sf = None

    # 构建输出
    output = {
        "meta": {
            "title": "国家队持仓实时追踪分析",
            "version": "2.6",
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_period": "2026中报 + 腾讯财经实时行情",
            "data_integrity_note": "持仓数据基于2026中报十大流通股东核实(通达信)，行情数据为腾讯财经实时接口，持仓市值=中报持股数×实时价格（估算值）",
            "data_warning": "持仓数据已更新至2026中报(通达信十大流通股东核实)，剔除国家队退出前十的标的(茅台/海康/长电/广核/紫光国微/海通/同仁堂/上海机场/恒瑞医药/国泰君安)，修正多只标的持仓团队与比例；行情数据每日更新",
            "total_stocks": len(stock_summary),
            "total_holdings": len(holdings_detail),
            "total_value_yi": round(sum(e["holding_value_yi"] for e in holdings_detail), 2),
            "market_status": "交易中" if 9 <= datetime.now().hour < 15 else "已收盘",
        },
        "national_team_entities": NATIONAL_TEAM_ENTITIES,
        "team_summary": sorted_team,
        "sector_summary": sorted_sector,
        "stock_summary": sorted_stock,
        "holdings_detail": sorted_holdings,
        "industry_team_matrix": industry_team_matrix,
        "insights": insights,
        "news": news,
        "etf_data": etf_data,
        "etf_signals": etf_signals,
        "etf_total_value_yi": round(total_etf_value, 2),
        "etf_history_trend": build_etf_history_trend(history, ETF_TRACKING),
        "market_funds": _collect_market_funds_section(),
    }
    if _prev_ff:
        output["main_force_flow"] = _prev_ff
    if _prev_sf:
        output["sector_flow"] = _prev_sf

    # 保存
    base = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(base, "data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 同步 dashboard.html 内嵌快照（双击 file:// 打开时显示最新数据）
    sync_dashboard_embedded(output)

    # 打印摘要
    print(f"\n{'='*60}")
    print(f"  数据采集完成 V2.6")
    print(f"  标的: {output['meta']['total_stocks']}只 记录: {output['meta']['total_holdings']}条")
    tv = output['meta']['total_value_yi']
    print(f"  持仓市值: {tv/10000:.2f}万亿" if tv>10000 else f"  持仓市值: {tv:.1f}亿")
    print(f"  信号洞察: {len(insights)}条")
    for ins in insights:
        icon = {"warn":"⚠️","alert":"🔴","info":"ℹ️","opportunity":"💡"}.get(ins["level"],"•")
        print(f"    {icon} {ins['title']}")
    print(f"{'='*60}")
    return output

def sync_dashboard_embedded(output):
    """把最新 data.json 数据同步进 dashboard.html 的内嵌 JSON 快照。

    背景: dashboard.html 支持两种打开方式:
      1. http.server 模式 -> fetch('data.json') 实时读最新数据
      2. 双击 file:// 模式 -> 读页面内嵌 <script id="embedded-data"> 快照
    每次采集后同步内嵌快照,保证双击打开也是最新数据。
    """
    import re as _re2
    base = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base, "dashboard.html")
    if not os.path.exists(html_path):
        print("  ⚠️ dashboard.html 不存在，跳过同步", file=sys.stderr)
        return False
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        data_json = json.dumps(output, ensure_ascii=False).replace("</", "<\\/")
        pattern = r'(<script type="application/json" id="embedded-data">)([\s\S]*?)(</script>)'
        new_html, n = _re2.subn(pattern, lambda m: m.group(1) + data_json + m.group(3), html, count=1)
        if n == 0:
            print("  ⚠️ dashboard.html 未找到内嵌数据标签，跳过同步", file=sys.stderr)
            return False
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(new_html)
        print(f"  ✅ dashboard.html 内嵌数据已同步 ({(len(new_html)//1024)}KB)")
        return True
    except Exception as e:
        print(f"  ⚠️ dashboard.html 同步失败: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    main()
