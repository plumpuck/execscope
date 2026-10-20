# ExecScope 使用与阅读指南

这份指南回答三个问题：每个文件做什么、怎么在你的电脑上跑起来、跑出来的结果怎么读。

## 一、整体结构（从下往上读）

```
数据层      data/        读币安文件、质量检查、合成数据（只用来验证代码）
   │
计算层      algos/ models/ tca/ stats/ refsim/     纯 Python，不依赖 Nautilus，全部有测试
   │            拆单规则   冲击模型   成本指标   置信区间   订单簿参考模拟器
   │
回测层      backtest/    把计算层的规则放进 NautilusTrader 里真的"下单、成交"
   │
实验层      experiments/ 重复很多个父单，对比算法，给置信区间；E1–E5
   │
服务层      service/ sql/   把结果存进数据库，网页仪表板，HTTP 接口
   │
解读层      explain/     把数字写成人话，并核对每个数字都有来源
```

## 二、每个文件做什么

| 文件 | 作用 | 你读它时要问自己 |
|---|---|---|
| `tca/metrics.py` | 平均成交价、滑点（bp）、成本（美元） | 为什么买入和卖出符号相反？ |
| `tca/shortfall.py` | Implementation Shortfall 拆成延迟、执行、机会、费用四项 | 四项加起来为什么恰好等于总成本？ |
| `tca/benchmarks.py` | 相对到达价、区间 VWAP、收盘价的成本；参与率 | 三个基准各回答什么问题？ |
| `algos/twap.py` | 平均拆单 | 余数怎么分？ |
| `algos/vwap.py` | 区间 VWAP（成交量加权均价） | |
| `algos/schedules.py` | 按成交量分布拆单（VWAP 算法）、POV、历史成交量分布 | 为什么历史分布只能用"之前"的日子？ |
| `models/almgren_chriss.py` | 最优执行轨迹：风险厌恶越高，越前重后轻 | `kappa_t = 0` 时为什么等于 TWAP？ |
| `models/impact.py` | 平方根冲击模型：冲击 ∝ 波动率 × √(量/市场量) | 订单放大 4 倍，冲击为什么只翻倍？ |
| `stats/bootstrap.py` | 自助法置信区间、配对差、符号检验 | 为什么用"配对"？ |
| `refsim/book.py` | 订单簿参考模拟器：大单会一档一档吃掉挂单 | 为什么拆单在深度能恢复时更便宜？ |
| `data/quality.py` | 数据体检：乱序、重复、缺口、OHLC 矛盾、异常跳变 | 为什么先体检再做实验？ |
| `data/binance.py` | 读币安 klines / aggTrades / bookTicker 文件 | |
| `data/prepare.py` | 把下载的 klines 压缩包合成一个 bars CSV | |
| `data/synthetic.py` | 合成 K 线和成交流水，**只用来验证代码** | 为什么不能拿它得结论？ |
| `backtest/strategies.py` | Nautilus 策略：一次性、按计划表、POV | `on_bar` 里什么时候记录到达价？ |
| `backtest/runner.py` | 搭引擎、加数据、跑回测、算成本 | |
| `experiments/harness.py` | 多父单实验（同一批父单跑所有算法） | 为什么窗口之间不能重叠？ |
| `experiments/fidelity.py` | E3：默认成交模型是否低估大单成本 | |
| `experiments/sweeps.py` | E2/E5：换设置或换参数重复实验 | |
| `experiments/granularity.py` | E4：1 分钟 K 线隐藏了什么 | |
| `experiments/cli.py` | e1–e5 的命令行入口 | |
| `service/db.py`, `sql/` | SQLite 存储，SQL 可直接用于 PostgreSQL | |
| `service/app.py` | HTTP 接口和网页仪表板 | |
| `explain/` | 事实表、人话报告、数字核对器 | 核对器怎么抓出编造的数字？ |

## 三、在你的电脑上运行（Windows，PowerShell，一条一条来）

解压 zip，用 VS Code 打开 `execscope` 文件夹，然后在终端里：

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[backtest,service,dev]"
python -m pytest
```
应该看到 `94 passed`（有一条来自 Nautilus 的 Pandas 弃用警告，无害）。我在 Linux 上测过；Windows 上如果有测试失败，把最后几行报错截图给我。

跑合成数据的实验（只验证流程，不得结论）：
```
python -W ignore -m execscope.experiments.cli e1 --data synthetic:0
```

## 四、用真实币安数据

1. 打开 https://data.binance.vision ，进入 `spot → daily → klines → BTCUSDT → 1m`，下载连续几天的 zip（文件名形如 `BTCUSDT-1m-2024-01-02.zip`；以网页上实际显示为准）。要做 E4，再从 `aggTrades → BTCUSDT` 下载同一天的 zip。
2. 合成一个 bars 文件：
```
python -m execscope.data.prepare klines 文件1.zip 文件2.zip 文件3.zip --out data/btcusdt_1m.csv
```
它会打印数据质量报告。**先看报告再做实验。**
3. 跑实验：
```
python -W ignore -m execscope.experiments.cli e1 --data data/btcusdt_1m.csv --parents 40
python -W ignore -m execscope.experiments.cli e2 --data data/btcusdt_1m.csv
python -W ignore -m execscope.experiments.cli e3 --data data/btcusdt_1m.csv
python -W ignore -m execscope.experiments.cli e4 --trades 某天的aggTrades.zip
python -W ignore -m execscope.experiments.cli e5 --data data/btcusdt_1m.csv
```
注意：实验里的窗口需要有"前几天同一时段"的历史来做 VWAP 的成交量分布，所以至少下载 3 到 5 天的数据。

## 五、五个实验问什么、怎么读

| 实验 | 问题 | 怎么读结果 |
|---|---|---|
| E1 | 各算法比一次性下单便宜多少？ | 看"配对差"的区间：整个区间都在 0 的同一侧才算有证据；包含 0 就是没有明确差别 |
| E2 | 模拟交易所的设置（滑点概率、延迟、流动性消耗、K 线内高低点顺序）会让成本估计变多少？ | 看"相对默认的变化"；变化大说明回测结论依赖这个设置 |
| E3 | Nautilus 默认成交模型低估大单成本多少？ | 看"低估量"随订单大小的变化。**参考模拟器的深度是假设，不是真实盘口**，结论要连同假设一起写 |
| E4 | 只用 1 分钟 K 线，基准价和到达价偏差多大？ | 看 K 线 VWAP 与真实 VWAP 的差、K 线收盘与真实到达价的差 |
| E5 | 结论换订单大小、窗口长度、买卖方向还成立吗？ | 看各变体的配对差是否方向一致 |

## 六、诚信规则（面试时会被追问）

- 合成数据只用来证明代码没问题。它是随机游走，所以各算法"没有差别"才是正确结果。
- 任何写进简历的数字必须来自你自己机器上的真实数据运行，并写明数据范围、样本数量。
- 结论要带置信区间。区间包含 0 就写"没有发现显著差别"。
- 参考模拟器（E3）的深度参数是假设。要变成实证结论，需要用真实订单簿数据校准（币安的 bookTicker / 深度快照），这是下一步。
- 币安是加密货币数据，结论不能说成"期货市场的结论"。

## 七、已知局限（我没有验证过的）

- Docker 镜像和 compose 我写好了，但沙箱里没有 Docker 引擎，**没有实际构建过**。
- 币安文件的列名和时间单位按官方文档编写，并用合成文件测试；你下载第一个真实文件后，请先用 `describe()` 看一眼。
- Windows 上的运行我没有测过（GitHub Actions 的配置里包含 Windows，推送后会自动测）。
- 1 分钟 K 线下，延迟小于一分钟的设置会被量化成"下一根 K 线成交"，所以 1 秒、30 秒、60 秒的延迟在合成数据上结果相同。这是 K 线数据的局限，也是 E4 要量化的内容。
