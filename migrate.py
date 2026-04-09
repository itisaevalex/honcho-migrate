#!/usr/bin/env python3
"""
honcho-migrate — Migrate Honcho memory data between any two instances.

Replays workspaces, peers, sessions, messages, and peer observer configs
through the target API. The target's deriver re-extracts observations and
rebuilds memory from the replayed messages.

Works in any direction: cloud ↔ self-hosted ↔ self-hosted.

Usage:
  # Dry run
  python3 migrate.py --target https://api.honcho.dev --target-key KEY --dry-run

  # Local → Cloud
  python3 migrate.py --target https://api.honcho.dev --target-key KEY

  # Cloud → Local
  python3 migrate.py --source https://api.honcho.dev --source-key KEY --target http://localhost:8000

  # Single workspace only
  python3 migrate.py --target http://other:8000 --workspace my-project
"""

import argparse
import sys
import time

import requests

DEFAULT_SOURCE = "http://localhost:8000"
DEFAULT_DELAY = 0.3
DEFAULT_BATCH = 20


def api(base_url, key, method, path, body=None, retries=5, timeout=60):
    """Make an API call with retry on 429."""
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    for attempt in range(retries):
        try:
            fn = requests.get if method == "GET" else requests.post
            r = fn(f"{base_url}{path}", json=body if method != "GET" else None,
                   headers=headers, timeout=timeout)

            if r.status_code == 429:
                wait = min(2 ** attempt, 10)
                time.sleep(wait)
                continue
            if r.status_code == 204 or not r.content:
                return {}
            if r.ok:
                return r.json()
            return {"_error": f"HTTP {r.status_code}: {r.text[:200]}"}
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            return {"_error": str(e)}
    return {"_error": "Rate limited after retries"}


def paginate_all(base_url, key, path, page_size=100):
    """Fetch all pages from a paginated Honcho list endpoint."""
    items = []
    page = 1
    while True:
        data = api(base_url, key, "POST", f"{path}?page={page}&size={page_size}")
        batch = data.get("items", [])
        if not batch:
            break
        items.extend(batch)
        if page >= data.get("pages", 1):
            break
        page += 1
    return items


def migrate(source_url, source_key, target_url, target_key,
            dry_run=False, delay=DEFAULT_DELAY, workspace_filter=None,
            batch_size=DEFAULT_BATCH):
    """Run the migration."""

    # Auto-detect delay for cloud targets
    if delay == DEFAULT_DELAY and "localhost" in target_url:
        delay = 0

    print(f"  Source:    {source_url}")
    print(f"  Target:    {target_url}")
    print(f"  Filter:    {workspace_filter or 'all workspaces'}")
    print(f"  Dry run:   {dry_run}")
    print(f"  Delay:     {delay}s")
    print()

    # Connectivity check
    for label, url, key in [("Source", source_url, source_key), ("Target", target_url, target_key)]:
        r = api(url, key, "POST", "/v3/workspaces/list?size=1")
        if "_error" in r:
            print(f"  ERROR: Cannot reach {label} at {url}: {r['_error']}")
            return False
        print(f"  {label}: connected")
    print()

    # List workspaces
    workspaces = paginate_all(source_url, source_key, "/v3/workspaces/list")
    if workspace_filter:
        workspaces = [w for w in workspaces if w["id"] == workspace_filter]
        if not workspaces:
            print(f"  Workspace '{workspace_filter}' not found on source.")
            return False

    print(f"  Found {len(workspaces)} workspace(s)\n")

    stats = {"workspaces": 0, "peers": 0, "sessions": 0, "messages": 0, "errors": 0}
    start_time = time.time()

    for ws in workspaces:
        ws_id = ws["id"]
        print(f"  -- Workspace: {ws_id}")

        # Create workspace on target
        if not dry_run:
            result = api(target_url, target_key, "POST", "/v3/workspaces", {"id": ws_id})
            if "_error" in result:
                print(f"     ERROR: {result['_error']}")
                stats["errors"] += 1
                continue
            if delay:
                time.sleep(delay)
        stats["workspaces"] += 1

        # Peers
        peers = paginate_all(source_url, source_key, f"/v3/workspaces/{ws_id}/peers/list")
        print(f"     Peers: {len(peers)}")
        for peer in peers:
            if not dry_run:
                api(target_url, target_key, "POST",
                    f"/v3/workspaces/{ws_id}/peers", {"id": peer["id"]})
                if delay:
                    time.sleep(delay)
            stats["peers"] += 1

        # Sessions
        sessions = paginate_all(source_url, source_key, f"/v3/workspaces/{ws_id}/sessions/list")
        print(f"     Sessions: {len(sessions)}")

        for session in sessions:
            sid = session["id"]
            if not dry_run:
                api(target_url, target_key, "POST",
                    f"/v3/workspaces/{ws_id}/sessions", {"id": sid})
                if delay:
                    time.sleep(delay)
            stats["sessions"] += 1

            # Peer observer configs
            session_peers = api(source_url, source_key, "GET",
                                f"/v3/workspaces/{ws_id}/sessions/{sid}/peers")
            sp_items = session_peers.get("items", [])

            if sp_items and not dry_run:
                peer_configs = {}
                for sp in sp_items:
                    config = api(source_url, source_key, "GET",
                                 f"/v3/workspaces/{ws_id}/sessions/{sid}/peers/{sp['id']}/config")
                    if not config.get("_error"):
                        peer_configs[sp["id"]] = config
                if peer_configs:
                    api(target_url, target_key, "POST",
                        f"/v3/workspaces/{ws_id}/sessions/{sid}/peers", peer_configs)
                    if delay:
                        time.sleep(delay)

            # Messages (paginated, chronological)
            session_msgs = 0
            page = 1
            while True:
                msgs_data = api(source_url, source_key, "POST",
                                f"/v3/workspaces/{ws_id}/sessions/{sid}/messages/list"
                                f"?page={page}&size=50")
                messages = msgs_data.get("items", [])
                if not messages:
                    break

                messages.sort(key=lambda m: m.get("created_at", ""))

                if not dry_run:
                    batch = [
                        {"content": m["content"], "peer_id": m["peer_id"], "role": "user"}
                        for m in messages if m.get("content")
                    ]
                    for i in range(0, len(batch), batch_size):
                        chunk = batch[i:i + batch_size]
                        result = api(target_url, target_key, "POST",
                                     f"/v3/workspaces/{ws_id}/sessions/{sid}/messages",
                                     {"messages": chunk})
                        if "_error" in result:
                            print(f"     ERROR [{sid}]: {result['_error']}")
                            stats["errors"] += 1
                        if delay:
                            time.sleep(delay)

                session_msgs += len(messages)
                if page >= msgs_data.get("pages", 1):
                    break
                page += 1

            stats["messages"] += session_msgs
            if session_msgs > 0:
                print(f"       {sid}: {session_msgs} messages")

    elapsed = time.time() - start_time

    # Summary
    print(f"\n  {'DRY RUN - ' if dry_run else ''}Migration Summary:")
    print(f"    Workspaces: {stats['workspaces']}")
    print(f"    Peers:      {stats['peers']}")
    print(f"    Sessions:   {stats['sessions']}")
    print(f"    Messages:   {stats['messages']}")
    if stats["errors"]:
        print(f"    Errors:     {stats['errors']}")
    print(f"    Time:       {elapsed:.1f}s")

    if not dry_run and stats["messages"] > 0:
        print(f"\n  Messages replayed. The target's deriver will re-extract observations.")
        print(f"  Memories will rebuild as the deriver processes the queue.")

    return stats["errors"] == 0


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Honcho memory data between instances",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local → Cloud
  python3 migrate.py --target https://api.honcho.dev --target-key KEY

  # Cloud → Local
  python3 migrate.py --source https://api.honcho.dev --source-key KEY --target http://localhost:8000

  # Single workspace
  python3 migrate.py --target http://other:8000 --workspace my-project

  # Dry run
  python3 migrate.py --target https://api.honcho.dev --dry-run
""")
    parser.add_argument("--source", default=DEFAULT_SOURCE,
                        help=f"Source Honcho URL (default: {DEFAULT_SOURCE})")
    parser.add_argument("--source-key", default="", help="Source API key")
    parser.add_argument("--target", required=True, help="Target Honcho URL")
    parser.add_argument("--target-key", default="", help="Target API key")
    parser.add_argument("--dry-run", action="store_true", help="Preview without migrating")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"Delay between requests in seconds (default: {DEFAULT_DELAY})")
    parser.add_argument("--workspace", default=None, help="Migrate only this workspace")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH,
                        help=f"Messages per batch (default: {DEFAULT_BATCH})")

    args = parser.parse_args()

    print()
    print("  honcho-migrate")
    print("  ==============")
    print()

    success = migrate(
        args.source, args.source_key,
        args.target, args.target_key,
        dry_run=args.dry_run,
        delay=args.delay,
        workspace_filter=args.workspace,
        batch_size=args.batch_size,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
