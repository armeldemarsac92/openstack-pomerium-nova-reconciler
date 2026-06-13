FROM golang:1.25.11 AS teleport-helper

WORKDIR /src/teleport-helper
COPY teleport-helper/go.mod teleport-helper/go.sum ./
RUN go mod download
COPY teleport-helper ./
RUN go build -o /out/mustelinet-teleport-helper ./cmd/mustelinet-teleport-helper

FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY --from=teleport-helper /out/mustelinet-teleport-helper /usr/local/bin/mustelinet-teleport-helper
RUN pip install --no-cache-dir .

EXPOSE 8080
ENTRYPOINT ["mustelinet-reconciler"]
CMD ["serve", "--config", "/etc/openstack-teleport-reconciler/config.yaml"]
