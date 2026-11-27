# signal-lab

Helm chart for **Signal Lab**, an interactive OpenTelemetry course: learners write
instrumented code in the browser, run it, and follow their traces, metrics and logs
through an OpenTelemetry Collector into real observability backends.

## What gets deployed

| Component | Kind | Notes |
|-----------|------|-------|
| `lab` | Deployment + Service (8000) | UI and API. The only component meant to be exposed (Ingress optional). |
| `runner` | Deployment + Service (8001) | Runs untrusted learner code. ClusterIP only, read-only root FS, non-root, no capabilities, no service-account token, resource limits, and a NetworkPolicy (ingress from the lab only; egress to the Collector, the shop and DNS). |
| `collector` | Deployment + Service (4317, 4318, 13133) | `otel/opentelemetry-collector-contrib`. Config = `base.yaml` + one file per enabled backend + optional `collector.extraConfig`. |
| `scenario` | one Deployment + Service per shop service | The Signal Shop: storefront, checkout, inventory, payments, loadgen. |
| `victoriametrics` | StatefulSet + Grafana Deployment | Bundled or external. Enabled by default. |
| `jaeger` | Deployment | Bundled (in-memory) or external. Enabled by default. |
| `elastic` | Elasticsearch StatefulSet, Kibana and APM Server Deployments | Bundled or external. **Disabled by default** (the bundled stack needs about 3 GiB of memory). |

The Collector config files under `files/collector/` are copies of
`deploy/collector/base.yaml` and `plugins/backends/<id>/collector.yaml`. Do not edit
them here: change the originals and run `scripts/sync-chart.sh` (CI can run
`scripts/sync-chart.sh --check`). Grafana dashboards found in
`plugins/backends/*/grafana/dashboards/*.json` are synced and provisioned the same way.

## Prerequisites

* Kubernetes 1.25+, Helm 3.10+
* A CNI that enforces NetworkPolicy (Calico, Cilium, ...) if you rely on the runner's isolation
* A default StorageClass, or `persistence.enabled=false` for the bundled backends

## Quick start

```bash
helm install signal-lab ./charts/signal-lab -n signal-lab --create-namespace
kubectl -n signal-lab port-forward svc/signal-lab-lab 8000:8000
# open http://localhost:8000
```

Backend links in the UI point at `localhost` by default. Port-forward the UIs too
(`helm status signal-lab -n signal-lab` prints the commands), or use an Ingress.

## Enable the Elastic stack

```bash
helm upgrade --install signal-lab ./charts/signal-lab -n signal-lab \
  --set backends.elastic.enabled=true
```

The bundled stack is a single-node Elasticsearch with **security disabled** (no TLS,
no authentication), plus Kibana and APM Server. It is meant for a personal lab only.
Never expose it to a network you do not trust. Tune `backends.elastic.elasticsearch.heap`
and `resources` together (heap of about half the memory limit).

## External backends

Point the lab and the Collector at backends you already run:

```yaml
# external.yaml
backends:
  victoriametrics:
    mode: external
    external:
      url: http://vmsingle.monitoring:8428              # queries
      # otlpUrl defaults to <url>/opentelemetry/v1/metrics
      grafanaUrl: http://grafana.monitoring
      grafanaPublicUrl: https://grafana.example.com
      grafanaDatasourceUid: victoriametrics
      grafanaToken: {existingSecret: grafana-token, key: token}
  jaeger:
    mode: external
    external:
      url: http://jaeger-query.tracing:16686
      publicUrl: https://jaeger.example.com
      otlpEndpoint: jaeger-collector.tracing:4317
  elastic:
    enabled: true
    mode: external
    external:
      elasticsearchUrl: https://es.example.com:443
      kibanaUrl: https://kibana.example.com
      apmServerUrl: https://apm.example.com:443
      apiKey: {existingSecret: elastic-creds, key: es-api-key}          # ELASTICSEARCH_API_KEY
      apmAuthHeader: {existingSecret: elastic-creds, key: apm-auth}     # "ApiKey ..." or "Bearer ..."
collector:
  extraConfig:            # the shipped Elastic exporter uses plaintext gRPC
    exporters:
      otlp/elastic:
        tls: {insecure: false}
```

```bash
kubectl -n signal-lab create secret generic elastic-creds \
  --from-literal=es-api-key=... --from-literal=apm-auth='ApiKey ...'
helm upgrade --install signal-lab ./charts/signal-lab -n signal-lab -f external.yaml
```

## Ingress

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    # The lab streams run output and live telemetry: do not buffer it.
    nginx.ingress.kubernetes.io/proxy-buffering: "off"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
  hosts:
    lab: lab.example.com
    grafana: grafana.example.com   # bundled Grafana
    jaeger: jaeger.example.com     # bundled Jaeger
    kibana: ""                     # bundled Kibana has no auth; leave it off unless the network is trusted
  tls:
    - secretName: signal-lab-tls
      hosts: [lab.example.com, grafana.example.com, jaeger.example.com]
```

The browser links the lab shows (`GRAFANA_PUBLIC_URL`, `JAEGER_PUBLIC_URL`,
`KIBANA_PUBLIC_URL`) follow the Ingress hosts, with `https` for hosts listed under
`tls`. Override them with `backends.victoriametrics.grafana.publicUrl`,
`backends.jaeger.publicUrl` and `backends.elastic.kibana.publicUrl`.

The bundled Grafana gives anonymous visitors the Admin role, as the compose stack
does. Set `backends.victoriametrics.grafana.anonymousAdmin=false` before putting it on
a shared Ingress.

## Customising the Collector

`collector.extraConfig` is written to `extra.yaml` and loaded last, so it can add
pipelines or override any shipped setting:

```yaml
collector:
  extraConfig:
    exporters:
      debug: {verbosity: detailed}
    service:
      pipelines:
        traces/debug: {receivers: [otlp], processors: [memory_limiter, batch], exporters: [debug]}
```

The same ConfigMap is mounted read-only into the lab pod so the UI can show the
pipeline the learner's telemetry goes through. Changing it rolls the Collector.

## Hardening the runner

The runner executes arbitrary learner code. Beyond the defaults you can:

* run it under a sandboxed runtime: `runner.runtimeClassName=gvisor` (or `kata`);
* pin it to a dedicated, tainted node pool with `runner.nodeSelector` / `runner.tolerations`;
* lower `runner.concurrency`, `runner.maxTimeout` and `runner.resources.limits`.

Kubernetes has no per-pod `pids` limit in the pod spec (compose sets `pids_limit: 256`);
the runner applies `RLIMIT_NPROC` to each run, and you can enforce a node-wide limit
with the kubelet's `podPidsLimit`.

## Testing the chart

```bash
helm lint charts/signal-lab
for f in charts/signal-lab/ci/*.yaml; do
  helm lint charts/signal-lab -f "$f"
  helm template t charts/signal-lab -f "$f" | kubeconform -strict -summary
done
```

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `global.imageRegistry` | string | `""` | Registry prefix for every image in the chart (lab, collector and bundled backends). Overrides each image's own `registry`. Useful with a pull-through mirror. |
| `global.imagePullSecrets` | list | `[]` | Pull secrets added to every pod, e.g. `[{name: regcred}]`. |
| `nameOverride` | string | `""` | Override the chart name used in resource names. |
| `fullnameOverride` | string | `""` | Override the full resource name prefix (defaults to `<release>-<chart>`). |
| `commonLabels` | object | `{}` | Labels added to every resource the chart creates. |
| `commonAnnotations` | object | `{}` | Annotations added to every resource the chart creates. |
| `image.registry` | string | `"ghcr.io"` | Image registry. Ignored when `global.imageRegistry` is set. |
| `image.repository` | string | `"heknon/signal-lab"` | Image repository. |
| `image.tag` | string | `""` | Image tag. Defaults to the chart's `appVersion`. |
| `image.digest` | string | `""` | Image digest (`sha256:...`). When set it is used instead of the tag. |
| `image.pullPolicy` | string | `"IfNotPresent"` | Image pull policy. |
| `imagePullSecrets` | list | `[]` | Pull secrets for the pods of this release (merged with `global.imagePullSecrets`). |
| `serviceAccount.create` | bool | `true` | Create a ServiceAccount shared by the chart's pods. |
| `serviceAccount.name` | string | `""` | ServiceAccount name. Defaults to the full name when `create` is true, `default` otherwise. |
| `serviceAccount.annotations` | object | `{}` | Annotations for the ServiceAccount (e.g. for workload identity). |
| `serviceAccount.automount` | bool | `false` | Mount the ServiceAccount token into pods. Nothing in Signal Lab talks to the Kubernetes API, so this is off. The runner never mounts a token, whatever this says. |
| `podSecurityContext` | object | `see values.yaml` | Pod security context for the pods that run the Signal Lab image (lab, scenario). The runner has its own, stricter settings under `runner`. |
| `securityContext` | object | `see values.yaml` | Container security context for the containers that run the Signal Lab image (lab, scenario). |
| `lab.replicaCount` | int | `1` | Number of lab replicas. The live telemetry inspector keeps state in memory, so keep this at 1 unless you add session affinity. |
| `lab.environment` | string | `"lab"` | Value of `deployment.environment.name` stamped on learner runs (`SIGNAL_LAB_ENVIRONMENT`). |
| `lab.logLevel` | string | `"INFO"` | Log level of the lab server (`SIGNAL_LAB_LOG_LEVEL`). |
| `lab.lessonPacks` | list | `[]` | Lesson packs to load (`SIGNAL_LAB_LESSON_PACKS`). Empty loads every pack in the image. |
| `lab.runs.enabled` | bool | `true` | Allow learners to run code (`SIGNAL_LAB_RUNS_ENABLED`). Set false for a read-only course. |
| `lab.runs.timeout` | int | `20` | Default timeout for a learner run, in seconds (`SIGNAL_LAB_RUN_TIMEOUT`). Capped by `runner.maxTimeout`. |
| `lab.service.type` | string | `"ClusterIP"` | Service type. |
| `lab.service.port` | int | `8000` | Service port. |
| `lab.service.annotations` | object | `{}` | Service annotations. |
| `lab.resources` | object | `see values.yaml` | Resource requests and limits. |
| `lab.extraEnv` | list | `[]` | Extra environment variables (list of EnvVar objects). |
| `lab.extraVolumes` | list | `[]` | Extra volumes for the lab pod. |
| `lab.extraVolumeMounts` | list | `[]` | Extra volume mounts for the lab container. |
| `lab.podAnnotations` | object | `{}` | Annotations for the lab pods. |
| `lab.podLabels` | object | `{}` | Labels for the lab pods. |
| `lab.nodeSelector` | object | `{}` | Node selector. |
| `lab.tolerations` | list | `[]` | Tolerations. |
| `lab.affinity` | object | `{}` | Affinity rules. |
| `runner.replicaCount` | int | `1` | Number of runner replicas. Each handles `concurrency` runs at a time. |
| `runner.maxTimeout` | int | `30` | Hard cap on a single run, in seconds (`SIGNAL_LAB_RUN_TIMEOUT` on the runner). |
| `runner.concurrency` | int | `4` | Runs executed in parallel per replica (`SIGNAL_LAB_RUNNER_CONCURRENCY`). |
| `runner.service.port` | int | `8001` | Service port. |
| `runner.service.annotations` | object | `{}` | Service annotations. |
| `runner.resources` | object | `see values.yaml` | Resource requests and limits. Keep limits: this pod runs arbitrary code. |
| `runner.tmpSizeLimit` | string | `"256Mi"` | Size limit of the writable `/tmp` emptyDir where runs get their scratch directory. |
| `runner.podSecurityContext` | object | `see values.yaml` | Pod security context. Tighten further if you like; do not loosen. |
| `runner.securityContext` | object | `see values.yaml` | Container security context. |
| `runner.networkPolicy.enabled` | bool | `true` | Create a NetworkPolicy that limits the runner to: ingress from lab pods only; egress to the Collector (4317/4318), the shop services (8080) and DNS. Requires a CNI that enforces NetworkPolicy. |
| `runner.networkPolicy.dnsTo` | list | `see values.yaml` | Peers allowed for DNS (port 53). Defaults to CoreDNS/kube-dns in any namespace. Set to `[]` to allow port 53 to any destination (e.g. with NodeLocal DNSCache). |
| `runner.networkPolicy.extraEgress` | list | `[]` | Extra egress rules (NetworkPolicyEgressRule objects), e.g. to let lessons reach a backend. |
| `runner.extraEnv` | list | `[]` | Extra environment variables (list of EnvVar objects). |
| `runner.podAnnotations` | object | `{}` | Annotations for the runner pods. |
| `runner.podLabels` | object | `{}` | Labels for the runner pods. |
| `runner.nodeSelector` | object | `{}` | Node selector. Consider a dedicated, tainted node pool for untrusted code. |
| `runner.tolerations` | list | `[]` | Tolerations. |
| `runner.affinity` | object | `{}` | Affinity rules. |
| `runner.runtimeClassName` | string | `""` | RuntimeClass for the runner (e.g. `gvisor` or `kata`) for stronger isolation. |
| `collector.image.registry` | string | `"docker.io"` | Image registry. Ignored when `global.imageRegistry` is set. |
| `collector.image.repository` | string | `"otel/opentelemetry-collector-contrib"` | Image repository. |
| `collector.image.tag` | string | `"0.115.1"` | Image tag. |
| `collector.image.digest` | string | `""` | Image digest. When set it is used instead of the tag. |
| `collector.image.pullPolicy` | string | `"IfNotPresent"` | Image pull policy. |
| `collector.replicaCount` | int | `1` | Number of Collector replicas. |
| `collector.service.type` | string | `"ClusterIP"` | Service type. |
| `collector.service.annotations` | object | `{}` | Service annotations. |
| `collector.extraConfig` | object | `{}` | Extra Collector config, merged on top of the shipped files as one more `--config`. Use it to add exporters/pipelines or tweak the shipped ones (e.g. TLS for an external backend). |
| `collector.extraEnv` | list | `[]` | Extra environment variables (list of EnvVar objects). Handy for `${env:...}` in `extraConfig`. |
| `collector.resources` | object | `see values.yaml` | Resource requests and limits. `memory_limiter` uses 80% of the memory limit. |
| `collector.podSecurityContext` | object | `see values.yaml` | Pod security context. |
| `collector.securityContext` | object | `see values.yaml` | Container security context. |
| `collector.podAnnotations` | object | `{}` | Annotations for the Collector pods. |
| `collector.podLabels` | object | `{}` | Labels for the Collector pods. |
| `collector.nodeSelector` | object | `{}` | Node selector. |
| `collector.tolerations` | list | `[]` | Tolerations. |
| `collector.affinity` | object | `{}` | Affinity rules. |
| `scenario.enabled` | bool | `true` | Deploy the Signal Shop scenario. |
| `scenario.services` | list | `see values.yaml` | One Deployment and Service per entry. `name` is the shop service id; each entry may also set `replicaCount`, `resources` and `extraEnv`. |
| `scenario.loadgen.rps` | int | `2` | Requests per second the load generator sends to the storefront (`SHOP_LOADGEN_RPS`). |
| `scenario.otel.resourceAttributes` | string | `"deployment.environment.name=lab,service.version=1.4.2"` | `OTEL_RESOURCE_ATTRIBUTES` for every shop service. |
| `scenario.otel.metricExportInterval` | int | `5000` | Metric export interval in milliseconds (`OTEL_METRIC_EXPORT_INTERVAL`). |
| `scenario.otel.disabledInstrumentations` | string | `"fastapi"` | Auto-instrumentations to skip (`OTEL_PYTHON_DISABLED_INSTRUMENTATIONS`). The shop instruments FastAPI itself, to drop the per-message ASGI send/receive spans. |
| `scenario.replicaCount` | int | `1` | Default replicas per shop service. |
| `scenario.resources` | object | `see values.yaml` | Default resources per shop service. |
| `scenario.extraEnv` | list | `[]` | Extra environment variables for every shop service (list of EnvVar objects). |
| `scenario.podAnnotations` | object | `{}` | Annotations for the shop pods. |
| `scenario.podLabels` | object | `{}` | Labels for the shop pods. |
| `scenario.nodeSelector` | object | `{}` | Node selector. |
| `scenario.tolerations` | list | `[]` | Tolerations. |
| `scenario.affinity` | object | `{}` | Affinity rules. |
| `backends.victoriametrics.enabled` | bool | `true` | Enable the VictoriaMetrics + Grafana backend. |
| `backends.victoriametrics.mode` | string | `"bundled"` | `bundled` deploys VictoriaMetrics (and Grafana); `external` uses `external.*` URLs. |
| `backends.victoriametrics.image.registry` | string | `"docker.io"` | Image registry. |
| `backends.victoriametrics.image.repository` | string | `"victoriametrics/victoria-metrics"` | Image repository. |
| `backends.victoriametrics.image.tag` | string | `"v1.106.1"` | Image tag. |
| `backends.victoriametrics.image.digest` | string | `""` | Image digest. |
| `backends.victoriametrics.image.pullPolicy` | string | `"IfNotPresent"` | Image pull policy. |
| `backends.victoriametrics.retentionPeriod` | string | `"7d"` | How long VictoriaMetrics keeps data (`-retentionPeriod`). |
| `backends.victoriametrics.extraArgs` | list | `[]` | Extra command-line flags, e.g. `["-memory.allowedPercent=40"]`. |
| `backends.victoriametrics.publicUrl` | string | `""` | Browser URL of VictoriaMetrics (VMUI links). Defaults to `http://localhost:8428` (reach it with `kubectl port-forward`); VictoriaMetrics is never put on the Ingress. |
| `backends.victoriametrics.persistence.enabled` | bool | `true` | Store data on a PersistentVolumeClaim. When false, an emptyDir is used. |
| `backends.victoriametrics.persistence.storageClass` | string | `""` | StorageClass. `""` uses the cluster default; `"-"` disables dynamic provisioning. |
| `backends.victoriametrics.persistence.accessModes` | list | `["ReadWriteOnce"]` | Access modes. |
| `backends.victoriametrics.persistence.size` | string | `"10Gi"` | Volume size. |
| `backends.victoriametrics.resources` | object | `see values.yaml` | Resource requests and limits. |
| `backends.victoriametrics.podSecurityContext` | object | `see values.yaml` | Pod security context. |
| `backends.victoriametrics.securityContext` | object | `see values.yaml` | Container security context. |
| `backends.victoriametrics.nodeSelector` | object | `{}` | Node selector. |
| `backends.victoriametrics.tolerations` | list | `[]` | Tolerations. |
| `backends.victoriametrics.affinity` | object | `{}` | Affinity rules. |
| `backends.victoriametrics.grafana.enabled` | bool | `true` | Deploy Grafana with a provisioned VictoriaMetrics datasource (bundled mode only). |
| `backends.victoriametrics.grafana.image.registry` | string | `"docker.io"` | Image registry. |
| `backends.victoriametrics.grafana.image.repository` | string | `"grafana/grafana"` | Image repository. |
| `backends.victoriametrics.grafana.image.tag` | string | `"11.4.0"` | Image tag. |
| `backends.victoriametrics.grafana.image.digest` | string | `""` | Image digest. |
| `backends.victoriametrics.grafana.image.pullPolicy` | string | `"IfNotPresent"` | Image pull policy. |
| `backends.victoriametrics.grafana.anonymousAdmin` | bool | `true` | Anonymous users are Grafana admins and the login form is hidden, as in the compose stack. Convenient for a personal lab; turn off for anything shared. |
| `backends.victoriametrics.grafana.env` | object | `{}` | Extra `GF_*` settings as a map, e.g. `{GF_SERVER_ROOT_URL: https://grafana.example.com}`. |
| `backends.victoriametrics.grafana.publicUrl` | string | `""` | Browser URL of Grafana. Defaults to the `ingress.hosts.grafana` host, else `http://localhost:3000`. |
| `backends.victoriametrics.grafana.resources` | object | `see values.yaml` | Resource requests and limits. |
| `backends.victoriametrics.grafana.podSecurityContext` | object | `see values.yaml` | Pod security context. |
| `backends.victoriametrics.grafana.securityContext` | object | `see values.yaml` | Container security context. |
| `backends.victoriametrics.grafana.nodeSelector` | object | `{}` | Node selector. |
| `backends.victoriametrics.grafana.tolerations` | list | `[]` | Tolerations. |
| `backends.victoriametrics.grafana.affinity` | object | `{}` | Affinity rules. |
| `backends.victoriametrics.external.url` | string | `""` | In-cluster URL of your VictoriaMetrics (or any Prometheus-API store), for queries. |
| `backends.victoriametrics.external.otlpUrl` | string | `""` | OTLP metrics ingest URL. Defaults to `<url>/opentelemetry/v1/metrics`. |
| `backends.victoriametrics.external.publicUrl` | string | `""` | Browser URL of VictoriaMetrics. Defaults to `url`. |
| `backends.victoriametrics.external.grafanaUrl` | string | `""` | In-cluster URL of your Grafana (also used in bundled mode when `grafana.enabled` is false). |
| `backends.victoriametrics.external.grafanaPublicUrl` | string | `""` | Browser URL of your Grafana. Defaults to `grafanaUrl`. |
| `backends.victoriametrics.external.grafanaDatasourceUid` | string | `"victoriametrics"` | UID of the Grafana datasource that points at VictoriaMetrics. |
| `backends.victoriametrics.external.grafanaToken.existingSecret` | string | `""` | Existing Secret holding a Grafana service-account token (`GRAFANA_TOKEN`). |
| `backends.victoriametrics.external.grafanaToken.key` | string | `"token"` | Key in that Secret. |
| `backends.jaeger.enabled` | bool | `true` | Enable the Jaeger backend. |
| `backends.jaeger.mode` | string | `"bundled"` | `bundled` deploys Jaeger all-in-one with in-memory storage; `external` uses `external.*`. |
| `backends.jaeger.image.registry` | string | `"docker.io"` | Image registry. |
| `backends.jaeger.image.repository` | string | `"jaegertracing/jaeger"` | Image repository. |
| `backends.jaeger.image.tag` | string | `"2.1.0"` | Image tag. |
| `backends.jaeger.image.digest` | string | `""` | Image digest. |
| `backends.jaeger.image.pullPolicy` | string | `"IfNotPresent"` | Image pull policy. |
| `backends.jaeger.publicUrl` | string | `""` | Browser URL of the Jaeger UI. Defaults to the `ingress.hosts.jaeger` host, else `http://localhost:16686`. |
| `backends.jaeger.resources` | object | `see values.yaml` | Resource requests and limits. Traces are kept in memory, so the limit caps retention. |
| `backends.jaeger.podSecurityContext` | object | `see values.yaml` | Pod security context. |
| `backends.jaeger.securityContext` | object | `see values.yaml` | Container security context. |
| `backends.jaeger.nodeSelector` | object | `{}` | Node selector. |
| `backends.jaeger.tolerations` | list | `[]` | Tolerations. |
| `backends.jaeger.affinity` | object | `{}` | Affinity rules. |
| `backends.jaeger.external.url` | string | `""` | In-cluster URL of the Jaeger query service (e.g. `http://jaeger-query.tracing:16686`). |
| `backends.jaeger.external.publicUrl` | string | `""` | Browser URL of the Jaeger UI. Defaults to `url`. |
| `backends.jaeger.external.otlpEndpoint` | string | `""` | OTLP/gRPC endpoint the Collector exports traces to, as `host:port`. |
| `backends.elastic.enabled` | bool | `false` | Enable the Elastic backend. |
| `backends.elastic.mode` | string | `"bundled"` | `bundled` deploys a single-node stack; `external` uses `external.*`. WARNING: the bundled stack runs with security DISABLED (no TLS, no auth). It is for a personal lab only. Never expose it outside the cluster. |
| `backends.elastic.version` | string | `"8.17.4"` | Elastic stack version, used as the tag for all three images unless they set their own. |
| `backends.elastic.elasticsearch.image.registry` | string | `"docker.elastic.co"` | Image registry. |
| `backends.elastic.elasticsearch.image.repository` | string | `"elasticsearch/elasticsearch"` | Image repository. |
| `backends.elastic.elasticsearch.image.tag` | string | `""` | Image tag. Defaults to `backends.elastic.version`. |
| `backends.elastic.elasticsearch.image.digest` | string | `""` | Image digest. |
| `backends.elastic.elasticsearch.image.pullPolicy` | string | `"IfNotPresent"` | Image pull policy. |
| `backends.elastic.elasticsearch.heap` | string | `"-Xms1g -Xmx1g"` | JVM heap (`ES_JAVA_OPTS`). Keep it at about half of the memory limit. |
| `backends.elastic.elasticsearch.extraEnv` | list | `[]` | Extra environment variables (list of EnvVar objects); dotted names set Elasticsearch settings. |
| `backends.elastic.elasticsearch.persistence.enabled` | bool | `true` | Store data on a PersistentVolumeClaim. When false, an emptyDir is used. |
| `backends.elastic.elasticsearch.persistence.storageClass` | string | `""` | StorageClass. `""` uses the cluster default; `"-"` disables dynamic provisioning. |
| `backends.elastic.elasticsearch.persistence.accessModes` | list | `["ReadWriteOnce"]` | Access modes. |
| `backends.elastic.elasticsearch.persistence.size` | string | `"20Gi"` | Volume size. |
| `backends.elastic.elasticsearch.resources` | object | `see values.yaml` | Resource requests and limits. |
| `backends.elastic.elasticsearch.podSecurityContext` | object | `see values.yaml` | Pod security context. |
| `backends.elastic.elasticsearch.securityContext` | object | `see values.yaml` | Container security context. |
| `backends.elastic.elasticsearch.nodeSelector` | object | `{}` | Node selector. |
| `backends.elastic.elasticsearch.tolerations` | list | `[]` | Tolerations. |
| `backends.elastic.elasticsearch.affinity` | object | `{}` | Affinity rules. |
| `backends.elastic.kibana.image.registry` | string | `"docker.elastic.co"` | Image registry. |
| `backends.elastic.kibana.image.repository` | string | `"kibana/kibana"` | Image repository. |
| `backends.elastic.kibana.image.tag` | string | `""` | Image tag. Defaults to `backends.elastic.version`. |
| `backends.elastic.kibana.image.digest` | string | `""` | Image digest. |
| `backends.elastic.kibana.image.pullPolicy` | string | `"IfNotPresent"` | Image pull policy. |
| `backends.elastic.kibana.publicUrl` | string | `""` | Browser URL of Kibana (`SERVER_PUBLICBASEURL`, `KIBANA_PUBLIC_URL`). Defaults to the `ingress.hosts.kibana` host, else `http://localhost:5601`. |
| `backends.elastic.kibana.encryptionKey` | string | `""` | Saved-objects encryption key (32+ characters). Generated once and kept across upgrades when empty. |
| `backends.elastic.kibana.existingSecret` | string | `""` | Existing Secret with the key under `encryptionKey`; overrides `encryptionKey`. |
| `backends.elastic.kibana.resources` | object | `see values.yaml` | Resource requests and limits. |
| `backends.elastic.kibana.podSecurityContext` | object | `see values.yaml` | Pod security context. |
| `backends.elastic.kibana.securityContext` | object | `see values.yaml` | Container security context. |
| `backends.elastic.kibana.nodeSelector` | object | `{}` | Node selector. |
| `backends.elastic.kibana.tolerations` | list | `[]` | Tolerations. |
| `backends.elastic.kibana.affinity` | object | `{}` | Affinity rules. |
| `backends.elastic.apmServer.image.registry` | string | `"docker.elastic.co"` | Image registry. |
| `backends.elastic.apmServer.image.repository` | string | `"apm/apm-server"` | Image repository. |
| `backends.elastic.apmServer.image.tag` | string | `""` | Image tag. Defaults to `backends.elastic.version`. |
| `backends.elastic.apmServer.image.digest` | string | `""` | Image digest. |
| `backends.elastic.apmServer.image.pullPolicy` | string | `"IfNotPresent"` | Image pull policy. |
| `backends.elastic.apmServer.resources` | object | `see values.yaml` | Resource requests and limits. |
| `backends.elastic.apmServer.podSecurityContext` | object | `see values.yaml` | Pod security context. |
| `backends.elastic.apmServer.securityContext` | object | `see values.yaml` | Container security context. |
| `backends.elastic.apmServer.nodeSelector` | object | `{}` | Node selector. |
| `backends.elastic.apmServer.tolerations` | list | `[]` | Tolerations. |
| `backends.elastic.apmServer.affinity` | object | `{}` | Affinity rules. |
| `backends.elastic.external.elasticsearchUrl` | string | `""` | URL of your Elasticsearch, e.g. `https://my-deployment.es.example.com:443`. |
| `backends.elastic.external.kibanaUrl` | string | `""` | In-cluster URL of your Kibana. |
| `backends.elastic.external.kibanaPublicUrl` | string | `""` | Browser URL of your Kibana. Defaults to `kibanaUrl`. |
| `backends.elastic.external.apmServerUrl` | string | `""` | URL of your APM Server (or Elastic managed OTLP intake). |
| `backends.elastic.external.apmOtlpEndpoint` | string | `""` | OTLP/gRPC endpoint the Collector exports to, as `host:port`. Defaults to the host:port of `apmServerUrl`. The shipped exporter uses plaintext gRPC; set TLS through `collector.extraConfig` for a TLS endpoint. |
| `backends.elastic.external.apiKey.existingSecret` | string | `""` | Existing Secret with an Elasticsearch API key the lab uses for queries (`ELASTICSEARCH_API_KEY`). |
| `backends.elastic.external.apiKey.key` | string | `"api-key"` | Key in that Secret. |
| `backends.elastic.external.apmAuthHeader.existingSecret` | string | `""` | Existing Secret with the full `Authorization` header value the Collector sends to APM, e.g. `ApiKey <base64>` or `Bearer <secret-token>` (`ELASTIC_APM_AUTH_HEADER`). |
| `backends.elastic.external.apmAuthHeader.key` | string | `"authorization"` | Key in that Secret. |
| `ingress.enabled` | bool | `false` | Create an Ingress. |
| `ingress.className` | string | `""` | IngressClass name (e.g. `nginx`, `traefik`). |
| `ingress.annotations` | object | `{}` | Ingress annotations. The lab streams run output and live telemetry (SSE/NDJSON): disable proxy buffering, e.g. `nginx.ingress.kubernetes.io/proxy-buffering: "off"`. |
| `ingress.pathType` | string | `"Prefix"` | Path type for every rule. |
| `ingress.hosts.lab` | string | `"signal-lab.local"` | Host of the lab UI. Empty creates a rule that matches any host. |
| `ingress.hosts.grafana` | string | `""` | Host of Grafana (bundled VictoriaMetrics backend). Empty leaves Grafana off the Ingress. |
| `ingress.hosts.jaeger` | string | `""` | Host of the Jaeger UI (bundled Jaeger). Empty leaves Jaeger off the Ingress. |
| `ingress.hosts.kibana` | string | `""` | Host of Kibana (bundled Elastic). Empty leaves Kibana off the Ingress. The bundled Elastic stack has no authentication: only expose it on a trusted network. |
| `ingress.tls` | list | `[]` | TLS blocks, e.g. `[{secretName: signal-lab-tls, hosts: [signal-lab.example.com]}]`. Public URLs switch to https for hosts listed here. |
