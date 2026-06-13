FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENTRYPOINT ["mustelinet-reconciler"]
CMD ["--config", "/etc/openstack-teleport-reconciler/config.yaml"]
