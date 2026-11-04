FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY host ./host
RUN pip install --no-cache-dir . && mkdir /data && chown 65532:65532 /data
USER 65532:65532
ENTRYPOINT ["panel-service"]
CMD ["run"]
