{{- define "kestrel.name" -}}{{ .Release.Name }}{{- end -}}
{{- define "kestrel.labels" -}}
app.kubernetes.io/name: kestrel-agents
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
{{- define "kestrel.selector" -}}
app.kubernetes.io/name: kestrel-agents
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
