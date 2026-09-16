# Start the self-hosted n8n that runs the Book Explainer (free, localhost:5678).
# Why each setting: the workflow's Code nodes read/write the run JSON on disk, and the
# guard runs as a local Python command - both are off by default in n8n 2.x.
$env:N8N_PORT = "5678"
$env:N8N_SECURE_COOKIE = "false"
$env:N8N_RUNNERS_ENABLED = "true"
$env:NODE_FUNCTION_ALLOW_BUILTIN = "fs,path"          # Code nodes read/write the run folder
$env:N8N_RESTRICT_FILE_ACCESS_TO = "C:\Users\ajwal\Documents\ai_agent_eval"
$env:N8N_BLOCK_FILE_ACCESS_TO_N8N_FILES = "true"
$env:NODES_EXCLUDE = "[]"                              # re-enable Execute Command (guard + book payload)
$env:N8N_DIAGNOSTICS_ENABLED = "false"
$env:N8N_PERSONALIZATION_ENABLED = "false"
$env:N8N_DEFAULT_LOCALE = "en"
$env:GENERIC_TIMEZONE = "America/New_York"
$env:N8N_LOG_LEVEL = "info"
if ($args -contains "--tunnel") { n8n start --tunnel } else { n8n start }
