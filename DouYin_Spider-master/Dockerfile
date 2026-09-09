FROM python:3.11-slim

# apt / pip 镜像源，可通过 build arg 覆盖（国内网络加速）
ARG APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# 将 Debian 官方源替换为镜像源（官方源在国内常挂起）
RUN set -eux; \
    for f in /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list; do \
      [ -f "$f" ] && sed -i "s|https\?://deb.debian.org|${APT_MIRROR}|g" "$f" || true; \
    done; \
    cat /etc/apt/sources.list.d/debian.sources 2>/dev/null || true

# 系统依赖：原 Dockerfile 只有 curl/gnupg/build-essential，
# 补 ffmpeg（混剪/视频处理）、中文字体（水印与报告渲染）、tzdata（定时任务时区）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    build-essential \
    ffmpeg \
    fonts-wqy-zenhei \
    tzdata \
    && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime && echo ${TZ} > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# blackboxprotobuf 1.0.1 将 protobuf 死钉在 3.10.0，与 static/*_pb2.py 的 5.27.1 gencode 冲突；
# 它仅在 dy_apis 的兜底解码分支中被惰性 import，故用 --no-deps 单独安装。
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r requirements.txt \
    && pip install --no-cache-dir -i ${PIP_INDEX_URL} --no-deps blackboxprotobuf \
    && pip install --no-cache-dir -i ${PIP_INDEX_URL} pyimagedl

COPY . .

# 运行期目录（数据/媒体/导出/日志）
RUN mkdir -p /app/datas/media_datas /app/datas/excel_datas /app/output /app/Logs

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -fsS http://127.0.0.1:5000/ -o /dev/null || exit 1

CMD ["python", "web_server.py"]
