#!/usr/bin/env python3
"""
板块主力资金监控数据采集 —— 国家队持仓追踪分析系统

【背景 · 数据源测试结论（2026-09-05 沙箱实测）】
  当日分时(分钟级)资金流公开接口已全部下线/不可用：
    - 腾讯 qt.gtimg.cn/q=ff_* / stock.gtimg.cn/data/view/ggdx.php / web.ifzq.gtimg.cn dayzjlx  -> 下线或空
    - 新浪 MoneyFlow.ssl_qsfx_zjlrqs?daima=  -> 全量2767天历史(过重)；minjc/mrzjlr 等分时变体 -> Service not found
    - 东方财富 push2his.eastmoney.com (分钟资金流) -> 沙箱断连；同花顺 -> 404；雪球 -> 403
 因此无法还原"当日分时累计净流入曲线"。本脚本退而求其次采用真实可用的日级口径：

【数据口径（真实可追溯）】
  1. 概念板块列表：新浪 money.finance.sina.com.cn/q/view/newFLJK.php?param=class（175个概念）
  2. 每板块取成交额前 N 大成分股：新浪 Market_Center.getHQNodeData（node=板块码, sort=amount）
  3. 每只成分股最近10个交易日主力资金流：
     vip.stock.finance.sina.com.cn MoneyFlow.ssl_qsfx_lscjfb?page=1&num=10&sort=opendate&asc=0&daima=xxx
     主力净流入 = r0_net(超大单) + r1_net(大单)，单位元 -> 亿元
  4. 板块资金流 = 成分股按日求和（当日值=最新交易日主力净额合计）
  页面将如实标注：板块=成分股前N聚合估算、主力=超大单+大单口径、图为近10交易日趋势（非当日分时）。

【用法】python3 collect_sector_flow.py
"""

import os, sys, json, re, time
import urllib.request

for k in list(os.environ):
    if "proxy" in k.lower(): os.environ.pop(k, None)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
AGG_TOP_N = 10          # 每板块取成交额前10大成分股聚合
DAYS_N = 10             # 最近10个交易日
COLLECT_TIME = "2026-09-05 19:30"

# 目标板块（在新浪概念列表里真实存在；覆盖科技/新能源/消费/医药/军工/金融/游戏等热点）
TARGET_SECTORS = [
    "华为概念", "华为海思", "国产软件", "机器人概念",
    "锂电池", "光伏概念", "白酒概念", "国防军工",
    "生物疫苗", "特斯拉", "网络游戏", "互联金融",
]


def fetch(url, referer="https://finance.sina.com.cn"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
    raw = urllib.request.urlopen(req, timeout=20).read()
    return raw


def fetch_json(url, referer="https://finance.sina.com.cn"):
    raw = fetch(url, referer)
    text = raw.decode("gbk", "ignore").strip()
    if text.startswith("var "):
        m = re.search(r"= (\{.*\})", text, re.S)
        if m: text = m.group(1)
    try:
        return json.loads(text)
    except Exception:
        return None


def get_concept_map():
    """175个概念板块: name -> (code, 涨跌幅%, 成交额, 领涨symbol)"""
    url = "https://money.finance.sina.com.cn/q/view/newFLJK.php?param=class"
    raw = fetch(url).decode("gbk", "ignore")
    m = re.search(r"= (\{.*\})", raw, re.S)
    data = json.loads(m.group(1))
    out = {}
    for code, v in data.items():
        p = v.split(",")
        if len(p) < 13:
            continue
        # 实测字段: 0=code 1=name 2=成分数 3=均价 4=涨跌额 5=涨跌幅% 6=成交量 7=成交额 8=领涨symbol 12=领涨名
        out[p[1]] = {
            "code": code,
            "count": p[2],
            "chg_pct": float(p[5]),
            "amount": float(p[7]),
            "leader": p[8],
            "leader_name": p[12],
        }
    return out


def get_sector_stocks(node):
    """板块成交额前 AGG_TOP_N 成分股: [{symbol, name, amount(万), changepercent}]"""
    url = ("https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           "Market_Center.getHQNodeData?page=1&num=%d&sort=amount&asc=0&node=%s" % (AGG_TOP_N, node))
    d = fetch_json(url)
    if not isinstance(d, list):
        return []
    return d


def get_stock_flow_days(symbol):
    """个股最近10个交易日资金流（倒序，最新在前）: [{d, main(亿), netamount(亿)}]"""
    url = ("https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           "MoneyFlow.ssl_qsfx_lscjfb?page=1&num=%d&sort=opendate&asc=0&daima=%s" % (DAYS_N, symbol))
    d = fetch_json(url)
    if not isinstance(d, list):
        return []
    days = []
    for x in d:
        try:
            main = (float(x["r0_net"]) + float(x["r1_net"])) / 1e8
        except (KeyError, ValueError):
            main = 0.0
        days.append({"d": x["opendate"], "main_yi": round(main, 4)})
    return days


def main():
    print("=" * 60)
    print("  板块主力资金监控 · 数据采集")
    print("=" * 60)
    base = os.path.dirname(os.path.abspath(__file__))

    # 1. 概念列表
    cmap = get_concept_map()
    print("  新浪概念板块总数:", len(cmap))

    sectors = []
    failed_stocks = 0
    total_requests = 0
    for name in TARGET_SECTORS:
        if name not in cmap:
            print("  ⚠️ 未找到板块:", name)
            continue
        info = cmap[name]
        stocks = get_sector_stocks(info["code"])
        total_requests += 1
        if not stocks:
            print("  ⚠️ %s 成分股获取失败" % name)
            continue

        # 每只成分股资金流
        stock_flows = []
        for s in stocks:
            sym = s.get("symbol", "")
            try:
                days = get_stock_flow_days(sym)
                total_requests += 1
                if not days:
                    failed_stocks += 1
                    continue
                stock_flows.append({"symbol": sym, "name": s.get("name"), "amount": s.get("amount", 0),
                                    "chg": s.get("changepercent", 0), "days": days})
            except Exception as e:
                failed_stocks += 1
                continue
            time.sleep(0.12)

        if not stock_flows:
            continue

        # 日期轴：取覆盖股票最多的最近日期（用第一只股票的日期顺序为基准）
        date_axis = []
        # 用所有日期并集，按倒序排列后截断为最近 DAYS_N 个交易日
        all_dates = set()
        for sf in stock_flows:
            for x in sf["days"]:
                all_dates.add(x["d"])
        date_axis = sorted(all_dates, reverse=True)[:DAYS_N]
        date_axis.reverse()  # 时间正序，绘图从左到右

        # 每股 days -> dict
        per_stock = []
        for sf in stock_flows:
            dmap = {x["d"]: x["main_yi"] for x in sf["days"]}
            per_stock.append({"name": sf["name"], "symbol": sf["symbol"],
                              "amount": sf["amount"], "chg": sf["chg"], "dmap": dmap})

        # 板块按日求和
        flow_by_date = []
        for d in date_axis:
            total_main = sum(ps["dmap"].get(d, 0.0) for ps in per_stock)
            flow_by_date.append(round(total_main, 3))

        last_main = flow_by_date[-1] if flow_by_date else 0.0
        leader = info["leader_name"]
        sectors.append({
            "code": info["code"],
            "name": name,
            "stock_count": len(per_stock),
            "chg_pct": info["chg_pct"],
            "amount_yi": round(info["amount"] / 1e8, 1),
            "leader": leader,
            "days": flow_by_date,
            "last_main_yi": last_main,
        })
        print("  ✅ %s | 涨跌 %+.2f%% | 当日主力 %+.2f 亿 | 聚合%d只" %
              (name, info["chg_pct"], last_main, len(per_stock)))

    if not sectors:
        print("  ❌ 所有板块采集失败", file=sys.stderr)
        return

    # 排序：当日主力净额降序（净流入在前，与截图强度榜一致）
    sectors.sort(key=lambda x: -x["last_main_yi"])

    section = {
        "trade_date": date_axis[-1],
        "collect_time": COLLECT_TIME,
        "dates": date_axis,
        "source": "新浪财经资金流(ssl_qsfx_lscjfb) + 概念板块成分聚合",
        "agg_top_n": AGG_TOP_N,
        "main_def": "主力=超大单(r0)+大单(r1)，板块=成交额前%d成分股按日求和" % AGG_TOP_N,
        "note": "当日分时(分钟级)资金流公开接口均已下线(腾讯/新浪/东财/同花顺/雪球实测不可用)，本图为近%d交易日主力净流入趋势，最新点=最近交易日(2026-09-04)当日值" % DAYS_N,
        "failed_stocks": failed_stocks,
        "requests": total_requests,
        "sectors": sectors,
    }

    # 写入 data.json
    data_path = os.path.join(base, "data.json")
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["sector_flow"] = section
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("  ✅ data.json 已合并 sector_flow 节点（%d个板块 × %d日）" % (len(sectors), len(date_axis)))

    # 同步 dashboard 内嵌快照
    html_path = os.path.join(base, "dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    pattern = r'(<script type="application/json" id="embedded-data">)([\s\S]*?)(</script>)'
    new_html, n = re.subn(pattern, lambda m: m.group(1) + data_json + m.group(3), html, count=1)
    if n:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(new_html)
        print("  ✅ dashboard.html 内嵌快照已同步 (%dKB)" % (len(new_html) // 1024))

    print("=" * 60)
    print("  完成。交易日:", section["trade_date"], "| 失败股票:", failed_stocks)


if __name__ == "__main__":
    main()
