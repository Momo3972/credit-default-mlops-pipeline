# Monitoring (Prometheus + Grafana)

Ce projet expose des métriques HTTP via `prometheus-fastapi-instrumentator` sur `GET /metrics` et fournit un dashboard Grafana provisionné automatiquement.

## Où sont les configs ?

- Prometheus : `monitoring/prometheus/prometheus.yml`
- Grafana datasource : `monitoring/grafana/provisioning/datasources/datasource.yml`
- Grafana provider dashboards : `monitoring/grafana/provisioning/dashboards/provider.yml`
- Dashboard JSON : `monitoring/grafana/dashboards/fastapi.json`

## Vérifications rapides

### Prometheus : target UP
- UI : http://localhost:9090/targets
- Tu dois voir `credit-default-api` en **UP** (target `api:8000`)

### Grafana : dashboard chargé
- UI : http://localhost:3000
- Dashboard : **FastAPI / Credit Default - Monitoring**

## Métriques principales

Les séries utilisées par le dashboard du repo :
- `http_requests_total{job="credit-default-api", handler="..."}`
- `http_request_duration_seconds_bucket{job="credit-default-api", ...}`

## PromQL (alignés avec le dashboard)

### RPS par handler
```promql
sum by (handler) (rate(http_requests_total{job="credit-default-api"}[1m]))
```

### Latence p95 (seconds)
```promql
histogram_quantile(
  0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket{job="credit-default-api"}[5m]))
)
```

### Ratio 2xx / 4xx / 5xx sur 5 minutes

2xx :
```promql
(100 * sum(rate(http_requests_total{job="credit-default-api",status=~"2.."}[5m]))
 / clamp_min(sum(rate(http_requests_total{job="credit-default-api"}[5m])), 1e-9)) or on() vector(0)
```

4xx :
```promql
(100 * sum(rate(http_requests_total{job="credit-default-api",status=~"4.."}[5m]))
 / clamp_min(sum(rate(http_requests_total{job="credit-default-api"}[5m])), 1e-9)) or on() vector(0)
```

5xx :
```promql
(100 * sum(rate(http_requests_total{job="credit-default-api",status=~"5.."}[5m]))
 / clamp_min(sum(rate(http_requests_total{job="credit-default-api"}[5m])), 1e-9)) or on() vector(0)
```

## Générer volontairement du 5xx

L’endpoint `GET /boom` renvoie un 500 (utile pour vérifier le panneau 5xx) :

```bash
curl -i http://localhost:8000/boom
```
