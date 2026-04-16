# Multi-Machine Setup with Tailscale

Tailscale creates a private mesh network (WireGuard under the hood) that lets any
machine reach any other machine by IP or MagicDNS name — no port forwarding, no
public exposure. This is the recommended way to share a single self-hosted Honcho
instance across laptops, desktops, and cloud VMs.

## Architecture

```
┌─────────────────┐         ┌─────────────────┐
│  Server Machine │         │  Client Machine │
│  (runs Honcho)  │◄───────►│  (runs agents)  │
│                 │Tailscale │                 │
│  Honcho :8000   │  mesh   │  Claude Code    │
│  Ollama :11434  │         │  Hermes Agent   │
│  PostgreSQL     │         │  ~/.honcho/     │
└─────────────────┘         └─────────────────┘
```

### Multi-Client Topology

One server hosts Honcho, PostgreSQL, and (optionally) Ollama. Any number of client
machines connect through the Tailscale mesh. Every client talks directly to the
server over an encrypted WireGuard tunnel — there is no central relay under normal
conditions.

```
                         ┌──────────────┐
                    ┌───►│  Laptop A    │
                    │    │  Claude Code │
┌──────────────┐    │    └──────────────┘
│  Server      │◄───┤
│  Honcho API  │    │    ┌──────────────┐
│  PostgreSQL  │◄───┼───►│  Desktop B   │
│  Ollama      │    │    │  Hermes      │
└──────────────┘    │    └──────────────┘
                    │
                    │    ┌──────────────┐
                    └───►│  Cloud VM C  │
                         │  Agents      │
                         └──────────────┘
```

All machines share the same Honcho workspace and memory. Agents on any machine can
read observations written by agents on any other machine.

---

## Server-Side Setup

### 1. Install Tailscale

```bash
# Debian/Ubuntu
curl -fsSL https://tailscale.com/install.sh | sh

# Or via package manager
sudo apt install tailscale
```

### 2. Authenticate and Start

```bash
sudo tailscale up
```

Follow the printed URL to authenticate in your browser. The machine joins your
tailnet automatically.

### 3. Get the Server's Tailscale IP

```bash
tailscale ip -4
# Example output: 100.100.223.89
```

Note this IP — clients will use it to reach Honcho.

### 4. Bind Honcho to All Interfaces

In your `docker-compose.yml`, make sure the API port is bound to `0.0.0.0` so
Tailscale traffic can reach it:

```yaml
services:
  api:
    ports:
      - "0.0.0.0:8000:8000"
```

If you also want clients to use the server's Ollama for embeddings:

```yaml
# Ollama is a system service, not in Docker — ensure it listens on 0.0.0.0
# /etc/systemd/system/ollama.service.d/override.conf
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0"
```

### 5. Firewall (if applicable)

If you run UFW or iptables, Tailscale traffic arrives on the `tailscale0`
interface. Most setups need no extra rules because Tailscale manages its own
interface. If you have restrictive policies:

```bash
sudo ufw allow in on tailscale0 to any port 8000 comment "Honcho API via Tailscale"
sudo ufw allow in on tailscale0 to any port 11434 comment "Ollama via Tailscale"
```

---

## Client-Side Setup

### Option A: Automated Installer

```bash
cd ~/Documents/honcho-migrate
bash client/install-client.sh
```

The installer will:
- Create `~/.honcho/` if it does not exist
- Prompt for the server's Tailscale IP (or default to localhost)
- Write `config.json` from the template
- Copy the workspace map example
- Offer to install the workspace shim (bashrc function or binary shim)

### Option B: Manual Setup

#### 1. Install Tailscale on the Client

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

#### 2. Verify Connectivity

```bash
# Replace with your server's Tailscale IP
curl http://100.100.223.89:8000/health
# Expected: {"status":"ok"}
```

If this fails, check that both machines are on the same tailnet and the server's
firewall allows port 8000.

#### 3. Configure Honcho Client

Create `~/.honcho/config.json`:

```json
{
  "apiKey": "not-required-for-self-hosted",
  "peerName": "YOUR_NAME",
  "endpoint": {
    "baseUrl": "http://100.100.223.89:8000/v3"
  },
  "sessionStrategy": "per-directory",
  "saveMessages": true,
  "enabled": true,
  "hosts": {
    "claude_code": {
      "workspace": "default"
    }
  }
}
```

Replace `100.100.223.89` with your server's actual Tailscale IP.

#### 4. (Optional) Set Up Workspace Auto-Switching

Copy the workspace map and shim:

```bash
cp client/workspace-map.conf.example ~/.honcho/workspace-map.conf
# Edit the map to match your projects
```

Then either source the bashrc function or install the binary shim — see
`client/install-client.sh` for details.

---

## Security

### Tailscale ACLs

Tailscale ACLs (Access Control Lists) let you restrict which machines on your
tailnet can reach the Honcho server. Configure these in the Tailscale admin
console at https://login.tailscale.com/admin/acls.

Example policy that limits Honcho access to specific machines:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["tag:honcho-client"],
      "dst": ["tag:honcho-server:8000"]
    }
  ],
  "tagOwners": {
    "tag:honcho-server": ["autogroup:admin"],
    "tag:honcho-client": ["autogroup:admin"]
  }
}
```

### Honcho Auth Keys

For self-hosted Honcho, API key authentication is optional. The default key
`not-required-for-self-hosted` or `local` works out of the box. If you want an
extra layer:

1. Set `AUTH_SECRET` in the server's `.env`
2. Use that value as `apiKey` in every client's `config.json`

For a private tailnet with ACLs, this is usually unnecessary.

### Network Isolation

Tailscale traffic never touches the public internet. The WireGuard tunnel is
end-to-end encrypted. Even if your server has no firewall rules at all, only
machines on your tailnet can reach it.

---

## DNS: MagicDNS

Instead of remembering Tailscale IPs, you can use MagicDNS names. Enable MagicDNS
in the Tailscale admin console, then use the machine's hostname:

```json
{
  "endpoint": {
    "baseUrl": "http://my-server.tail12345.ts.net:8000/v3"
  }
}
```

Find your MagicDNS name:

```bash
tailscale status
# Shows: 100.100.223.89  my-server  alex@  linux  -
# MagicDNS: my-server.tail12345.ts.net
```

MagicDNS names survive IP changes and are easier to share with teammates.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `curl` times out | Machines not on same tailnet | Run `tailscale status` on both; re-auth if needed |
| Connection refused | Honcho not bound to 0.0.0.0 | Check `docker-compose.yml` ports binding |
| Firewall blocks | UFW/iptables dropping tailscale0 | Add allow rules for tailscale0 interface |
| DNS name not resolving | MagicDNS disabled | Enable in Tailscale admin or use raw IP |
| Slow first connection | DERP relay fallback | Wait for direct connection or check NAT settings |
