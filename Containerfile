FROM python:3.12-slim AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels .

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    EXPERTCOMPOSE_WORKSPACE=/data
RUN groupadd --system expertcompose \
    && useradd --system --gid expertcompose --home-dir /data expertcompose \
    && mkdir -p /data \
    && chown expertcompose:expertcompose /data
COPY --from=build /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl \
    && rm -r /wheels
USER expertcompose
VOLUME ["/data"]
EXPOSE 8090
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/readyz', timeout=2).read()"]
ENTRYPOINT ["expertcompose", "--workspace", "/data"]
CMD ["api", "--host", "0.0.0.0", "--port", "8090"]
