# Futu OpenD (Docker)

The Futu OpenD Linux binary cannot be redistributed in this repository.

## Host mount (recommended)

1. Download OpenD for Linux from Futu and extract on the host.
2. In `docker-compose.yml`, mount your extract path:

```yaml
futu-opend:
    volumes:
        - /path/on/host/OpenD:/opt/futu-opend:ro
```

3. Publish API on localhost only: `127.0.0.1:11111:11111`.

## Build-time tarball (VPS)

```bash
docker build \
  --build-arg FUTU_OPEND_TARBALL=./vendor/OpenD.tar.gz \
  -f docker/Dockerfile.futu-opend \
  -t tradingai-futu-opend:local .
```

Never commit `vendor/OpenD.tar.gz`.
