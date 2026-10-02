#!/usr/bin/env python3
"""
主力资金流监控数据更新脚本 —— 国家队持仓追踪分析系统

【数据来源 · 真实可追溯】
  1. 全市场主力净流入 / 净流出 TOP10：腾讯自选股 MCP 排行接口
     metric = cap_main_net（单日主力净流入量），全市场 5207 只排序取首尾各 10
  2. 国家队 27 只持仓股资金流：腾讯自选股 MCP 个股资金流接口 data_fund_flow
     批量查询 27 只，取 MainNetFlow（主力净流入，单位元）

【重要说明 —— 自动化限制】
  本项目原有 collect_data.py 走的是 Python 直连腾讯财经行情接口（qt.gtimg.cn）。
  但资金流类接口的直连通道已实测不可用：
    - 腾讯 qt.gtimg.cn/q=ff_xxx  -> 返回 v_pv_none_match（接口下线）
    - 新浪 MoneyFlow.ssl_qsfx_*  -> {"__ERROR":1,"__ERRORMSG":"Input error"}
    - 同花顺 data.10jqka.com.cn  -> 404 不可用
    - 东方财富 push2.eastmoney.com -> 沙箱环境被拦截
  因此本脚本的资金流数据由 MCP 会话内采集后固化写入，执行本脚本完成合并/同步。
  脚本内每个数字都来自接口原始返回（单位已换算为"亿元"），不做任何推测填充。

【用法】
  python3 update_fund_flow.py
  执行后：更新 data.json -> 同步 dashboard.html 内嵌快照 -> 生成通达信 .blk 自选股文件
"""

import os, sys, json, re
from datetime import datetime

# ============================================================
# 2026-09-04 收盘真实数据（腾讯自选股 MCP 采集）
# 单位统一换算为「亿元」，保留 2 位小数
# ============================================================
TRADE_DATE = "2026-09-04"
COLLECT_TIME = "2026-09-05 18:40"
TOTAL_STOCKS_SCANNED = 5207

# 全市场主力净流入 TOP10（MainNetIn，原单位万元 -> 亿）
MARKET_TOP_IN = [
    {"code": "600150", "name": "中国船舶", "mkt": "sh", "net_yi": 20.65},
    {"code": "002354", "name": "天娱数科", "mkt": "sz", "net_yi": 15.84},
    {"code": "300058", "name": "蓝色光标", "mkt": "sz", "net_yi": 10.49},
    {"code": "603228", "name": "景旺电子", "mkt": "sh", "net_yi": 9.68},
    {"code": "300750", "name": "宁德时代", "mkt": "sz", "net_yi": 8.94},
    {"code": "000592", "name": "平潭发展", "mkt": "sz", "net_yi": 8.49},
    {"code": "301171", "name": "易点天下", "mkt": "sz", "net_yi": 8.12},
    {"code": "002472", "name": "双环传动", "mkt": "sz", "net_yi": 8.04},
    {"code": "000560", "name": "我爱我家", "mkt": "sz", "net_yi": 7.16},
    {"code": "300468", "name": "四方精创", "mkt": "sz", "net_yi": 6.97},
]

# 全市场主力净流出 TOP10（MainNetIn 为负，原单位万元 -> 亿）
MARKET_TOP_OUT = [
    {"code": "603986", "name": "兆易创新", "mkt": "sh", "net_yi": -19.02},
    {"code": "000977", "name": "浪潮信息", "mkt": "sz", "net_yi": -18.26},
    {"code": "600584", "name": "长电科技", "mkt": "sh", "net_yi": -14.37},
    {"code": "600176", "name": "中国巨石", "mkt": "sh", "net_yi": -12.93},
    {"code": "000938", "name": "紫光股份", "mkt": "sz", "net_yi": -12.90},
    {"code": "600487", "name": "亨通光电", "mkt": "sh", "net_yi": -12.17},
    {"code": "300604", "name": "长川科技", "mkt": "sz", "net_yi": -10.07},
    {"code": "000725", "name": "京东方Ａ", "mkt": "sz", "net_yi": -9.98},
    {"code": "002475", "name": "立讯精密", "mkt": "sz", "net_yi": -9.55},
    {"code": "002428", "name": "云南锗业", "mkt": "sz", "net_yi": -8.69},
]

# 国家队 27 只持仓股主力资金流（MainNetFlow，原单位元 -> 亿）
# rank = 全市场主力净流入排名（越小越靠前）; net_5d_yi = 近5日合计主力净流入(亿)
TEAM_HOLDINGS_FLOW = [
    {"code": "000858", "name": "五粮液",   "mkt": "sz", "net_yi": 4.11, "net_5d_yi": -3.51, "rank": 20},
    {"code": "600887", "name": "伊利股份", "mkt": "sh", "net_yi": 1.44, "net_5d_yi": 0.63,  "rank": 63},
    {"code": "000568", "name": "泸州老窖", "mkt": "sz", "net_yi": 0.80, "net_5d_yi": -1.82, "rank": 128},
    {"code": "000625", "name": "长安汽车", "mkt": "sz", "net_yi": 0.62, "net_5d_yi": -0.69, "rank": 177},
    {"code": "600104", "name": "上汽集团", "mkt": "sh", "net_yi": 0.55, "net_5d_yi": 0.79,  "rank": 202},
    {"code": "601668", "name": "中国建筑", "mkt": "sh", "net_yi": 0.46, "net_5d_yi": -0.49, "rank": 243},
    {"code": "600028", "name": "中国石化", "mkt": "sh", "net_yi": 0.44, "net_5d_yi": 2.57,  "rank": 256},
    {"code": "601318", "name": "中国平安", "mkt": "sh", "net_yi": 0.33, "net_5d_yi": 7.77,  "rank": 319},
    {"code": "601800", "name": "中国交建", "mkt": "sh", "net_yi": 0.18, "net_5d_yi": 0.00,  "rank": 507},
    {"code": "601288", "name": "农业银行", "mkt": "sh", "net_yi": 0.16, "net_5d_yi": 6.14,  "rank": 555},
    {"code": "000895", "name": "双汇发展", "mkt": "sz", "net_yi": 0.11, "net_5d_yi": 0.07,  "rank": 714},
    {"code": "601006", "name": "大秦铁路", "mkt": "sh", "net_yi": 0.08, "net_5d_yi": 1.14,  "rank": 851},
    {"code": "601390", "name": "中国中铁", "mkt": "sh", "net_yi": 0.05, "net_5d_yi": -0.66, "rank": 1091},
    {"code": "601398", "name": "工商银行", "mkt": "sh", "net_yi": 0.04, "net_5d_yi": 1.88,  "rank": 1177},
    {"code": "601899", "name": "紫金矿业", "mkt": "sh", "net_yi": 0.03, "net_5d_yi": -21.49,"rank": 1337},
    {"code": "000538", "name": "云南白药", "mkt": "sz", "net_yi": -0.02,"net_5d_yi": 0.52,  "rank": 3189},
    {"code": "000002", "name": "万科A",    "mkt": "sz", "net_yi": -0.10,"net_5d_yi": 0.71,  "rank": 4365},
    {"code": "601088", "name": "中国神华", "mkt": "sh", "net_yi": -0.13,"net_5d_yi": -0.75, "rank": 4557},
    {"code": "601857", "name": "中国石油", "mkt": "sh", "net_yi": -0.13,"net_5d_yi": -2.08, "rank": 4590},
    {"code": "601601", "name": "中国太保", "mkt": "sh", "net_yi": -0.14,"net_5d_yi": 2.65,  "rank": 4596},
    {"code": "601939", "name": "建设银行", "mkt": "sh", "net_yi": -0.38,"net_5d_yi": 0.59,  "rank": 5091},
    {"code": "601988", "name": "中国银行", "mkt": "sh", "net_yi": -0.44,"net_5d_yi": -4.34, "rank": 5139},
    {"code": "601328", "name": "交通银行", "mkt": "sh", "net_yi": -2.00,"net_5d_yi": -1.04, "rank": 5455},
    {"code": "688981", "name": "中芯国际", "mkt": "sh", "net_yi": -2.54,"net_5d_yi": -6.33, "rank": 5478},
    {"code": "600030", "name": "中信证券", "mkt": "sh", "net_yi": -0.68,"net_5d_yi": 3.66,  "rank": 5272},
    {"code": "600048", "name": "保利发展", "mkt": "sh", "net_yi": -0.64,"net_5d_yi": 0.01,  "rank": 5256},
    {"code": "601628", "name": "中国人寿", "mkt": "sh", "net_yi": -0.82,"net_5d_yi": -0.56, "rank": 5318},
]


def build_section():
    """组装写入 data.json 的 main_force_flow 节点"""
    team = sorted(TEAM_HOLDINGS_FLOW, key=lambda x: -x["net_yi"])
    in_sum = sum(x["net_yi"] for x in MARKET_TOP_IN)
    out_sum = sum(x["net_yi"] for x in MARKET_TOP_OUT)
    team_in_cnt = len([x for x in team if x["net_yi"] > 0])
    team_sum = sum(x["net_yi"] for x in team)
    return {
        "trade_date": TRADE_DATE,
        "collect_time": COLLECT_TIME,
        "source": "腾讯自选股 MCP（cap_main_net 排行 + data_fund_flow 个股资金流）",
        "source_note": "全市场 %d 只排序取首尾各10；国家队27只逐只查询。资金流直连接口(腾讯ff_/新浪MoneyFlow/同花顺/东财)在沙箱均不可用，数据由 MCP 会话采集后固化。" % TOTAL_STOCKS_SCANNED,
        "total_scanned": TOTAL_STOCKS_SCANNED,
        "unit": "亿元",
        "market_top_in": MARKET_TOP_IN,
        "market_top_out": MARKET_TOP_OUT,
        "team_holdings": team,
        "stats": {
            "top_in_sum_yi": round(in_sum, 2),
            "top_out_sum_yi": round(out_sum, 2),
            "team_net_sum_yi": round(team_sum, 2),
            "team_in_count": team_in_cnt,
            "team_out_count": len(team) - team_in_cnt,
        },
    }


def merge_data_json(section):
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, "data.json")
    if not os.path.exists(path):
        print("  ❌ data.json 不存在，请先运行 collect_data.py", file=sys.stderr)
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["main_force_flow"] = section
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ data.json 已合并 main_force_flow 节点")
    return data


def sync_dashboard(data):
    """把最新数据同步进 dashboard.html 的内嵌 JSON 快照（与 collect_data.py 同逻辑）"""
    base = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base, "dashboard.html")
    if not os.path.exists(html_path):
        print("  ⚠️ dashboard.html 不存在，跳过同步", file=sys.stderr)
        return False
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    pattern = r'(<script type="application/json" id="embedded-data">)([\s\S]*?)(</script>)'
    new_html, n = re.subn(pattern, lambda m: m.group(1) + data_json + m.group(3), html, count=1)
    if n == 0:
        print("  ⚠️ 未找到内嵌数据标签，跳过同步", file=sys.stderr)
        return False
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)
    print(f"  ✅ dashboard.html 内嵌快照已同步 ({len(new_html)//1024}KB)")
    return True


def to_tdx_code(item):
    """通达信自选股 .blk 格式：市场位(1=沪 0=深) + 6位代码"""
    return ("1" if item["mkt"] == "sh" else "0") + item["code"]


def write_tdx_blk():
    """生成通达信自定义板块/自选股 .blk 文件（可直接在通达信导入）"""
    base = os.path.dirname(os.path.abspath(__file__))

    # 文件1：主力资金监控（流入TOP10 + 流出TOP10）
    flow_items = MARKET_TOP_IN + MARKET_TOP_OUT
    p1 = os.path.join(base, "tdx_主力资金监控.blk")
    with open(p1, "w", encoding="gbk", errors="ignore") as f:
        for it in flow_items:
            f.write(to_tdx_code(it) + "\n")

    # 文件2：国家队持仓 27 只
    p2 = os.path.join(base, "tdx_国家队持仓.blk")
    with open(p2, "w", encoding="gbk", errors="ignore") as f:
        for it in TEAM_HOLDINGS_FLOW:
            f.write(to_tdx_code(it) + "\n")

    print(f"  ✅ 已生成通达信自选股文件（各 {len(flow_items)}/{len(TEAM_HOLDINGS_FLOW)} 只）")
    print(f"     {os.path.basename(p1)}")
    print(f"     {os.path.basename(p2)}")
    print("     通达信导入：功能 → 定制版面/自选股 → 导入自选股 → 选择 .blk 文件")


def main():
    print("=" * 60)
    print("  主力资金流监控 · 数据更新")
    print("=" * 60)
    print(f"  交易日: {TRADE_DATE}   扫描: {TOTAL_STOCKS_SCANNED} 只")

    section = build_section()
    print(f"  净流入TOP10合计: +{section['stats']['top_in_sum_yi']}亿")
    print(f"  净流出TOP10合计: {section['stats']['top_out_sum_yi']}亿")
    print(f"  国家队27只: {section['stats']['team_in_count']}只净流入 / {section['stats']['team_out_count']}只净流出")

    data = merge_data_json(section)
    if data is None:
        return
    sync_dashboard(data)
    write_tdx_blk()

    print("\n  ⚠️ 说明：资金流数据由 MCP 会话采集（详见脚本顶部来源注释），")
    print("     非 Python 全自动抓取；直连接口全部实测不可用。")
    print("=" * 60)


if __name__ == "__main__":
    main()
