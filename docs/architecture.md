# ExecScope 框架图

GitHub 会把下面的 mermaid 代码渲染成图。更好看的版本在交互笔记页的“框架”标签（notes/execscope-notes.html）。

## 图 1：一笔订单在引擎里怎么走

```mermaid
flowchart LR
  subgraph data[行情层]
    CSV[CSV 文件] -->|读入| W[BarDataWrangler<br/>表格行 → Bar] -->|Bar| DE[DataEngine<br/>分发行情]
  end
  DE -->|"on_bar(bar)"| S["策略 Strategy<br/>①父单拆成子单 twap.py"]
  subgraph exec[决策与执行层]
    S -->|submit_order| R[RiskEngine<br/>风控] -->|放行| E[ExecutionEngine<br/>路由订单] -->|发往交易所| M[OrderMatchingEngine<br/>模拟撮合]
    M -->|问：成交多少、什么价？| F["成交模型 FillModel<br/>②默认不滑点、不限量"]
  end
  F -->|答| O["OrderFilled 成交事件"]
  O -->|更新| P[Portfolio<br/>持仓与余额]
  O -.->|回传策略| S
  O -->|读出成交列表| T["③ tca.py / vwap.py<br/>算滑点和成本"]
  BUS[("MessageBus 消息总线 + Cache 缓存<br/>所有箭头实际上都从这里走")]
```

## 图 2：ExecScope 的流程

```mermaid
flowchart TB
  M0["M0 父单场景（雏形）"] -->|父单：方向、数量| M1["M1 拆单 twap.py（函数已写）"]
  M1 -->|子单：N 份| N["Nautilus 回测引擎（已跑通）"]
  N -->|成交列表：数量, 价格| M2["M2 TCA tca.py、vwap.py（已写，有测试）"]
  M2 -->|滑点基点、美元成本| M3["M3 实验批跑与对比（未开始）"]
  M3 -.->|改成交模型、延迟、订单大小后重跑| N
  M3 -->|对比表、图| M5["M5 看板 + M6 AI 解读（未开始）"]
```

## 三层心智模型
1. **行情层**：CSV → BarDataWrangler → DataEngine，把历史数据变成引擎认识的 Bar，按时间送给策略。
2. **决策与执行层**：策略 → 风控 → 执行引擎 → 撮合引擎 + 成交模型，决定买不买，以及成交多少、什么价。
3. **账户与分析层**：OrderFilled → Portfolio；ExecScope 从成交算 TCA。

## 你做过的事在图里的位置
| 做的事 | 对应位置 | 学到什么 |
|---|---|---|
| 跑通 example_01 | 图 1 整条链路 | 回测需要引擎、交易所、品种、数据、策略 |
| peek_bar.py | BarDataWrangler | 表格行被翻译成 Bar |
| order_strategy.py | 策略 → 风控 → 执行 → 撮合 | 下单后出现 OrderSubmitted、OrderFilled |
| 买 1 / 1000 / 10000 手 | 成交模型（②） | 默认每手多付约 1 个最小价位 |
| tca.py | ③ / M2 | 成交列表 → 滑点和成本 |
| twap.py | ① / M1 | 父单平均拆成 N 份 |
| vwap.py | M2 | 成交量加权均价 |

每做完一步，用自己的话回答：这一步在图里哪个位置？输入是什么？输出是什么？
