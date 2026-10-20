# 简历草稿（只写已验证的事实；真实数据结果出来后再填数字）

## 现在就能写（工程事实，均有测试/运行证据）
- Built ExecScope, a Python execution-cost (TCA) and backtest-fidelity framework on NautilusTrader: Perold implementation-shortfall decomposition (delay / execution / opportunity / fees), multi-benchmark analysis (arrival, interval VWAP, close), and five execution algorithms (one-shot, TWAP, volume-profile VWAP, POV, Almgren-Chriss)
- Designed a paired experiment harness (many non-overlapping parent orders, identical across algorithms, seeded, with bootstrap confidence intervals and sign tests); validated its statistical power on synthetic data (detects an injected drift effect, finds nothing on pure noise)
- Engineered for reproducibility and quality: 94 unit, property-based (hypothesis) and engine-integration tests, ruff + mypy clean, GitHub Actions CI on Linux/Windows, data-quality checks, run manifests (config, data hash, versions)
- Built a depth-walking order-book reference simulator and a square-root impact model to benchmark the engine's default fill model; FastAPI + SQL result store + dashboard; a numeric-grounding verifier that rejects AI-written summaries containing numbers not in the results
- Diagnosed a failed 100,000-lot run by reconciling its notional (about $13.8B) against the engine's money limit (about $9.2B)

## 做完真实数据实验后再填（目前没有数据，不要写数字）
- E1 algorithm comparison on Binance BTCUSDT 1-minute data: [算法差异，含 95% 区间，样本数，日期范围]
- E3 default fill model understates large-order cost by [X] bp at [size] (reference depth assumption: [..])
- E2/E5 sensitivity: [哪些设置改变成本多少]
- E4: 1-minute bars misstate VWAP by [X] bp versus the trade tape

## 注意
- 测试数量以最终运行结果为准（当前 94）。
- 币安是加密货币数据，不要写成“期货市场的结论”。
- E3 的深度是模型假设，必须连同假设一起写。
