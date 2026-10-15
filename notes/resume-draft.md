# 简历草稿（只写已测到的事实；未做的实验留空，做完再填）

## 现在就能写（已验证）
- Built a transaction-cost analysis layer in Python (arrival-price slippage in bp, dollar cost) plus a TWAP order slicer and an interval-VWAP helper, covered by 14 unit tests checked against hand-calculated cases
- Measured NautilusTrader's default fill model on EUR/USD futures (6E): slippage stays at about one tick (0 bp for 1 lot, 0.43 bp for 1,000 lots, 0.45 bp for 10,000 lots, about $62k), i.e. the cost does not grow with order size
- Diagnosed a failed 100,000-lot run by reconciling its notional (about $13.8B) against the engine's money limit (about $9.2B), then sized all later tests by notional

## 做完实验再填（目前没有数据，不要写数字）
- Compared TWAP (9 slices) with a one-shot order on the same bars: average price / bp / dollar difference = [E1 结果]
- Benchmarked the default fill model against a square-root impact model: understates the cost of a 10,000-lot order by [E3 结果] bp
- Varied fill-model, latency and queue-position settings: [E2 结果]

## 注意
- 之前草稿里的 "implementation shortfall" 我们还没实现（tca.py 只有滑点和成本），要写就先做，否则删掉
