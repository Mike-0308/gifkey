# -*- coding: utf-8 -*-
# GIF 去背景 —— 容器版
# 构建：docker build -t gifkey:1.1 .
# 运行：docker compose up -d
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    GIFKEY_HOST=0.0.0.0 \
    GIFKEY_PORT=8849 \
    GIFKEY_NO_BROWSER=1 \
    GIFKEY_CONTAINER=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 依赖先装，改代码时不用重装（numpy/pillow 都是 manylinux 预编译轮子）
# 国内网络建议用镜像源，构建时传参：docker build --build-arg PIP_INDEX=https://mirrors.huaweicloud.com/repository/pypi/simple .
ARG PIP_INDEX=https://pypi.org/simple
COPY requirements.txt ./
RUN pip install --no-cache-dir -i ${PIP_INDEX} -r requirements.txt

COPY app.py keying.py ./
COPY static ./static

RUN mkdir -p /app/work /app/output

EXPOSE 8849

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8849/api/info', timeout=3)"

CMD ["python", "app.py"]
