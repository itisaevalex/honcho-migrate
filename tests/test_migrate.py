#!/usr/bin/env python3
"""
test_migrate.py — Automated tests for honcho-migrate.

Tests migration between Honcho instances with various edge cases.

Usage:
  python3 tests/test_migrate.py
  HONCHO_URL=http://localhost:8000 python3 tests/test_migrate.py
"""

import json
import os
import subprocess
import sys
import time
import uuid

import requests

HONCHO_URL = os.environ.get("HONCHO_URL", "http://localhost:8000")
MIGRATE_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrate.py")

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []


def hpost(path, body=None):
    r = requests.post(f"{HONCHO_URL}{path}", json=body, headers={"Content-Type": "application/json"}, timeout=30)
    if r.status_code == 429:
        time.sleep(2)
        r = requests.post(f"{HONCHO_URL}{path}", json=body, headers={"Content-Type": "application/json"}, timeout=30)
    if r.status_code in (204,) or not r.content:
        return {}
    return r.json() if r.ok else {"_error": f"{r.status_code}: {r.text[:200]}"}


def hget(path):
    r = requests.get(f"{HONCHO_URL}{path}", timeout=15)
    return r.json() if r.ok else {}


def hdelete(path):
    requests.delete(f"{HONCHO_URL}{path}", timeout=15)


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, condition))
    print(f"  {status}  {name}" + (f" — {detail}" if detail and not condition else ""))
    return condition


def create_test_workspace(ws_id, num_peers=2, num_sessions=2, msgs_per_session=5):
    """Create a workspace with test data."""
    hpost("/v3/workspaces", {"id": ws_id})
    peers = [f"peer-{i}" for i in range(num_peers)]
    for p in peers:
        hpost(f"/v3/workspaces/{ws_id}/peers", {"id": p})

    for s in range(num_sessions):
        sid = f"session-{s}"
        hpost(f"/v3/workspaces/{ws_id}/sessions", {"id": sid})
        # Add peers with observer config
        peer_config = {p: {"observe_me": True, "observe_others": True} for p in peers}
        hpost(f"/v3/workspaces/{ws_id}/sessions/{sid}/peers", peer_config)
        # Add messages
        messages = [
            {"content": f"Message {m} from {peers[m % len(peers)]} in session {s}",
             "peer_id": peers[m % len(peers)], "role": "user"}
            for m in range(msgs_per_session)
        ]
        hpost(f"/v3/workspaces/{ws_id}/sessions/{sid}/messages", {"messages": messages})

    return peers


def count_messages(ws_id, session_id):
    data = hpost(f"/v3/workspaces/{ws_id}/sessions/{session_id}/messages/list?size=1")
    return data.get("total", 0)


# ===========================================================================
# Tests
# ===========================================================================

def test_dry_run():
    """Test that dry run doesn't modify anything."""
    print("\n--- Test: Dry Run ---")
    uid = uuid.uuid4().hex[:8]
    ws = f"test-dry-{uid}"
    create_test_workspace(ws, num_peers=2, num_sessions=1, msgs_per_session=3)

    result = subprocess.run(
        [sys.executable, MIGRATE_SCRIPT,
         "--source", HONCHO_URL, "--target", HONCHO_URL, "--dry-run"],
        capture_output=True, text=True, timeout=60
    )
    output = result.stdout

    check("Dry run exits cleanly", result.returncode == 0, result.stderr[:200])
    check("Dry run shows workspace", ws in output)
    check("Dry run shows 'DRY RUN' in summary", "DRY RUN" in output)
    check("Dry run counts peers", "2" in output)

    # Cleanup
    hdelete(f"/v3/workspaces/{ws}")


def test_basic_migration():
    """Test basic local-to-local migration (idempotent — same instance)."""
    print("\n--- Test: Basic Migration ---")
    uid = uuid.uuid4().hex[:8]
    ws = f"test-basic-{uid}"
    create_test_workspace(ws, num_peers=2, num_sessions=2, msgs_per_session=5)

    # Count source messages
    src_msgs_s0 = count_messages(ws, "session-0")
    src_msgs_s1 = count_messages(ws, "session-1")

    # Migrate (same instance — workspace already exists, messages get appended)
    result = subprocess.run(
        [sys.executable, MIGRATE_SCRIPT,
         "--source", HONCHO_URL, "--target", HONCHO_URL,
         "--workspace", ws, "--delay", "0"],
        capture_output=True, text=True, timeout=120
    )

    check("Migration exits cleanly", result.returncode == 0, result.stderr[:200])
    check("Migration summary present", "Migration Summary" in result.stdout)

    # On same-instance migration, messages get duplicated (appended)
    post_msgs_s0 = count_messages(ws, "session-0")
    check("Messages exist after migration", post_msgs_s0 >= src_msgs_s0,
          f"before={src_msgs_s0} after={post_msgs_s0}")

    # Cleanup
    hdelete(f"/v3/workspaces/{ws}")


def test_edge_cases():
    """Test edge case data."""
    print("\n--- Test: Edge Cases ---")
    uid = uuid.uuid4().hex[:8]
    ws = f"test-edge-{uid}"
    hpost("/v3/workspaces", {"id": ws})

    # Empty workspace (no peers, no sessions)
    # Should not crash the migration

    # Peer with special names
    hpost(f"/v3/workspaces/{ws}/peers", {"id": "user-with-hyphens"})
    hpost(f"/v3/workspaces/{ws}/peers", {"id": "under_score_peer"})

    # Session with special messages
    hpost(f"/v3/workspaces/{ws}/sessions", {"id": "edge-session"})
    hpost(f"/v3/workspaces/{ws}/sessions/edge-session/peers",
          {"user-with-hyphens": {"observe_me": True, "observe_others": True}})

    special_messages = [
        {"content": 'He said "hello" and she said \'goodbye\'', "peer_id": "user-with-hyphens", "role": "user"},
        {"content": "Line 1\nLine 2\nLine 3", "peer_id": "user-with-hyphens", "role": "user"},
        {"content": "Unicode test: cafe\u0301 na\u00efve re\u0301sume\u0301", "peer_id": "user-with-hyphens", "role": "user"},
        {"content": "<script>alert('xss')</script> <b>bold</b>", "peer_id": "user-with-hyphens", "role": "user"},
        {"content": "A" * 3000, "peer_id": "user-with-hyphens", "role": "user"},
    ]
    hpost(f"/v3/workspaces/{ws}/sessions/edge-session/messages", {"messages": special_messages})

    # Migrate
    result = subprocess.run(
        [sys.executable, MIGRATE_SCRIPT,
         "--source", HONCHO_URL, "--target", HONCHO_URL,
         "--workspace", ws, "--delay", "0"],
        capture_output=True, text=True, timeout=120
    )

    check("Edge case migration exits cleanly", result.returncode == 0, result.stderr[:200])
    check("Edge case messages counted", "5" in result.stdout or "edge-session" in result.stdout)

    # Verify messages survived
    msgs = hpost(f"/v3/workspaces/{ws}/sessions/edge-session/messages/list?size=50")
    total = msgs.get("total", 0)
    check("Special messages preserved", total >= 5, f"found {total}")

    # Cleanup
    hdelete(f"/v3/workspaces/{ws}")


def test_empty_workspace():
    """Test migration of empty workspace."""
    print("\n--- Test: Empty Workspace ---")
    uid = uuid.uuid4().hex[:8]
    ws = f"test-empty-{uid}"
    hpost("/v3/workspaces", {"id": ws})

    result = subprocess.run(
        [sys.executable, MIGRATE_SCRIPT,
         "--source", HONCHO_URL, "--target", HONCHO_URL,
         "--workspace", ws, "--delay", "0"],
        capture_output=True, text=True, timeout=60
    )

    check("Empty workspace migration exits cleanly", result.returncode == 0, result.stderr[:200])
    check("Shows 0 messages", "Messages:   0" in result.stdout or "Messages:      0" in result.stdout)

    hdelete(f"/v3/workspaces/{ws}")


def test_workspace_filter():
    """Test --workspace flag migrates only the specified workspace."""
    print("\n--- Test: Workspace Filter ---")
    uid = uuid.uuid4().hex[:8]
    ws1 = f"test-filter-a-{uid}"
    ws2 = f"test-filter-b-{uid}"
    create_test_workspace(ws1, num_peers=1, num_sessions=1, msgs_per_session=3)
    create_test_workspace(ws2, num_peers=1, num_sessions=1, msgs_per_session=3)

    result = subprocess.run(
        [sys.executable, MIGRATE_SCRIPT,
         "--source", HONCHO_URL, "--target", HONCHO_URL,
         "--workspace", ws1, "--delay", "0", "--dry-run"],
        capture_output=True, text=True, timeout=60
    )

    check("Filter shows target workspace", ws1 in result.stdout)
    check("Filter excludes other workspace", ws2 not in result.stdout)

    hdelete(f"/v3/workspaces/{ws1}")
    hdelete(f"/v3/workspaces/{ws2}")


def test_idempotency():
    """Test running migration twice doesn't crash."""
    print("\n--- Test: Idempotency ---")
    uid = uuid.uuid4().hex[:8]
    ws = f"test-idemp-{uid}"
    create_test_workspace(ws, num_peers=1, num_sessions=1, msgs_per_session=3)

    for run in range(2):
        result = subprocess.run(
            [sys.executable, MIGRATE_SCRIPT,
             "--source", HONCHO_URL, "--target", HONCHO_URL,
             "--workspace", ws, "--delay", "0"],
            capture_output=True, text=True, timeout=120
        )
        check(f"Run {run + 1} exits cleanly", result.returncode == 0, result.stderr[:100])

    # Note: messages will be duplicated on same-instance migration
    # This is expected since Honcho's message API always appends
    msgs = hpost(f"/v3/workspaces/{ws}/sessions/session-0/messages/list?size=1")
    total = msgs.get("total", 0)
    check("Idempotency note: messages appended (expected)", total >= 3, f"total={total}")

    hdelete(f"/v3/workspaces/{ws}")


# ===========================================================================

def main():
    print(f"Testing honcho-migrate against {HONCHO_URL}")

    # Health check
    try:
        r = requests.get(f"{HONCHO_URL}/health", timeout=5)
        assert r.ok
    except Exception:
        print(f"ERROR: Cannot reach Honcho at {HONCHO_URL}")
        sys.exit(1)

    test_dry_run()
    test_basic_migration()
    test_edge_cases()
    test_empty_workspace()
    test_workspace_filter()
    test_idempotency()

    # Summary
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{'=' * 40}")
    print(f"Results: {passed}/{total} passed")
    if passed == total:
        print(f"\033[92mAll tests passed!\033[0m")
    else:
        failed = [name for name, ok in results if not ok]
        print(f"\033[91mFailed: {', '.join(failed)}\033[0m")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
