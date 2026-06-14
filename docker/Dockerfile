FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

EXPOSE 8080
ENTRYPOINT ["mustelinet-reconciler"]
CMD ["serve", "--config", "/etc/openstack-pomerium-nova-reconciler/config.yaml"]
