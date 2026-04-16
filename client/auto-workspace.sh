#!/usr/bin/env bash
# Resolve Honcho workspace from cwd using ~/.honcho/workspace-map.conf
# Patches ~/.honcho/config.json directly (hosts block takes precedence over env vars).
# Source this in .bashrc, then use `claude` as normal.
# To bypass: `command claude` runs the real binary without the shim.

_honcho_resolve_workspace() {
  local map_file="$HOME/.honcho/workspace-map.conf"
  [ -f "$map_file" ] || return
  while IFS='=' read -r pattern workspace; do
    [[ "$pattern" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$pattern" ]] && continue
    if [[ "$PWD" == *"$pattern"* ]]; then
      echo "$workspace"
      return
    fi
  done < "$map_file"
}

claude() {
  local ws config="$HOME/.honcho/config.json"
  ws=$(_honcho_resolve_workspace)
  ws="${ws:-claude_code}"

  if [ -f "$config" ] && command -v python3 &>/dev/null; then
    HONCHO_WS="$ws" HONCHO_CFG="$config" python3 -c "
import json, os
config_path = os.environ['HONCHO_CFG']
ws = os.environ['HONCHO_WS']
with open(config_path) as f:
    cfg = json.load(f)
cfg.setdefault('hosts', {}).setdefault('claude_code', {})['workspace'] = ws
with open(config_path, 'w') as f:
    json.dump(cfg, f, indent=2)
" 2>/dev/null
  fi

  command claude "$@"
}
