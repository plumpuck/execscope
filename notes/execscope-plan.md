# ExecScope 项目规划摘要（trading system 项目）

完整规划文档（Claude Docs）：https://claude.ai/code/artifact/95597300-caaf-4711-b7e0-224d67e12c74

- 主项目：NautilusTrader（LGPL-3.0，Rust 核心 + Python 控制层）；对照：hftbacktest（MIT）、CppTrader（MIT）
- 定位：执行算法（TWAP/VWAP/POV）TCA + 回测假设（填充模型/延迟/L1 vs L2/队列位置）敏感性 + 自写 C++17 订单簿参考模拟器 + FastAPI/Postgres + 数字受约束的 AI 解读
- 运行深度（假设）：local-full-run，两周，每天约 4 小时
- 优先级：P0 第 7 天（M0–M3 + E1–E3）；P1 第 11 天（C++ + E4/E5）；P2 第 14 天（API/看板 + AI + E6）
- 开工第一件事：锁定 Nautilus 版本（v2 rc 或 v1.231.0）并跑通 smoke test —— 规划时沙箱连不上 PyPI，未实测安装
- 简历行里的方括号必须用真实实验数字替换，没有就删
