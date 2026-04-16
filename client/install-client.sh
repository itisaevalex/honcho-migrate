#!/usr/bin/env bash
set -euo pipefail

# install-client.sh — Set up a Honcho client on this machine.
# Creates ~/.honcho/, writes config from template, installs workspace shim.
# Safe to re-run: never clobbers existing files.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HONCHO_DIR="$HOME/.honcho"
CONFIG_FILE="$HONCHO_DIR/config.json"
WORKSPACE_MAP="$HONCHO_DIR/workspace-map.conf"
TEMPLATE="$REPO_DIR/templates/honcho-config.json"

# --- Colors (disabled if not a terminal) ---
if [ -t 1 ]; then
  BOLD='\033[1m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  RED='\033[0;31m'
  RESET='\033[0m'
else
  BOLD='' GREEN='' YELLOW='' RED='' RESET=''
fi

info()  { echo -e "${GREEN}[OK]${RESET}   $1"; }
warn()  { echo -e "${YELLOW}[SKIP]${RESET} $1"; }
error() { echo -e "${RED}[ERR]${RESET}  $1"; }
step()  { echo -e "\n${BOLD}=> $1${RESET}"; }

# --- 1. Create ~/.honcho/ ---
step "Checking ~/.honcho directory"

if [ -d "$HONCHO_DIR" ]; then
  info "$HONCHO_DIR already exists"
else
  mkdir -p "$HONCHO_DIR"
  info "Created $HONCHO_DIR"
fi

# --- 2. Prompt for Honcho server address ---
step "Configuring Honcho server endpoint"

if [ -f "$CONFIG_FILE" ]; then
  warn "$CONFIG_FILE already exists — not overwriting"
else
  echo ""
  echo "Where is your Honcho server running?"
  echo "  - Enter a Tailscale IP   (e.g. 100.100.223.89)"
  echo "  - Enter a MagicDNS name  (e.g. my-server.tail12345.ts.net)"
  echo "  - Press Enter for localhost (single-machine setup)"
  echo ""
  read -rp "Honcho server address [localhost]: " HONCHO_HOST
  HONCHO_HOST="${HONCHO_HOST:-localhost}"

  # Prompt for peer name
  DEFAULT_PEER="$(whoami)"
  read -rp "Your name / peer name [$DEFAULT_PEER]: " PEER_NAME
  PEER_NAME="${PEER_NAME:-$DEFAULT_PEER}"

  if [ ! -f "$TEMPLATE" ]; then
    error "Template not found at $TEMPLATE"
    error "Run this script from the honcho-migrate repo."
    exit 1
  fi

  # Sanitize inputs before substitution (prevent sed/JSON injection)
  HONCHO_HOST="${HONCHO_HOST//[^A-Za-z0-9._:-]/}"
  PEER_NAME="${PEER_NAME//[^A-Za-z0-9._@ -]/}"

  # Write config from template, replacing placeholders
  sed \
    -e "s|YOUR_HONCHO_HOST|$HONCHO_HOST|g" \
    -e "s|YOUR_NAME|$PEER_NAME|g" \
    "$TEMPLATE" > "$CONFIG_FILE"

  info "Wrote $CONFIG_FILE (server: $HONCHO_HOST, peer: $PEER_NAME)"

  # Quick connectivity check (non-blocking)
  if command -v curl &>/dev/null; then
    echo ""
    echo "  Testing connection to http://$HONCHO_HOST:8000/health ..."
    if curl -sf --connect-timeout 5 "http://$HONCHO_HOST:8000/health" >/dev/null 2>&1; then
      info "Honcho API is reachable"
    else
      warn "Could not reach Honcho API — make sure the server is running"
      echo "       You can test later with: curl http://$HONCHO_HOST:8000/health"
    fi
  fi
fi

# --- 3. Copy workspace map example ---
step "Setting up workspace map"

if [ -f "$WORKSPACE_MAP" ]; then
  warn "$WORKSPACE_MAP already exists — not overwriting"
else
  EXAMPLE="$SCRIPT_DIR/workspace-map.conf.example"
  if [ -f "$EXAMPLE" ]; then
    cp "$EXAMPLE" "$WORKSPACE_MAP"
    info "Copied workspace-map.conf.example to $WORKSPACE_MAP"
    echo "       Edit this file to map your project directories to Honcho workspaces."
  else
    warn "workspace-map.conf.example not found in $SCRIPT_DIR"
  fi
fi

# --- 4. Install workspace shim ---
step "Workspace shim installation"

echo ""
echo "The workspace shim auto-switches Honcho workspaces based on your"
echo "current directory when you run 'claude'. Two options:"
echo ""
echo "  1) Bashrc function  — adds a shell function to ~/.bashrc"
echo "                        (works everywhere, easy to remove)"
echo ""
echo "  2) Binary shim      — copies a script to ~/.local/bin/claude"
echo "                        (intercepts the real binary, transparent)"
echo ""
echo "  3) Skip             — do not install a shim"
echo ""

read -rp "Choose [1/2/3]: " SHIM_CHOICE

case "${SHIM_CHOICE:-3}" in
  1)
    BASHRC="$HOME/.bashrc"
    MARKER="# >>> honcho workspace shim >>>"
    if grep -qF "$MARKER" "$BASHRC" 2>/dev/null; then
      warn "Bashrc shim already installed — not modifying $BASHRC"
    else
      AUTO_WS="$SCRIPT_DIR/auto-workspace.sh"
      if [ ! -f "$AUTO_WS" ]; then
        error "auto-workspace.sh not found at $AUTO_WS"
        exit 1
      else
        {
          echo ""
          echo "$MARKER"
          echo "source \"$AUTO_WS\""
          echo "# <<< honcho workspace shim <<<"
        } >> "$BASHRC"
        info "Added workspace shim to $BASHRC"
        echo "       Run 'source ~/.bashrc' or open a new terminal to activate."
      fi
    fi
    ;;
  2)
    SHIM_DIR="$HOME/.local/bin"
    SHIM_TARGET="$SHIM_DIR/claude"
    SHIM_SRC="$SCRIPT_DIR/claude-shim"

    if [ -f "$SHIM_TARGET" ]; then
      warn "$SHIM_TARGET already exists — not overwriting"
      echo "       Remove it manually if you want to reinstall."
    elif [ ! -f "$SHIM_SRC" ]; then
      error "claude-shim not found at $SHIM_SRC"
    else
      mkdir -p "$SHIM_DIR"
      cp "$SHIM_SRC" "$SHIM_TARGET"
      chmod +x "$SHIM_TARGET"
      info "Installed shim to $SHIM_TARGET"

      # Check PATH precedence
      if command -v claude &>/dev/null; then
        WHICH_CLAUDE="$(command -v claude)"
        if [ "$WHICH_CLAUDE" = "$SHIM_TARGET" ]; then
          info "Shim is first in PATH — it will intercept 'claude' commands"
        else
          warn "Current 'claude' resolves to $WHICH_CLAUDE"
          echo "       Make sure $SHIM_DIR is before that path in your \$PATH."
          echo "       Add to ~/.bashrc:  export PATH=\"$SHIM_DIR:\$PATH\""
        fi
      fi
    fi
    ;;
  *)
    info "Skipping shim installation"
    echo "       You can install later by re-running this script."
    ;;
esac

# --- 5. Detect Claude Code ---
step "Checking for Claude Code"

CLAUDE_BIN=""
if command -v claude &>/dev/null; then
  CLAUDE_BIN="$(command -v claude)"
  info "Claude Code found at $CLAUDE_BIN"
elif [ -d "$HOME/.local/share/claude/versions" ]; then
  info "Claude Code versions directory exists (binary may not be in PATH)"
else
  warn "Claude Code not detected"
  echo "       Install from: https://docs.anthropic.com/en/docs/claude-code"
  echo "       The Honcho config will be ready when you do."
fi

# --- Summary ---
step "Setup complete"

echo ""
echo "  Config:         $CONFIG_FILE"
echo "  Workspace map:  $WORKSPACE_MAP"
if [ -f "$CONFIG_FILE" ]; then
  CONFIGURED_HOST=$(python3 -c "
import json
with open('$CONFIG_FILE') as f:
    cfg = json.load(f)
print(cfg.get('endpoint', {}).get('baseUrl', 'unknown'))
" 2>/dev/null || echo "unknown")
  echo "  Server:         $CONFIGURED_HOST"
fi
echo ""
echo "  Next steps:"
echo "    1. Edit $WORKSPACE_MAP to map your projects"
echo "    2. Start using 'claude' — memory is now persistent"
echo ""
