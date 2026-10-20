FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY sql ./sql
RUN pip install --no-cache-dir ".[backtest,service]"
ENV EXECSCOPE_DB=/data/execscope.db
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "execscope.service.app:app", "--host", "0.0.0.0", "--port", "8000"]
