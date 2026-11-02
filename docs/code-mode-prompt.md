# 交给 Claude Code（VS Code 里的 code 模式）的指令

用法：用 VS Code 打开 `execscope` 文件夹，打开 Claude Code，把下面“---”之间的整段话发给它。
项目根目录的 `CLAUDE.md` 会被它自动读取（里面有规则和已验证的事实），所以这段话只需要说清任务。

---
Read CLAUDE.md, docs/guide.md and docs/roadmap-v2.md first. Then do the following in order. After each task:
run `python -m pytest`, `ruff check src tests` and `mypy`, update notes/execscope-learning-notes.md, commit and
push. Reply to me in Chinese, start every reply with a 4-line recap (why / done / doing / next), explain each
new concept in plain words, and give PowerShell commands one at a time.

Task 1 - Verify my environment on Windows.
Create/activate .venv, `pip install -e ".[backtest,service,dev]"`, run the tests. Fix anything that fails on
Windows (paths, encodings, line endings, pandas 3 behaviour). Do not change experiment logic to make tests pass.

Task 2 - Download real Binance data.
Add `src/execscope/data/download.py` (stdlib urllib only, with retries and a progress line, skipping files that
already exist) that downloads daily klines (and optionally aggTrades) zips from https://data.binance.vision for a
symbol and a date range into data/raw/, plus tests that mock the network. If the site is unreachable from my
network, say so and propose another free source instead of working around it. Then run
`python -m execscope.data.prepare klines ...` and read the data-quality report with me.

Task 3 - Run E1 to E5 on the real data (at least 5 consecutive days, >= 40 parent orders).
Save outputs under results/, ingest them into the SQLite store, and open the dashboard. For each experiment write,
in notes/results.md, only what the numbers show: sample size, date range, mean difference with 95% interval,
and an explicit statement when the interval includes zero. Walk me through each table.

Task 4 - Calibrate the reference simulator (E3) with real depth.
Binance publishes bookTicker / depth snapshots in the same data.binance.vision archive. Verify the real file
layout on a downloaded file first, update data/binance.py if my assumptions are wrong, then estimate the depth
parameters (depth_at_best, level_growth, level spacing) from real data, add a sensitivity table over plausible
parameter ranges, and rewrite the E3 conclusion with its assumptions.

Task 5 - Fit the square-root impact constant.
Use models/impact.py::fit_sqrt_impact on the cost-versus-size observations from the real-data runs, with a
bootstrap interval for Y, and compare it with the commonly quoted value of about 1.

Task 6 - Quality and delivery.
Build the Docker image and confirm /health and the dashboard work inside the container (docker compose up);
confirm GitHub Actions passes on Linux and Windows; then update notes/resume-draft.md with real numbers only and
write a one-page README results section.

Task 7 - Teach me.
For every module, ask me the three questions: where does it sit in the architecture, what is its input, what is its
output; and give me one small exercise I write myself. Do this after tasks 1-3, before moving on to task 4.

Optional later: a C++ order-book simulator that reproduces refsim/book.py exactly (exposed through pybind11),
benchmarked against the Python version; an LLM writer for explain/ that must pass the number verifier.
---
