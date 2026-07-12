{{/*
charts/launchpad/templates/_helpers.tpl
Standard naming helpers for the launchpad chart.
Follows helm create naming conventions — name/fullname/labels/selectorLabels.
Adds: launchpad.mongodb.fullname — the SINGLE source of truth for the
mongodb Service name and the MONGO_URI hostname (Phase 9, DEP-03).
The distinct "launchpad" name/prefix is what prevents a label-selector collision
with any other chart sharing this namespace (SC #1).
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "launchpad.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
Truncated at 63 chars (DNS naming spec limit).
When release name contains chart name, release name is used as the full name.
Recommended release name: "launchpad" — collapses fullname to "launchpad".
*/}}
{{- define "launchpad.fullname" -}}
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
Never write the mongodb hostname anywhere else (mirrors field-guide-api Pitfall 9).
*/}}
{{- define "launchpad.mongodb.fullname" -}}
{{- printf "%s-mongodb" (include "launchpad.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "launchpad.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels — applied to all resources.
*/}}
{{- define "launchpad.labels" -}}
helm.sh/chart: {{ include "launchpad.chart" . }}
{{ include "launchpad.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels — used by Deployment selector and Service selector.
These are immutable once a Deployment is created; do not add mutable fields here.
Distinct app.kubernetes.io/name: launchpad prevents other charts' Service
selectors from matching launchpad pods and vice versa (SC #1).
*/}}
{{- define "launchpad.selectorLabels" -}}
app.kubernetes.io/name: {{ include "launchpad.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
MongoDB selector labels — DISTINCT identity from the app selectorLabels.
Kubernetes label selectors are subset matches: if the mongodb pod carried the
app's name/instance labels, the app Service would route traffic to mongod
(connection refused on port 8000). A distinct app.kubernetes.io/name keeps the
app Service Endpoints scoped to app pods only.
SINGLE source of truth for mongodb pod identity — used by:
  - templates/mongodb/deployment.yaml (spec.selector.matchLabels + pod template labels)
  - templates/mongodb/service.yaml    (spec.selector)
*/}}
{{- define "launchpad.mongodb.selectorLabels" -}}
app.kubernetes.io/name: {{ include "launchpad.name" . }}-mongodb
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
