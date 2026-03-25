# Spier & Mackay Scraper

A scraper that monitors [Spier & Mackay](https://www.spierandmackay.com/)
clearance and odds-and-ends sections for in-stock items matching your size and
fit preferences, with Discord webhook notifications.

## Features

- **Auto-discovery**: Automatically finds all clearance and sale collections
- **Category-aware filtering**: Separate fit/size preferences for pants, sport
  coats, shirts, etc.
- **Change detection**: Only notifies about new items (configurable 24h TTL)
- **Discord notifications**: Rich embeds with price, discount %, and available
  sizes
- **Rate limiting**: Respectful scraping with configurable delays
- **Container-ready**: Nix-built Docker image for Kubernetes deployment

## Quick Start

### Local Development

```bash
# Enter dev environment
nix develop

# Copy and edit config
cp config.example.yaml config.yaml

# Run with dry-run (no Discord notifications)
python -m spierscraper --dry-run --verbose

# Run for real
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." python -m spierscraper
```

### Building the Container

```bash
# Build Docker image via Nix
nix build .#docker
docker load < result

# Or use make
make docker
```

## Configuration

The scraper uses a YAML config file for filter preferences and environment
variables for secrets.

### Environment Variables

| Variable                  | Required | Description                                                          |
| ------------------------- | -------- | -------------------------------------------------------------------- |
| `DISCORD_WEBHOOK_URL`     | Yes      | Discord webhook URL for notifications                                |
| `SPIERSCRAPER_CACHE_PATH` | No       | Path for persistent cache (enables change detection across restarts) |

### Config File (config.yaml)

```yaml
# Filter configuration by garment category
# Only categories listed here will be matched - omit categories you don't want
filters:
  pants:
    fits:
      - "Contemporary"
      - "Slim"
    sizes:
      - "33"
      - "34"

  chinos:
    fits:
      - "Contemporary"
      - "Relaxed Fit"
    sizes:
      - "33"
      - "34"

  sport_coats:
    fits:
      - "Moro Cut (Regular)"
      - "Neo Cut"
    sizes:
      - "40R"
      - "40S"
      - "40L"

  suits:
    fits:
      - "Ellis Cut (Regular)"
      - "Neo Cut"
    sizes:
      - "40R"
      - "40S"

  shirts:
    fits:
      - "Slim"
      - "Contemporary"
    sizes:
      - "15.5/34"
      - "16/34"

  knitwear:
    fits: [] # Knitwear doesn't use fit names
    sizes:
      - "M"
      - "L"

# Optional settings
rate_limit_seconds: 1.5 # Delay between requests (default: 1.5)
cache_ttl_hours: 24 # How long to remember seen items (default: 24)
cache_path: "/data/cache" # Persistent cache location (default: in-memory)
```

### Available Categories

| Category       | Config Key    | Description                           |
| -------------- | ------------- | ------------------------------------- |
| Dress Trousers | `pants`       | Wool dress trousers, flannel trousers |
| Chinos         | `chinos`      | Cotton chinos and casual pants        |
| Jeans          | `pants`       | Denim jeans (categorized with pants)  |
| Sport Coats    | `sport_coats` | Blazers and sport coats               |
| Suits          | `suits`       | Full suits (jacket + trousers)        |
| Dress Shirts   | `shirts`      | Dress and business casual shirts      |
| Knitwear       | `knitwear`    | Sweaters, cardigans, knit polos       |
| Outerwear      | `outerwear`   | Coats, jackets, vests                 |

### Valid Fits by Category

#### Pants & Chinos

| Category       | Valid Fits                                          |
| -------------- | --------------------------------------------------- |
| Dress Trousers | `Slim`, `Contemporary`                              |
| Chinos         | `Extra Slim`, `Slim`, `Contemporary`, `Relaxed Fit` |
| Jeans          | `Slim`, `Contemporary`                              |

**Sizes:** `28`, `30`, `31`, `32`, `33`, `34`, `35`, `36`, `38`, `40`, `41`

#### Suits

| Valid Fits (Cuts)     |
| --------------------- |
| `Ellis Cut (Regular)` |
| `Neo Cut`             |
| `Mayfair Cut`         |
| `Moro Cut`            |
| `Rivo Cut`            |

**Sizes:** `34`-`52` with suffixes: `R` (regular), `S` (short), `L` (long)

- Regular: `34R`, `36R`, `38R`, `40R`, `42R`, `44R`, `46R`, `48R`, `50R`, `52R`
- Short: `34S`, `36S`, `38S`, `40S`, `42S`, `44S`
- Long: `38L`, `40L`, `42L`, `44L`, `46L`

#### Sport Coats

| Valid Fits (Cuts)    |
| -------------------- |
| `Moro Cut (Regular)` |
| `Neo Cut`            |
| `Slim`               |
| `Contemporary`       |
| `Relaxed`            |

**Sizes:** `34`-`48` with suffixes: `R` (regular), `S` (short), `L` (long)

- Regular: `34R`, `36R`, `38R`, `40R`, `42R`, `44R`, `46R`, `48R`
- Short: `34S`, `36S`, `38S`, `40S`, `42S`
- Long: `36L`, `38L`, `40L`, `42L`, `44L`

#### Shirts

| Valid Fits     |
| -------------- |
| `Extra Slim`   |
| `Slim`         |
| `Contemporary` |
| `Classic`      |

**Sizes:** Collar/sleeve format (e.g., `15.5/34`)

- Collar: `14.5`, `15`, `15.5`, `16`, `16.5`, `17`, `17.5`, `18`
- Sleeve: `32`, `33`, `34`, `35`, `36`, `37` (or combined: `32/33`, `34/35`,
  `36/37`)

#### Knitwear

Knitwear uses standard alpha sizing rather than fit names.

**Sizes:** `XS`, `S`, `M`, `L`, `XL`, `XXL`

#### Outerwear

Outerwear uses standard alpha sizing rather than fit names.

**Sizes:** `XS`, `S`, `M`, `L`, `XL`, `XXL` (varies by item)

---

## Container Deployment

### Docker Compose

```yaml
# docker-compose.yaml
version: "3.8"

services:
  spierscraper:
    image: ghcr.io/your-username/spierscraper:latest
    environment:
      - DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL}
    volumes:
      # Mount config file
      - ./config.yaml:/config.yaml:ro
      # Optional: persistent cache for change detection
      - scraper-cache:/data/cache
    command: ["-c", "/config.yaml"]
    # For scheduled runs, see the ofelia example below

volumes:
  scraper-cache:
```

Create a `.env` file for secrets:

```bash
# .env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your/webhook
```

Run with:

```bash
docker-compose up -d
```

For scheduled runs, you can use a separate scheduler container or cron on the
host:

```yaml
# docker-compose.yaml with ofelia scheduler
version: "3.8"

services:
  scheduler:
    image: mcuadros/ofelia:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    command: daemon --docker
    labels:
      ofelia.job-run.scraper.schedule: "@every 1h"
      ofelia.job-run.scraper.container: "spierscraper"

  spierscraper:
    image: ghcr.io/your-username/spierscraper:latest
    container_name: spierscraper
    environment:
      - DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL}
    volumes:
      - ./config.yaml:/config.yaml:ro
      - scraper-cache:/data/cache
    command: ["-c", "/config.yaml"]
    restart: "no" # Scheduler handles restarts

volumes:
  scraper-cache:
```

---

### Kubernetes

#### ConfigMap for scraper configuration

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: spierscraper-config
  namespace: default
data:
  config.yaml: |
    filters:
      pants:
        fits:
          - "Contemporary"
          - "Slim"
        sizes:
          - "33"
          - "34"
      chinos:
        fits:
          - "Contemporary"
        sizes:
          - "33"
    rate_limit_seconds: 1.5
    cache_ttl_hours: 24
    cache_path: "/data/cache"
```

#### Secret for Discord webhook

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: spierscraper-secret
  namespace: default
type: Opaque
stringData:
  DISCORD_WEBHOOK_URL: "https://discord.com/api/webhooks/your/webhook"
```

Or create via kubectl:

```bash
kubectl create secret generic spierscraper-secret \
  --from-literal=DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/your/webhook"
```

#### CronJob for scheduled execution

```yaml
# cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: spierscraper
  namespace: default
spec:
  schedule: "0 */2 * * *" # Every 2 hours
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 2
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: spierscraper
              image: ghcr.io/ianepreston/spierscraper:latest
              args: ["--config", "/config/config.yaml"]
              env:
                - name: DISCORD_WEBHOOK_URL
                  valueFrom:
                    secretKeyRef:
                      name: spierscraper-secret
                      key: DISCORD_WEBHOOK_URL
              volumeMounts:
                - name: config
                  mountPath: /config
                  readOnly: true
                - name: cache
                  mountPath: /data/cache
              resources:
                requests:
                  memory: "64Mi"
                  cpu: "50m"
                limits:
                  memory: "128Mi"
                  cpu: "200m"
          volumes:
            - name: config
              configMap:
                name: spierscraper-config
            - name: cache
              persistentVolumeClaim:
                claimName: spierscraper-cache
```

#### PersistentVolumeClaim for cache (optional but recommended)

```yaml
# pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: spierscraper-cache
  namespace: default
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Mi
  # storageClassName: your-storage-class  # Uncomment if needed
```

#### Deploy to Kubernetes

```bash
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f pvc.yaml
kubectl apply -f cronjob.yaml

# Trigger a manual run
kubectl create job --from=cronjob/spierscraper spierscraper-manual-$(date +%s)

# Check logs
kubectl logs -l job-name=spierscraper-manual-xxx
```

#### Helm Values (if using a generic CronJob chart)

```yaml
# values.yaml for a generic cronjob helm chart
schedule: "0 */2 * * *"
image:
  repository: ghcr.io/your-username/spierscraper
  tag: latest

args: ["-c", "/config/config.yaml"]

env:
  - name: DISCORD_WEBHOOK_URL
    valueFrom:
      secretKeyRef:
        name: spierscraper-secret
        key: DISCORD_WEBHOOK_URL

volumes:
  - name: config
    configMap:
      name: spierscraper-config
  - name: cache
    persistentVolumeClaim:
      claimName: spierscraper-cache

volumeMounts:
  - name: config
    mountPath: /config
    readOnly: true
  - name: cache
    mountPath: /data/cache

resources:
  requests:
    memory: 64Mi
    cpu: 50m
  limits:
    memory: 128Mi
    cpu: 200m
```

---

## CLI Options

```
usage: spierscraper [-h] [-c CONFIG] [-v] [--dry-run] [--live]

options:
  -h, --help            show this help message and exit
  -c, --config CONFIG   Path to config file (default: config.yaml)
  -v, --verbose         Enable verbose logging
  --dry-run             Don't send notifications, just print matches
  --live                Alias for running against live site (default behavior)
```

## Development

```bash
# Enter dev shell
nix develop

# Run tests
make test

# Run linting
make lint

# Run type checking
make type-check

# Run all checks
make check

# Build Docker image
make docker
```

## License

MIT
