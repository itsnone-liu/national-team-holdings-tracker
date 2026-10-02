# 国家队持仓追踪分析系统 (V2.6)

追踪六大国家队主体持仓与宽基 ETF 动向：中央汇金、证金、社保基金、养老金、外管局（梧桐树/凤山/坤藤）、国家大基金。

## 组成
- `dashboard.html` — 单页看板（ECharts 本地渲染）
- `collect_data.py` — 持仓数据采集（腾讯 API + 季报）
- `collect_sector_flow.py` / `update_fund_flow.py` — 板块资金流更新
- `tdx_*.blk` — 通达信板块文件
- `data.json` — 数据（2026-09-06 快照）
