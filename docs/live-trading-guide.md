# ETF 趋势 + 风险平价 实盘策略使用指南（盈透 IBKR）

> **先说清楚**：本代码不保证盈利，我也不是持牌投资顾问。仓库里没有任何真实回测结果——数字必须由你在自己电脑上用真实价格跑出来。
> 默认只"模拟"：不加 `--execute` 什么都不会发送；真钱需要三道独立确认。

## 1. 策略做什么（一句话版）
9 只美国 ETF（SPY 美股、EFA 发达市场、EEM 新兴、IEF 中期国债、TLT 长债、GLD 黄金、DBC 商品、VNQ 地产、UUP 美元）+ 现金 ETF（BIL）。
- **入选条件**：收盘价 > 200 日均线 **且** 过去 126 日收益 > 0（趋势向上才持有）。
- **权重**：入选者按 1/60 日波动率配比（越稳越多），单只上限 35%，多出的部分放 BIL（现金）。
- **风险目标**：组合年化波动超过 8% 就整体按比例缩小，**只减不加杠杆**。
- **频率**：每月最后几天，用当天收盘数据决策，下一个交易日执行；偏离小于 2% 不交易。
- **只做多、不借钱、不做空。** 全部为整股交易（小资金会有取整误差）。

## 2. 安装
```powershell
cd execscope
.\.venv\Scripts\Activate.ps1
pip install -e ".[live,dev]"
```
（一条一条执行。）

## 3. 下载价格并回测
```powershell
python -m execscope.live.cli fetch --out data/etf_prices.csv
python -m execscope.live.cli backtest --prices data/etf_prices.csv
```
- 价格用 yfinance 的**复权收盘价**（含分红）。免费数据可能有错，程序会提示异常（跳变、重复日期、停更）。上实盘前，抽查几个日期对照 IBKR 的行情。
- 回测含：下一交易日成交、5bp 成本 + 每笔最低 $1、整股、月度换仓。对比基准：全仓 SPY、60/40、等权。
- 输出里 **"Sharpe difference … 区间包含 0"** 的意思是：统计上看不出比基准好。这是正常且诚实的结论，不要强行解读。
- 回测只说明"这个规则在过去的数据上表现如何"，**不代表未来**。ETF 历史较短（如 DBC 2006 起），样本里只有少数几次危机。

## 4. 看今天的信号（不下单）
```powershell
python -m execscope.live.cli signal --prices data/etf_prices.csv --equity 8000
```
显示每只 ETF 的目标权重、入选/剔除原因、整股订单。若你已有持仓：`--positions SPY=3,IEF=10`。

## 5. 模拟盘（本地纸上交易，不连券商）
```powershell
python -m execscope.live.cli paper --prices data/etf_prices.csv --equity 10000 --force
```
这是演习（`--force` 忽略月末窗口）。加 `--execute` 才会在本地模拟账户里"成交"，状态保存在 `live_state/`。

## 6. 连接 IBKR 纸上账户（强烈建议先跑至少 3 个月）
1. IBKR 网站开通 **Paper Trading 账户**。
2. 打开 TWS 或 IB Gateway，用纸上账户登录；Configure → API → Settings：勾选 *Enable ActiveX and Socket Clients*，端口：TWS 纸上 **7497**，Gateway 纸上 **4002**；勾选 *Read-Only API* 先不取消（只看不下单），确认连通后再取消。
3. 试运行（仍是模拟，不发单）：
```powershell
python -m execscope.live.cli ibkr --prices data/etf_prices.csv --port 7497 --force
```
4. 确认输出的计划合理后，才加 `--execute`（会提示你输入 y 确认每批订单）。

## 7. 真钱（只有纸上账户连续运行、行为符合预期之后）
- 端口 7496（TWS 真实）/ 4001（Gateway 真实）会被识别为真钱。需要**同时**：`--i-understand-this-is-real-money`、环境变量 `EXECSCOPE_ALLOW_LIVE=1`、并手动输入 `I ACCEPT REAL MONEY RISK`。少一个都会被拒绝。
- 建议先用本金的 10–20% 跑几个月。

## 8. 每月流程
1. 月末最后几个自然日（程序有"月末窗口"，每月只允许执行一次）。
2. `fetch` 更新价格 → `signal` 看信号 → `ibkr`（先不加 `--execute`）看计划 → 没问题再 `--execute`。
3. 检查 `live_state/orders.csv`（审计日志：每次计划/成交都有记录）。

## 9. 内置安全机制
价格过期（>5 天）拒绝交易；只允许名单内 ETF；限价单偏离不超过 1%；单笔订单占比、持仓上限、最多 20 单；绝不做空；现金检查；
**回撤熔断**：账户从历史高点回撤 15% → 之后的调仓一律转为 100% 现金，并**停机**，直到你手动检查并重置（`DrawdownGuard.reset`）。
这能限制损失，但无法保证最大回撤不超过 20%（跳空、延迟、数据错误都可能让实际更差）。

## 10. 成本与现实差异
- IBKR 美股 ETF 佣金大约每股 $0.005、每单最低约 $1（Lite/Pro 方案不同，请以官网为准）；此外有买卖价差和滑点。回测按 5bp+$1 假设，**不是你的实际成本**。
- 资金 < $1 万时，整股取整会让实际权重偏离目标；TLT/IEF 等单价较高，请看 `signal` 输出的取整结果。
- 回测里下一日收盘成交；实盘用限价单（当日有效），可能不成交（程序会取消未成交单并记录）。

## 11. 税务与法律提示（非建议）
非美国居民（如香港/新加坡）持有美国 ETF 通常涉及：美国股息预扣税（常见 30%，视税收协定/表格 W-8BEN）、美国遗产税对非居民资产的敞口（门槛较低）。
UCITS/爱尔兰注册 ETF 可能更合适但本策略代码默认使用美国 ETF。请咨询税务专业人士。

## 12. 它证明不了什么
没有真实数据结果前，不要把任何收益数字写进简历或对外宣称。简历上可以写"构建了带风控与审计的 ETF 趋势/风险平价自动调仓系统，含回测与区块自助法置信区间"，数字等你真实跑出来再填。
