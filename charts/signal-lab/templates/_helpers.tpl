{{/* vim: set filetype=mustache: */}}

{{/* ------------------------------------------------------------ naming */}}

{{/* Chart name. */}}
{{- define "signal-lab.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Fully qualified app name, truncated to leave room for component suffixes. */}}
{{- define "signal-lab.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 40 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 40 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 40 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/* Chart label value. */}}
{{- define "signal-lab.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Name of a component's resources.
Usage: include "signal-lab.componentName" (dict "ctx" $ "component" "lab")
*/}}
{{- define "signal-lab.componentName" -}}
{{- printf "%s-%s" (include "signal-lab.fullname" .ctx) .component | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* ------------------------------------------------------------ labels */}}

{{/* Common labels. */}}
{{- define "signal-lab.labels" -}}
helm.sh/chart: {{ include "signal-lab.chart" . }}
{{ include "signal-lab.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: signal-lab
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/* Selector labels. */}}
{{- define "signal-lab.selectorLabels" -}}
app.kubernetes.io/name: {{ include "signal-lab.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Labels for one component.
Usage: include "signal-lab.componentLabels" (dict "ctx" $ "component" "lab")
*/}}
{{- define "signal-lab.componentLabels" -}}
{{ include "signal-lab.labels" .ctx }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Selector labels for one component.
Usage: include "signal-lab.componentSelectorLabels" (dict "ctx" $ "component" "lab")
*/}}
{{- define "signal-lab.componentSelectorLabels" -}}
{{ include "signal-lab.selectorLabels" .ctx }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/* Metadata annotations shared by every resource (commonAnnotations). */}}
{{- define "signal-lab.annotations" -}}
{{- with .Values.commonAnnotations }}
annotations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Resource metadata for a component (name, labels, annotations).
Usage: include "signal-lab.metadata" (dict "ctx" $ "component" "lab" "annotations" (dict ...))
*/}}
{{- define "signal-lab.metadata" -}}
name: {{ default (include "signal-lab.componentName" .) .name }}
labels:
  {{- include "signal-lab.componentLabels" . | nindent 2 }}
  {{- with .extraLabels }}
  {{- toYaml . | nindent 2 }}
  {{- end }}
{{- $ann := merge (dict) (default (dict) .annotations) (default (dict) .ctx.Values.commonAnnotations) }}
{{- with $ann }}
annotations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/* ------------------------------------------------------------ images */}}

{{/*
Image reference. global.imageRegistry overrides image.registry; a digest wins over a tag.
Usage: include "signal-lab.image" (dict "image" .Values.image "global" .Values.global "defaultTag" .Chart.AppVersion)
*/}}
{{- define "signal-lab.image" -}}
{{- $registry := .image.registry | default "" }}
{{- if and .global .global.imageRegistry }}
{{- $registry = .global.imageRegistry }}
{{- end }}
{{- $repo := .image.repository }}
{{- if $registry }}
{{- $repo = printf "%s/%s" (trimSuffix "/" $registry) .image.repository }}
{{- end }}
{{- if .image.digest }}
{{- printf "%s@%s" $repo .image.digest }}
{{- else }}
{{- printf "%s:%s" $repo (toString (.image.tag | default .defaultTag)) }}
{{- end }}
{{- end }}

{{/* imagePullSecrets for every pod (global + chart level). */}}
{{- define "signal-lab.imagePullSecrets" -}}
{{- $secrets := concat (.Values.global.imagePullSecrets | default list) (.Values.imagePullSecrets | default list) | uniq }}
{{- with $secrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/* ServiceAccount name. */}}
{{- define "signal-lab.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "signal-lab.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Scheduling fields (nodeSelector, tolerations, affinity) of a values block.
Usage: include "signal-lab.scheduling" .Values.lab
*/}}
{{- define "signal-lab.scheduling" -}}
{{- with .nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .tolerations }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .affinity }}
affinity:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
volumeClaimTemplate storageClassName handling: "" = cluster default, "-" = none.
Usage: include "signal-lab.storageClass" .persistence
*/}}
{{- define "signal-lab.storageClass" -}}
{{- if .storageClass }}
{{- if eq "-" .storageClass }}
storageClassName: ""
{{- else }}
storageClassName: {{ .storageClass | quote }}
{{- end }}
{{- end }}
{{- end }}

{{/* ------------------------------------------------------------ backends */}}

{{/* Backend ids in a stable order. */}}
{{- define "signal-lab.backendIds" -}}
victoriametrics,jaeger,elastic
{{- end }}

{{/* Comma list of enabled backend ids (SIGNAL_LAB_BACKENDS). */}}
{{- define "signal-lab.enabledBackends" -}}
{{- $out := list }}
{{- range $id := splitList "," (include "signal-lab.backendIds" .) }}
{{- $b := index $.Values.backends $id }}
{{- if and $b $b.enabled }}
{{- $out = append $out $id }}
{{- end }}
{{- end }}
{{- join "," $out }}
{{- end }}

{{/*
"true" when a backend is enabled and bundled.
Usage: include "signal-lab.bundled" (dict "ctx" $ "id" "jaeger")
*/}}
{{- define "signal-lab.bundled" -}}
{{- $b := index .ctx.Values.backends .id }}
{{- if and $b.enabled (eq $b.mode "bundled") }}true{{ end }}
{{- end }}

{{/*
"true" when a backend is enabled in external mode.
*/}}
{{- define "signal-lab.external" -}}
{{- $b := index .ctx.Values.backends .id }}
{{- if and $b.enabled (eq $b.mode "external") }}true{{ end }}
{{- end }}

{{/* "true" when the bundled Grafana is deployed. */}}
{{- define "signal-lab.grafanaBundled" -}}
{{- if and (include "signal-lab.bundled" (dict "ctx" . "id" "victoriametrics")) .Values.backends.victoriametrics.grafana.enabled }}true{{ end }}
{{- end }}

{{/* Elastic image tag default. */}}
{{- define "signal-lab.elasticImage" -}}
{{- include "signal-lab.image" (dict "image" .image "global" .ctx.Values.global "defaultTag" .ctx.Values.backends.elastic.version) }}
{{- end }}

{{/* ------------------------------------------------------------ collector config */}}

{{/* Collector config file names in load order (base, enabled backends, extra). */}}
{{- define "signal-lab.collectorConfigFiles" -}}
{{- $files := list "base.yaml" }}
{{- range $id := splitList "," (include "signal-lab.enabledBackends" .) }}
{{- if and $id ($.Files.Get (printf "files/collector/%s.yaml" $id)) }}
{{- $files = append $files (printf "%s.yaml" $id) }}
{{- end }}
{{- end }}
{{- if .Values.collector.extraConfig }}
{{- $files = append $files "extra.yaml" }}
{{- end }}
{{- join "," $files }}
{{- end }}

{{/* Where the collector config is mounted in the Collector pod. */}}
{{- define "signal-lab.collectorConfDir" -}}/conf{{- end }}
{{/* Where the same config is mounted (read-only) in the lab pod, for the pipeline view. */}}
{{- define "signal-lab.labCollectorConfDir" -}}/etc/signal-lab/collector{{- end }}

{{/* ------------------------------------------------------------ URLs */}}

{{/*
In-cluster URL of a component service.
Usage: include "signal-lab.svcUrl" (dict "ctx" $ "component" "lab" "port" 8000)
*/}}
{{- define "signal-lab.svcUrl" -}}
{{- printf "http://%s:%v" (include "signal-lab.componentName" .) .port }}
{{- end }}

{{/*
Browser URL for a UI: explicit override, else the Ingress host (https if listed in tls), else localhost:<port>.
Usage: include "signal-lab.publicUrl" (dict "ctx" $ "override" "..." "host" "grafana" "port" 3000)
*/}}
{{- define "signal-lab.publicUrl" -}}
{{- $ing := .ctx.Values.ingress }}
{{- $host := index $ing.hosts .host | default "" }}
{{- if .override }}
{{- .override | trimSuffix "/" }}
{{- else if and $ing.enabled $host }}
{{- $scheme := "http" }}
{{- range $ing.tls }}
{{- if has $host (.hosts | default list) }}
{{- $scheme = "https" }}
{{- end }}
{{- end }}
{{- printf "%s://%s" $scheme $host }}
{{- else }}
{{- printf "http://localhost:%v" .port }}
{{- end }}
{{- end }}

{{/* Shop service URL. Usage: include "signal-lab.shopUrl" (dict "ctx" $ "name" "storefront") */}}
{{- define "signal-lab.shopUrl" -}}
{{- include "signal-lab.svcUrl" (dict "ctx" .ctx "component" .name "port" 8080) }}
{{- end }}

{{/* host:port part of a URL ("https://a.b:443/x" -> "a.b:443"). */}}
{{- define "signal-lab.hostPort" -}}
{{- $u := urlParse . }}
{{- $u.host }}
{{- end }}

{{/* ------------------------------------------------------------ env */}}

{{/* SHOP_*_URL env vars. */}}
{{- define "signal-lab.shopUrlEnv" -}}
{{- range .Values.scenario.services }}
- name: {{ printf "SHOP_%s_URL" (.name | upper | replace "-" "_") }}
  value: {{ include "signal-lab.shopUrl" (dict "ctx" $ "name" .name) | quote }}
{{- end }}
{{- end }}

{{/* Backend adapter env vars for the lab container (the settings blocks of each backend plugin.yaml). */}}
{{- define "signal-lab.backendLabEnv" -}}
{{- $vm := .Values.backends.victoriametrics }}
{{- if $vm.enabled }}
{{- if eq $vm.mode "bundled" }}
{{- $vmUrl := include "signal-lab.svcUrl" (dict "ctx" $ "component" "victoriametrics" "port" 8428) }}
- name: VICTORIAMETRICS_URL
  value: {{ $vmUrl | quote }}
- name: VICTORIAMETRICS_PUBLIC_URL
  value: {{ $vm.publicUrl | default "http://localhost:8428" | trimSuffix "/" | quote }}
{{- else }}
- name: VICTORIAMETRICS_URL
  value: {{ $vm.external.url | trimSuffix "/" | quote }}
- name: VICTORIAMETRICS_PUBLIC_URL
  value: {{ $vm.external.publicUrl | default $vm.external.url | trimSuffix "/" | quote }}
{{- end }}
{{- if include "signal-lab.grafanaBundled" . }}
- name: GRAFANA_URL
  value: {{ include "signal-lab.svcUrl" (dict "ctx" $ "component" "grafana" "port" 3000) | quote }}
- name: GRAFANA_PUBLIC_URL
  value: {{ include "signal-lab.publicUrl" (dict "ctx" $ "override" $vm.grafana.publicUrl "host" "grafana" "port" 3000) | quote }}
- name: GRAFANA_DATASOURCE_UID
  value: victoriametrics
{{- else if $vm.external.grafanaUrl }}
- name: GRAFANA_URL
  value: {{ $vm.external.grafanaUrl | trimSuffix "/" | quote }}
- name: GRAFANA_PUBLIC_URL
  value: {{ $vm.external.grafanaPublicUrl | default $vm.external.grafanaUrl | trimSuffix "/" | quote }}
- name: GRAFANA_DATASOURCE_UID
  value: {{ $vm.external.grafanaDatasourceUid | default "victoriametrics" | quote }}
{{- end }}
{{- if $vm.external.grafanaToken.existingSecret }}
- name: GRAFANA_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ $vm.external.grafanaToken.existingSecret }}
      key: {{ $vm.external.grafanaToken.key }}
{{- end }}
{{- end }}
{{- $j := .Values.backends.jaeger }}
{{- if $j.enabled }}
{{- if eq $j.mode "bundled" }}
- name: JAEGER_URL
  value: {{ include "signal-lab.svcUrl" (dict "ctx" $ "component" "jaeger" "port" 16686) | quote }}
- name: JAEGER_PUBLIC_URL
  value: {{ include "signal-lab.publicUrl" (dict "ctx" $ "override" $j.publicUrl "host" "jaeger" "port" 16686) | quote }}
{{- else }}
- name: JAEGER_URL
  value: {{ $j.external.url | trimSuffix "/" | quote }}
- name: JAEGER_PUBLIC_URL
  value: {{ $j.external.publicUrl | default $j.external.url | trimSuffix "/" | quote }}
{{- end }}
{{- end }}
{{- $e := .Values.backends.elastic }}
{{- if $e.enabled }}
{{- if eq $e.mode "bundled" }}
- name: ELASTICSEARCH_URL
  value: {{ include "signal-lab.svcUrl" (dict "ctx" $ "component" "elasticsearch" "port" 9200) | quote }}
- name: KIBANA_URL
  value: {{ include "signal-lab.svcUrl" (dict "ctx" $ "component" "kibana" "port" 5601) | quote }}
- name: KIBANA_PUBLIC_URL
  value: {{ include "signal-lab.publicUrl" (dict "ctx" $ "override" $e.kibana.publicUrl "host" "kibana" "port" 5601) | quote }}
- name: ELASTIC_APM_SERVER_URL
  value: {{ include "signal-lab.svcUrl" (dict "ctx" $ "component" "apm-server" "port" 8200) | quote }}
{{- else }}
- name: ELASTICSEARCH_URL
  value: {{ $e.external.elasticsearchUrl | trimSuffix "/" | quote }}
- name: KIBANA_URL
  value: {{ $e.external.kibanaUrl | trimSuffix "/" | quote }}
- name: KIBANA_PUBLIC_URL
  value: {{ $e.external.kibanaPublicUrl | default $e.external.kibanaUrl | trimSuffix "/" | quote }}
- name: ELASTIC_APM_SERVER_URL
  value: {{ $e.external.apmServerUrl | trimSuffix "/" | quote }}
{{- if $e.external.apiKey.existingSecret }}
- name: ELASTICSEARCH_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ $e.external.apiKey.existingSecret }}
      key: {{ $e.external.apiKey.key }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}

{{/* Env vars that fill the ${env:...} placeholders of the shipped Collector configs. */}}
{{- define "signal-lab.collectorEnv" -}}
- name: SIGNAL_LAB_TAP_URL
  value: {{ printf "%s/tap" (include "signal-lab.svcUrl" (dict "ctx" $ "component" "lab" "port" .Values.lab.service.port)) | quote }}
{{- $vm := .Values.backends.victoriametrics }}
{{- if $vm.enabled }}
- name: VICTORIAMETRICS_OTLP_URL
{{- if eq $vm.mode "bundled" }}
  value: {{ printf "%s/opentelemetry/v1/metrics" (include "signal-lab.svcUrl" (dict "ctx" $ "component" "victoriametrics" "port" 8428)) | quote }}
{{- else }}
  value: {{ $vm.external.otlpUrl | default (printf "%s/opentelemetry/v1/metrics" ($vm.external.url | trimSuffix "/")) | quote }}
{{- end }}
{{- end }}
{{- $j := .Values.backends.jaeger }}
{{- if $j.enabled }}
- name: JAEGER_OTLP_ENDPOINT
{{- if eq $j.mode "bundled" }}
  value: {{ printf "%s:4317" (include "signal-lab.componentName" (dict "ctx" $ "component" "jaeger")) | quote }}
{{- else }}
  value: {{ $j.external.otlpEndpoint | quote }}
{{- end }}
{{- end }}
{{- $e := .Values.backends.elastic }}
{{- if $e.enabled }}
- name: ELASTIC_APM_OTLP_ENDPOINT
{{- if eq $e.mode "bundled" }}
  value: {{ printf "%s:8200" (include "signal-lab.componentName" (dict "ctx" $ "component" "apm-server")) | quote }}
{{- else }}
  value: {{ $e.external.apmOtlpEndpoint | default (include "signal-lab.hostPort" $e.external.apmServerUrl) | quote }}
{{- if $e.external.apmAuthHeader.existingSecret }}
- name: ELASTIC_APM_AUTH_HEADER
  valueFrom:
    secretKeyRef:
      name: {{ $e.external.apmAuthHeader.existingSecret }}
      key: {{ $e.external.apmAuthHeader.key }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}

{{/* ------------------------------------------------------------ validation */}}

{{- define "signal-lab.validate" -}}
{{- $vm := .Values.backends.victoriametrics }}
{{- if and $vm.enabled (eq $vm.mode "external") (not $vm.external.url) }}
{{- fail "backends.victoriametrics.mode=external needs backends.victoriametrics.external.url" }}
{{- end }}
{{- $j := .Values.backends.jaeger }}
{{- if and $j.enabled (eq $j.mode "external") (or (not $j.external.url) (not $j.external.otlpEndpoint)) }}
{{- fail "backends.jaeger.mode=external needs backends.jaeger.external.url and backends.jaeger.external.otlpEndpoint" }}
{{- end }}
{{- $e := .Values.backends.elastic }}
{{- if and $e.enabled (eq $e.mode "external") (or (not $e.external.elasticsearchUrl) (not $e.external.kibanaUrl) (not $e.external.apmServerUrl)) }}
{{- fail "backends.elastic.mode=external needs backends.elastic.external.elasticsearchUrl, kibanaUrl and apmServerUrl" }}
{{- end }}
{{- $names := list }}
{{- range .Values.scenario.services }}
{{- if not .name }}{{ fail "every scenario.services entry needs a name" }}{{ end }}
{{- if has .name (list "lab" "runner" "collector" "victoriametrics" "grafana" "jaeger" "elasticsearch" "kibana" "apm-server") }}
{{- fail (printf "scenario service name %q clashes with a chart component" .name) }}
{{- end }}
{{- $names = append $names .name }}
{{- end }}
{{- if ne (len $names) (len (uniq $names)) }}
{{- fail "scenario.services names must be unique" }}
{{- end }}
{{- end }}
