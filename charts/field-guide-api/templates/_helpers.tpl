{{/*
charts/field-guide-api/templates/_helpers.tpl
Standard naming helpers for the field-guide-api chart.
Follows helm create naming conventions — name/fullname/labels/selectorLabels.
Adds: field-guide-api.mongodb.fullname — the SINGLE source of truth for the
mongodb Service name and the MONGO_URI hostname (RESEARCH.md Pitfall 9).
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "field-guide-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
Truncated at 63 chars (DNS naming spec limit).
When release name contains chart name, release name is used as the full name.
Recommended release name: "field-guide-api" — collapses fullname to "field-guide-api".
*/}}
{{- define "field-guide-api.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Fully qualified name for MongoDB resources.
SINGLE SOURCE OF TRUTH — this helper is used by BOTH:
  - templates/mongodb/service.yaml  (metadata.name)
  - templates/secret.yaml           (MONGO_URI hostname)
Never write the mongodb hostname anywhere else (RESEARCH.md Pitfall 9).
*/}}
{{- define "field-guide-api.mongodb.fullname" -}}
{{- printf "%s-mongodb" (include "field-guide-api.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "field-guide-api.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels — applied to all resources.
*/}}
{{- define "field-guide-api.labels" -}}
helm.sh/chart: {{ include "field-guide-api.chart" . }}
{{ include "field-guide-api.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels — used by Deployment selector and Service selector.
These are immutable once a Deployment is created; do not add mutable fields here.
*/}}
{{- define "field-guide-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "field-guide-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
MongoDB selector labels — DISTINCT identity from the app selectorLabels.
Kubernetes label selectors are subset matches: if the mongodb pod carried the
app's name/instance labels, the app Service would route traffic to mongod
(connection refused on port 8000). A distinct app.kubernetes.io/name keeps the
app Service Endpoints scoped to API pods only.
SINGLE source of truth for mongodb pod identity — used by:
  - templates/mongodb/deployment.yaml (spec.selector.matchLabels + pod template labels)
  - templates/mongodb/service.yaml    (spec.selector)
*/}}
{{- define "field-guide-api.mongodb.selectorLabels" -}}
app.kubernetes.io/name: {{ include "field-guide-api.name" . }}-mongodb
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
