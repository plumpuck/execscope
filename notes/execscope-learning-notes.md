# ExecScope 学习笔记

目标：两周内做出能写进简历的 ExecScope（基于 NautilusTrader 的执行质量 TCA + 回测保真度工作台，Python 为主）。
项目总览（计划文档的浓缩版，附进度）：notes/execscope-overview.md
交互版笔记页：https://claude.ai/artifact/3nP52MS5LTGQVAZHnShgbj　完整规划：https://claude.ai/artifact/KSeuRgRWF2iSbehqdbxP63

## 项目地图（每次交流开头都回顾一遍）
**为什么做：** 目标岗位是量化开发实习，需要一个能写进简历、面试讲得清楚的项目。ExecScope 要回答一个问题：回测默认把大额买单按 K 线价格一次全部成交、滑点为 0，会少算多少执行成本？用 TWAP 拆单和 TCA 指标来量化。
**闭环：** 动机 → 业界方案 → 我们的设计 → 实验证明。
**已完成：** 规划；环境（venv + nautilus_trader 1.231.0）；跑通 example_01；看懂回测 7 步和 BarDataWrangler；第一笔订单（买 1 手，成交价 1.10780，手续费 0）；笔记与 GitHub 同步。
**正在做：** 自己写 interval_vwap（区间成交量加权均价），第一次由用户独立写函数；之后把 TWAP 拆单接进回测，和“一次买完”比较成本。已得到的证据：买 1、1000、10000 手，每手多付的钱几乎不变（约 6 美元/手，约 1 个最小价位），默认滑点有上限。
**接下来：** M0 造“大额父单”场景 → M1 实现 TWAP → M2 算滑点/实施缺口并写测试。

## 工作约定
- 每次回复开头先回顾：为什么做、已完成、正在做、接下来。
- 每次交流后，把重点写入学习笔记，并同步到 GitHub（plumpuck/execscope）和 Project。
- 命令一条一条复制、粘贴、回车；如果出现 `>>`，按 Ctrl+C 退出。
- 新开 PowerShell 窗口要做四步：Set-ExecutionPolicy → cd execscope → 激活 .venv → cd 到例子文件夹。
- VS Code 工作流：File → Open Folder 选 `C:\Users\HP\execscope`；Terminal → New Terminal，终端会自动在该文件夹里（提示符以 `execscope>` 结尾）；前面要有 `(.venv)`，没有就先运行 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`，再运行 `.\.venv\Scripts\Activate.ps1`。
- 写函数卡住时：先找项目里已有的类似写法（如 `total_quantity`、`average_price`），再做“填空”版本，最后才看完整答案。

## 框架图
交互笔记页“框架”标签有图 1（一笔订单在引擎里怎么走）和图 2（ExecScope 流程）；仓库里是 docs/architecture.md（mermaid）。三层：行情层 → 决策与执行层 → 账户与分析层。每做完一步问自己：这一步在图里哪个位置？输入是什么？输出是什么？

## 来源与许可（我们抄了 Nautilus 吗）
- 官方例子文件（run_example.py、strategy.py、CSV）：Nautilus 的 LGPL-3.0 代码，只在本机运行，没有放进我们的仓库。
- examples/ 里的 peek_bar.py、order_strategy.py：参照官方例子的写法、只用公开接口，属于“衍生”；已在文件头和 examples/README.md 写明来源和许可。run_order.py 是官方 run_example.py 的改名副本，不进仓库。
- src/ 里的 tca.py、twap.py、vwap.py：我们自己写的纯 Python，不依赖 Nautilus。TWAP、VWAP、滑点、实施缺口是行业通用概念，不属于 Nautilus。
- 简历说法：“基于 NautilusTrader 搭建”，自己的部分是 TCA 模块、拆单实验、测试和分析，不说成自己写了回测引擎。
- 文件位置：peek_bar.py、order_strategy.py、run_order.py 在 `C:\Users\HP\nautilus_src\examples\backtest\example_01_load_bars_from_custom_csv`（需要同目录的 CSV 和 strategy.py）；在 VS Code 里用 File → Add Folder to Workspace 把它加进来。

## 文件地图（C:\Users\HP\execscope，对应仓库 src/）
| 文件 | 作用 | 对应项目模块 |
|---|---|---|
| tca.py | 交易成本分析函数：average_price（平均成交价）、slippage_bps（滑点基点）、cost_usd（美元成本） | M2 TCA 引擎 |
| test_tca.py | tca.py 的“判卷老师”，用回测里观察到的数字（52+948、52+9948）检查结果 | E1 正确性 |
| twap.py | twap_schedule：把父单平均拆成 N 份，余数分给前几份 | M1 执行算法 |
| test_twap.py | twap.py 的单元测试 | E1 正确性 |
| vwap.py | interval_vwap：一段时间内成交量加权均价（用户自己写） | M2 相对区间 VWAP |
| test_vwap.py | vwap.py 的单元测试 | E1 正确性 |
规则：`test_X.py` 检查 `X.py`；运行 `python test_X.py`，显示 OK 就是通过。纯 Python 文件不依赖 Nautilus。
其他位置：`C:\Users\HP\nautilus_src\examples\backtest\example_01_load_bars_from_custom_csv` 里放官方例子和 order_strategy.py、run_order.py、output*.txt；`C:\Users\HP\execscope\.venv` 是虚拟环境。

## 当前进度（2026-10-08）
- [x] 规划完成（项目、动机、设计、实验、读码路线、日程）
- [x] 公共环境已清理（用户目录 10 个包已卸载，Anaconda 原版本恢复：pandas 2.2.3、fsspec 2025.3.2）
- [x] 虚拟环境 `C:\Users\HP\execscope\.venv`（Anaconda Python 3.13）里装好 nautilus_trader 1.231.0，版本检查打印 1.231.0
- [x] Git 可用（2.55.0）；已下载 develop_v1 分支到 `C:\Users\HP\nautilus_src`
- [x] 跑通 example_01：处理 9 根 K 线（Iterations 9 = Total bars processed 9），Total orders 0（DemoStrategy 只计数不下单），收益统计全是 nan（无交易），末尾正常 DISPOSED
- [x] CSV 共 10 行（1 表头 + 9 数据），与 9 根 K 线一致
- [x] 对照 run_example.py 7 步读懂输出；peek_bar.py 实验：表格行 → Bar（价格统一 5 位小数、带品种和周期、时间为纳秒整数）
- [x] 第一笔订单：OrderStrategy 在第一根 K 线买 1 手 → Total orders 1，Total positions 1，成交价 1.10780（等于该 K 线收盘价），commission 0，TAKER
- [x] 大单实验：买 1000 手（第一根 K 线成交量 205）→ 1 个订单、2 笔成交：52 手@1.10780 + 948 手@1.10785，手续费 0，平均价 1.1078474，约 0.43 基点；没有被成交量 205 限制
- [x] 放大实验：买 10000 手 → 52 手@1.10780 + 9948 手@1.10785，平均价 1.10784974，约 0.45 基点，总成本约 62,175 美元（约 6.2 美元/手）；与 1000 手（约 5.9 美元/手）几乎相同 → 推测成立：默认滑点有上限（约 1 个最小价位）
- [x] TCA 函数和单元测试（src/tca.py、src/test_tca.py）：用户已运行，4 个测试全部 OK
- [x] TWAP 拆单函数和测试（src/twap.py、src/test_twap.py）：用户已运行，5 个测试全部 OK
- [x] 安装 VS Code（用户想锻炼编程能力，之后在 VS Code 里写代码；教学方式改为“我给测试，你自己写”）
- [x] 自己写 interval_vwap（src/vwap.py）：用户已运行，5 个测试全部 OK
- [ ] 建 `debug-log.md`

## 每次新开 PowerShell 的固定动作
1. `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
2. `.\.venv\Scripts\Activate.ps1`，看到 `(.venv)` 再继续。命令一条一条粘贴。

## 关键概念
- 虚拟环境：项目专属小房间，避免包版本互相覆盖。
- `==1.231.0`：锁定版本，保证可复现。
- PATH：`python` 可能指向 Windows 占位入口（你的电脑上就是；Get-Command 显示路径在 Microsoft\Wi...，被截断，推测为 WindowsApps）。
- 执行策略：Windows 默认不允许运行脚本；`-Scope Process` 只放行当前窗口。
- 工作目录与相对路径：脚本里的相对路径只在脚本所在文件夹有效。
- git clone / 分支：`--branch develop_v1` 让示例代码与已装 v1 版本对应。
- 策略生命周期：on_start（subscribe_bars 订阅）→ 每根 K 线 on_bar → on_stop。不订阅收不到数据，不下单就没有订单。
- 回测时间 vs 真实时间：日志里 2024-01-01T23:09 是数据时间，2026-10-07 是真实运行时间。
- nan：没有已平仓交易时，夏普等指标算不出，不是错误。
- 回测 7 步（大白话）：像办一场模拟比赛。1 建引擎＝搭场地；2 add_venue＝开模拟交易所并给账户放 100 万美元（NETTING＝同品种买卖合并成净仓位，杠杆 1＝不借钱）；3 add_instrument＝选品种（2024 年 3 月到期欧元兑美元期货）；4 加数据（4a 读 CSV、4b 整理表格、4c 声明 K 线类型、4d Wrangler 转成 Bar、4e add_data）；5 add_strategy＝请策略上场；6 engine.run＝按时间顺序播放数据；7 dispose＝收场。ExecScope 主要改第 4、5 步，成交模型在第 2 步附近加。
- 订单的一生：submit_order → OrderSubmitted → OrderMatchingEngine 撮合 → OrderFilled（含 last_qty、last_px、commission、liquidity_side=TAKER）。
- 大单默认成交（观察+源码）：买 1000 手，K 线成交量 205 → 52 手@1.10780 + 948 手@1.10785。源码（develop_v1，matching_engine/engine.rs）：BarTickSizes::from_volume 把成交量分成 开/高/低 各 205/4=51、收 205-153=52；用完 L1 量后，“slip remainder by a single price increment”，剩余部分按最后成交价加 1 个最小价位成交。推测：订单再大也只多滑 1 个价位（待放大实验验证）。
- 合约乘数与名义金额：名义金额 = 手数 × 价格 × 合约乘数。本例欧元期货乘数 125,000（由报错数据反推）：1 手约 13.8 万美元，1000 手约 1.38 亿美元，100000 手约 138 亿美元，超过 Money 上限约 92.2 亿会抛 ValueError。
- 放大实验结论：手数增大 10 倍，每手成本几乎不变（1000 手约 5.9 美元/手，10000 手约 6.2 美元/手，1 个最小价位约 6.25 美元/手）。真实市场里大单通常把价格推得更远，所以默认回测可能低估大单成本（需用后续实验和文献继续检验）。
- K 线（Bar）：把一段时间的价格压成开、高、低、收 + 成交量。1 分钟 K 线丢掉了分钟内部的先后顺序，引擎要假设价格走法（开→高→低→收）。例子里第一根：开 1.1076、高 1.10785、低 1.1076、收 1.1078、量 205。
- CSV 数据来源：交易所（如 CME）、数据商（Bloomberg、LSEG、Databento，要订阅，协议通常限制转发）、免费来源（Yahoo Finance、Binance 公开数据）；本项目用 Nautilus 自带样例，不需订阅。Bloomberg 终端除数据外还有新闻、分析、聊天、下单执行；据我所知有交易成本分析功能（待核实）。有些高校图书馆或商学院有终端，视学校而定。
- 策略 vs 执行算法：策略（alpha）决定买什么、何时买，来自研究和回测（如均线交叉）；执行算法（TWAP/VWAP/POV）决定一笔已定的大单怎么买；ExecScope 做执行 + 事后 TCA，不做预测涨跌。
- 真实交易流程：研究想法 → 投资决策 → 订单管理（OMS）→ 执行（EMS 与算法）→ 成交 → 清算结算 → 事后分析（TCA）；ExecScope 做“执行”里的算法选择和“事后分析”；行情数据贯穿全程。
- BarDataWrangler 原理：对每一行，按品种精度生成 Price/Quantity，时间转成纳秒整数，与 BarType 一起装成 Bar；引擎内部用整数和固定精度避免浮点误差。
- DataEngine 学习深度：用得上 / 讲得清 / 改得动 三档；ExecScope 里策略、风控与执行引擎、撮合引擎与成交模型、Portfolio 要讲得清；DataEngine 用得上即可。
- 回放：回测把历史数据按时间顺序一根根回放。循环：拨模拟时钟到这根 K 线时间 → 调用策略 on_bar(bar) → 策略可能下单 → 撮合引擎用这根 K 线的价格尝试成交 → 下一根。不等真实时间；引擎保证策略不会偷看未来。日志 Iterations: 9 = 循环 9 次；默认下单和成交同一时刻（延迟为 0），是乐观假设，实验 E2 检验。
- 6EH4：CME 欧元期货，6E=欧元兑美元，H=3 月，4=2024 年。“9 根 K 线、1 个品种”＝2024-01-01 23:01 到 23:09 共 9 分钟的数据，只有这一个品种；是最小演示数据，正式实验（M0）要换更长、更多的数据。
- 分工：预测涨跌是基金经理的事；ExecScope 做执行（让下单成本尽量低）和事后分析（实际花了多少）。用户答对了“为什么不做预测策略”。
- on_bar：引擎每回放完一根 K 线就“回调”策略的 on_bar(bar)，就像门铃响了你去开门；策略所有决定（看价格、下单）都写在里面。TWAP = 每根 K 线下一小笔，共 9 笔。
- 为什么每个文件配一个 test：函数一多，改一处可能悄悄弄坏另一处；test 是自动检查答案，改完跑一遍就知道对不对。成本计算错了，后面所有实验结论都不可信。
- 只有 TWAP 是否单薄：TWAP 是对照基线。计划里还有 VWAP/POV 和一次性下单做对比，实验 E1–E3 才有意义；先把一条完整链路跑通，再加算法。
- TwapStrategy 的功能：父单（买多少、买不买）由基金经理给定；它只决定“怎么分时间买”：10000 手拆成 9 份，每根 K 线买一份。on_bar 的“决策”不看价格，只看“现在是第几根”，按时间表取数量——这正是 TWAP 的特点：简单、可预测。VWAP 会按历史成交量分布分配，POV 会跟随实时成交量，IS 会盯到达价，这些才会用到 bar 里的内容。
- K 线周期：没有唯一标准。研究策略常用 1 分钟、5 分钟、日线；执行/TCA 在真实机构里用逐笔（tick）或盘口数据，因为成交发生在秒级。1 分钟 K 线较粗（一分钟内的路径是引擎假设的），适合学习和小时级的 TWAP/VWAP，粗糙之处作为局限写进实验报告。
- 变量 i 与 qty（twap_strategy）：i = 这是计划表里的第几格（下标，从 0 数）；qty = 这一格里写的数量。self.bars_processed 从 1 数，列表下标从 0 数，所以 i = bars_processed - 1；qty = self.plan[i]。类比：计划表是一排 9 个格子，i 是“现在翻到第几格”，qty 是“格子里写的数字”。
- twap.py 与 twap_strategy.py：前者只算数（时间表，纯 Python，有测试），后者是照表执行的人（在引擎里下单，依赖 Nautilus）。
- 单元测试：用已知答案（我们观察到的成交数据）检查函数；改代码后重新运行就知道有没有改坏。
- 默认成交是乐观的：买 1 手按 K 线价全部成交、滑点 0、手续费 0；ExecScope 要检验大单下这是否低估成本。
- BarDataWrangler：把 pandas 表格的每一行翻译成引擎认识的 Bar 对象（带品种、价格精度、纳秒时间戳）。引擎只处理自己的数据类型，所以不能直接收表格。类比：成绩单要先录入学籍系统规定的格式。
- 父单/子单、TWAP/VWAP/POV、到达价、滑点、实施缺口（IS，基点）、成交模型、延迟模型、L1/L2/L3、队列位置、MessageBus、随机种子、LGPL-3.0：详见交互版笔记页的概念页。

## 小测验参考答案
1. 虚拟环境：给项目单独准备的环境；不建会让软件版本互相覆盖（如这次的 s3fs、streamlit 冲突）。
2. `==`：规定必须装该版本，保证以后能复现。
3. debug-log：记现象、原因、解决办法。
4. 为什么 Total orders: 0 不算失败？（用户答：还没有下单只是测试）→ 补充：策略代码里没有下单语句，数完 9 根 K 线就是它的任务，结果符合预期。
6. slippage_bps 衡量什么、为什么拿平均成交价和起始价比？10 拆 3 为什么是 [4,3,3]？（用户答：不太清楚）→ 见概念：滑点基点＝平均多付了起始价的万分之几（起始价是“瞬间买完、价格不动”的参照；分多笔成交要用数量加权平均价；基点便于跨品种比较）；拆分各份之和必须等于父单，10÷3＝3 余 1，余数给前面的份。
5. BarDataWrangler 做什么、为什么不能直接给表格？（用户答：不知道）→ 见上方概念；做完 peek_bar 后用户复述：“它只看得懂 Bar，不懂表格”（对；补充：是转换，不是建立数据）。

## 踩坑日志
| # | 现象 | 原因 | 解决 | 状态 |
|---|---|---|---|---|
| 1 | python --version 无输出，venv 未建成 | python 是占位入口 | 用 Anaconda 完整路径建 venv | 已解决 |
| 2 | pip 提示 user installation | 没激活虚拟环境 | 卸载后在 venv 重装 | 已解决 |
| 3 | s3fs、streamlit 版本冲突警告 | pandas、fsspec 被覆盖 | 卸载多装的包 | 已解决 |
| 4 | import nautilus_trader 无输出 | 同 1 | 激活 venv 后重跑 | 已解决 |
| 5 | Activate.ps1 被禁止运行 | PowerShell 执行策略 | Set-ExecutionPolicy -Scope Process Bypass | 已解决 |
| 6 | 两条命令连成一行报错 | 粘贴没换行 | 一条一条粘贴 | 已解决 |
| 8 | Get-Content output.txt -Tail 40 粘贴三遍报“无法绑定参数 Tail” | 命令连成一行 | 只粘贴一次 | 已解决 |
| 9 | output.txt 里红色 NativeCommandError + Timestamp.utcnow deprecated | Python 弃用提醒写到错误输出，2>&1 后被 PowerShell 套上错误格式；不是回测失败 | 忽略；成败看有无 Traceback 和末尾 DISPOSED | 已解决 |
| 10 | 在 C:\Users\HP 里运行了 notepad order_strategy.py | 没先 cd 到例子文件夹 | 先看路径或 pwd；多出的文件无害 | 已解决 |
| 11 | 命令粘贴多遍后出现 >> 提示符 | 缺结尾引号，PowerShell 等待继续输入 | Ctrl+C，命令只粘贴一次 | 已解决 |
| 12 | 日志中文乱码 | 重定向到文件的编码与 UTF-8 不一致 | 日志先用英文 | 已解决 |
| 13 | 新开窗口后 Select-String 无输出 | 没有 (.venv)、不在例子文件夹，run_order.py 找不到，报错被存进 output3.txt | 新窗口先做四步准备 | 已解决 |
| 14 | Select-String 又被连续粘贴，出现 >> | 命令连成一行、缺结尾引号 | Ctrl+C，只粘贴一次 | 处理中 |
| 15 | 大单实验输出仍是 BUY 1、Quantity(1) | order_strategy.py 没有真正改成 make_qty(1000)（可能没保存或存错位置） | 用 Select-String 检查 make_qty 的数值，再在例子文件夹里重新修改保存 | 处理中 |
| 15 已解决 | 大单实验仍是 BUY 1 | 文件没改成功 | 重新保存后 BUY 1_000，成交 52+948 | 已解决 |
| 16 | 买 100000 手时 ValueError: invalid value greater than MONEY_MAX | 算手续费时的名义金额 13,840,923,975 超过 Money 上限 9,223,372,036（我先猜成保证金不足，猜错） | 数量降到 10000 手；以后先估算名义金额 | 已解决 |
| 17 | VS Code 报 Expected indented block（vwap.py 第 11 行） | 把整个函数粘贴到了函数里面，出现了两个 def interval_vwap | 删掉多余的 def 行，函数体保持 4 个空格缩进 | 已解决 |
| 7 | fx_ema_cross 例子可能找不到测试数据 | 推测：TEST_DATA_DIR 指向包目录旁 tests/test_data（只读源码判断，未运行） | 先用 example_01 | 待处理 |

## 决定记录
- 2026-10-07：项目以 Python 为主，C++ 订单簿降为选做。
- 2026-10-07：引擎用 PyPI 稳定版 1.231.0（v1），示例用 develop_v1 分支；规划里的读码路径来自 v2（develop 分支，commit ab02165），读码时需对应到 v1。
- 2026-10-08：笔记先用 notes 文件夹下三个 markdown（learning-notes、debug-log、decisions）；QMD（tobi/qmd，MIT，要求 Node.js 22+，首次使用自动下载三个本地模型）等笔记超过十几篇再装。
- 2026-10-08：鼠鼠实习工具（shushu-internship-tool）此前只装在我的沙箱里，不在你的 Claude 账号；已提交保存卡片，保存后才会出现在你的技能列表。保存的只有 SKILL.md，脚本和参考文档仍在 GitHub 仓库。

## 已核实事实（来源）
- 默认成交模型 prob_fill_on_limit=1.0、prob_slippage=0.0：仓库 docs/concepts/backtesting/fill-models.md
- 延迟模型目前只有 StaticLatencyModel：docs/concepts/behavioral_models.md
- 队列位置需 queue_position=True 且 trade_execution=True：docs/concepts/backtesting/trade-execution.md
- PyPI 最新稳定版 1.231.0（2026-08-02）：https://pypi.org/project/nautilus-trader/
- QMD 要求 Node.js >= 22、MIT：https://github.com/tobi/qmd 的 README 与 package.json

## 文件按功能分组（谁在做什么）
| 功能 | 文件 | 作用 | 有测试 |
|---|---|---|---|
| ① 算数工具（纯 Python） | tca.py | 平均成交价、滑点 bp、成本美元 | test_tca.py |
| ① 算数工具 | twap.py | 把总量拆成 N 份的时间表 | test_twap.py |
| ① 算数工具 | vwap.py | 区间成交量加权均价（基准价） | test_vwap.py |
| ② 策略（在引擎里下单） | twap_strategy.py | 每根 K 线按时间表下一小笔 | 靠回测验证 |
| ② 策略 | order_strategy.py | 第一根 K 线一次性买（对照组） | 靠回测验证 |
| ③ 运行脚本 | run_twap.py / run_order.py | 装配引擎：数据 + 策略 → 跑回测 | - |
| ④ 观察工具 | peek_bar.py | 看一行表格怎样变成 Bar | - |
| ⑤ 数据 | 6EH4.XCME_1min_bars.csv | 9 根 1 分钟 K 线 | - |
注：Pylance 提示 Import "strategy" could not be resolved，因为 strategy.py 在官方示例文件夹，不在 execscope 文件夹；运行时放在同一文件夹就能找到，不是错误。

## 踩坑补充
- 变量名拼写：属性名必须和 DemoStrategy 里的完全一致，是 self.bars_processed（不是 bar_count，也不是 bar_processed）。写错会报 AttributeError。VS Code 把鼠标放在红/黄波浪线上，或看终端报错的最后一行，就能看到哪个名字不存在。
- 减少复制粘贴：可以直接发截图；让我看文件时，只发出问题的那一段和报错最后几行即可。
- 不用 PowerShell 也能运行：在 VS Code 打开 .py 文件，右上角 ▶ (Run Python File) 会用已选的 .venv 解释器运行，输出在终端面板。前提：示例文件夹已加入工作区、右下角解释器选的是 .venv。注意当前工作目录可能是工作区根目录，若脚本用相对路径读 CSV 可能找不到文件。

## 决定：项目升级为机构级路线（2026-10-20，用户要求）
用户希望项目达到能让机构直接使用的水平，不必迁就当前水平。新路线见 docs/roadmap-v2.md：基准体系 + IS 分解 + 多算法 + 平方根冲击校准 + 统计检验 + 回测保真度实验 + 数据质量层 + 工程规范（配置化、可复现、CI、属性测试）+ 逐笔/L2 数据 + 服务层。分 Tier 1/2/3 交付。待用户确认数据源、可投入时间、是否做 C++。当前进度（TWAP 回测第一跑）保留，作为 Tier 1 的起点。
用户已确认：数据源=币安公开逐笔/L2；时间=先做 Tier 1，边做边定；C++ 暂缓。Tier 1 任务顺序见 docs/roadmap-v2.md。
