# ExecScope 学习笔记

目标：两周内做出能写进简历的 ExecScope（基于 NautilusTrader 的执行质量 TCA + 回测保真度工作台，Python 为主）。
交互版笔记页：https://claude.ai/artifact/3nP52MS5LTGQVAZHnShgbj　完整规划：https://claude.ai/artifact/KSeuRgRWF2iSbehqdbxP63

## 项目地图（每次交流开头都回顾一遍）
**为什么做：** 目标岗位是量化开发实习，需要一个能写进简历、面试讲得清楚的项目。ExecScope 要回答一个问题：回测默认把大额买单按 K 线价格一次全部成交、滑点为 0，会少算多少执行成本？用 TWAP 拆单和 TCA 指标来量化。
**闭环：** 动机 → 业界方案 → 我们的设计 → 实验证明。
**已完成：** 规划；环境（venv + nautilus_trader 1.231.0）；跑通 example_01；看懂回测 7 步和 BarDataWrangler；第一笔订单（买 1 手，成交价 1.10780，手续费 0）；笔记与 GitHub 同步。
**正在做：** 放大实验——买 100000 手，验证默认滑点是否仍只有 1 个价位。已得到的第一个证据：买 1000 手（K 线成交量 205）全部成交，平均只比起始价差 0.43 基点。
**接下来：** M0 造“大额父单”场景 → M1 实现 TWAP → M2 算滑点/实施缺口并写测试。

## 工作约定
- 每次回复开头先回顾：为什么做、已完成、正在做、接下来。
- 每次交流后，把重点写入学习笔记，并同步到 GitHub（plumpuck/execscope）和 Project。
- 命令一条一条复制、粘贴、回车；如果出现 `>>`，按 Ctrl+C 退出。
- 新开 PowerShell 窗口要做四步：Set-ExecutionPolicy → cd execscope → 激活 .venv → cd 到例子文件夹。

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
- [ ] 放大实验：买 100000 手，验证“默认滑点只有 1 个最小价位”的推测 —— 第一次运行：先成交 52 手@1.10780，随后出现 Traceback（output5.txt 第 248 行），原因待查，需要看 Traceback 全文
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
- 默认成交是乐观的：买 1 手按 K 线价全部成交、滑点 0、手续费 0；ExecScope 要检验大单下这是否低估成本。
- BarDataWrangler：把 pandas 表格的每一行翻译成引擎认识的 Bar 对象（带品种、价格精度、纳秒时间戳）。引擎只处理自己的数据类型，所以不能直接收表格。类比：成绩单要先录入学籍系统规定的格式。
- 父单/子单、TWAP/VWAP/POV、到达价、滑点、实施缺口（IS，基点）、成交模型、延迟模型、L1/L2/L3、队列位置、MessageBus、随机种子、LGPL-3.0：详见交互版笔记页的概念页。

## 小测验参考答案
1. 虚拟环境：给项目单独准备的环境；不建会让软件版本互相覆盖（如这次的 s3fs、streamlit 冲突）。
2. `==`：规定必须装该版本，保证以后能复现。
3. debug-log：记现象、原因、解决办法。
4. 为什么 Total orders: 0 不算失败？（用户答：还没有下单只是测试）→ 补充：策略代码里没有下单语句，数完 9 根 K 线就是它的任务，结果符合预期。
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
