# 真实 L2 深度基准

旧 E3 用“第一根 K 线成交量 × 25%”构造最优档深度，并假定后续每档等距增长。这个假设没有真实盘口支持。新流程直接保存 BTCUSDT 现货 L2 快照，在每个快照上按真实价格和挂单量逐档吃单，得到同一时点的订单大小—静态成本曲线。

例如卖盘为 101 元 1 单位、104 元 2 单位，买 2 单位的均价是 102.5 元，不会假定下一档一定是 102 元。可见盘口只有 3 单位时，买 10 单位只能估算前 3 单位的成本，剩下 7 单位保留未成交，整单成本为空。

## 获取与重放（PowerShell，每条单独运行）

在项目根目录运行。采集文件必须使用新文件名；默认采 6 次，响应之间至少等 5 秒。网络或 HTTP 错误直接停止，已有有效前缀保留，可离线分析；不自动重试限流或拒绝访问。

```powershell
.\.venv\Scripts\python.exe -m execscope.experiments.depth collect --out data/raw/depth-BTCUSDT-20261121.jsonl --samples 6 --interval 5 --limit 1000
```

```powershell
.\.venv\Scripts\python.exe -m execscope.experiments.depth analyse --input data/raw/depth-BTCUSDT-20261121.jsonl --out results/depth-BTCUSDT-20261121
```

输出：

- `depth_profiles.csv`：每个快照、买卖方向的实际价格、档位数量和累计深度。
- `sweeps.csv`：逐快照、方向、订单大小的均价、成交率、吃掉的档位数量。
- `summary.json`：完整成交样本的描述统计、样本数、最小成交率、时间范围、输入与实现 SHA-256、Git 版本及工作区状态。

“中间价成本”包含买卖价差和逐档吃单成本；“相对最优买卖价的成本”只描述继续吃深档位的代价。深度不足时只报告已成交部分的均价，整单成本为空。汇总只针对完整成交的样本，必须同时看 `n_complete`，不能忽略未完成的大单。

## 可以与不能校准的内容

可观测：每档实际价格与数量、买卖价差、即时可见深度、静态吃单价格。这里直接使用经验盘口，不把不规则价格阶梯强行拟合为 BookParams 的等间距形状。旧 E3 结果文件不覆盖。

仍未知：订单到达之前的撤单、隐藏流动性、真实延迟、手续费、交易后的补单速度、永久市场冲击。快照不含交易所事件时间，只保存本地 UTC 请求起止时间和 `lastUpdateId`；它不是连续订单簿回放。

当前快照不能拿去校准 2026-10-26 至 11-01 的历史实验。短时间相邻快照也不独立，所以不输出 iid bootstrap 的“95% 区间”，只描述这个采样窗口。下一阶段应积累更长的、带连续更新和成交流的同时间段数据，再验证恢复速度；永久冲击不能仅靠静态挂单量识别。

## 来源

- [Binance Market Data Only](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md)：无需 API key 的公共行情域名与 `/api/v3/depth`。
- [Binance Order book endpoint](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#order-book)：返回 `lastUpdateId`、`bids` 和 `asks`，最大 5,000 档；本流程使用 1,000 档。

原始快照与输出位于被 Git 忽略的 `data/raw/` 和 `results/`，留在本机。仅提交代码、测试与说明。
