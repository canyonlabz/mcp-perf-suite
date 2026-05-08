# Rancher Desktop: Container Port Not Reachable on macOS (Lima SSH Port Forwarding Failure)

This guide covers a silent port forwarding failure in Rancher Desktop on macOS where a
container port (e.g., `5432`) appears mapped in `docker ps` but is completely unreachable
from `localhost`.

> **See also:**
> - [Rancher Desktop Fix](rancher-desktop-fix.md) — mount type and file sharing fixes
> - [MacBook Troubleshooting Guide](pgvector-fix-on-macbook.md) — PostgreSQL 18 startup fixes

---

## Symptom

The container is running and `docker ps` shows the port as mapped:

```
CONTAINER ID   IMAGE                         PORTS                                         NAMES
7a16d0f833bb   perfmem-pgvector-age:latest   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp   perfmem-pgvector-age
```

But any attempt to connect from the macOS host fails:

```
psql: error: connection to server at "localhost" (::1), port 5432 failed: Connection refused
    Is the server running on that host and accepting TCP/IP connections?
connection to server at "localhost" (127.0.0.1), port 5432 failed: Connection refused
    Is the server running on that host and accepting TCP/IP connections?
```

And `lsof` shows nothing listening on the port:

```bash
lsof -i :5432
# (no output)
```

The container itself is healthy — you can connect directly via `docker exec`:

```bash
docker exec perfmem-pgvector-age psql -U perfadmin -d perfmemory -c "SELECT count(*) FROM debug_sessions;"
# Returns results normally
```

---

## Cause

Rancher Desktop on macOS does **not** use Docker Desktop's proxy daemon for port
forwarding. Instead, it routes all container port forwards through an SSH tunnel managed
by the **Lima host agent** (`limactl hostagent`).

When a container port is detected in the Lima VM, the host agent runs an SSH command
to add a new forward to the existing SSH multiplexer:

```
ssh ... -O forward -L 0.0.0.0:5432:0.0.0.0:5432 ... 127.0.0.1
```

This command silently fails with `exit status 255`. The Lima host agent logs a warning
but treats it as non-fatal:

```json
{
  "error": "failed to run [ssh ... -O forward -L 0.0.0.0:5432:0.0.0.0:5432 ...]: exit status 255",
  "level": "warning",
  "msg": "failed to set up forwarding tcp port 5432 (negligible if already forwarded)"
}
```

The failure occurs because macOS restricts SSH from binding a port forward to `0.0.0.0`
(all interfaces) via the SSH multiplexer control socket. The forward to `127.0.0.1`
(loopback only) succeeds where `0.0.0.0` does not.

You can confirm this by checking the Lima host agent stderr log:

```bash
grep -i "5432" "$HOME/Library/Application Support/rancher-desktop/lima/0/ha.stderr.log"
```

If you see repeated `"failed to set up forwarding tcp port 5432"` entries, this is
the issue.

---

## Fix: Manually Add the Port Forward

The Lima SSH master process is already running — only the automated forward attempt
uses the wrong bind address. Run this command to manually add the forward using
`127.0.0.1` instead of `0.0.0.0`:

```bash
/usr/bin/ssh \
  -F /dev/null \
  -i "/Users/$USER/Library/Application Support/rancher-desktop/lima/_config/user" \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -o NoHostAuthenticationForLocalhost=yes \
  -o PreferredAuthentications=publickey \
  -o BatchMode=yes \
  -o IdentitiesOnly=yes \
  -o GSSAPIAuthentication=no \
  -S "/Users/$USER/Library/Application Support/rancher-desktop/lima/0/ssh.sock" \
  -o User=$USER \
  -T -O forward -L "127.0.0.1:5432:127.0.0.1:5432" \
  -p 64494 127.0.0.1 --
```

After running this, verify the port is now listening:

```bash
lsof -i :5432
# Expected output:
# COMMAND   PID   USER   FD   TYPE  DEVICE SIZE/OFF NODE NAME
# ssh     XXXXX  <user>  10u  IPv4  ...      0t0   TCP  localhost:postgresql (LISTEN)
```

Then confirm the database is reachable from the host:

```bash
PGPASSWORD='your_password' psql -h 127.0.0.1 -p 5432 -U perfadmin -d perfmemory -c "SELECT 1;"
```

---

## When This Happens

This issue typically surfaces after:

- **macOS sleep/wake** — The Lima VM resumes and container ports are re-detected, but
  the automated forward re-registration fails.
- **Container restart** — Stopping and starting the container triggers Lima to re-register
  the port forward, which fails again.
- **Rancher Desktop restart** — A fresh Rancher Desktop startup re-establishes the SSH
  master but the first port forward attempt for `0.0.0.0` still fails.

The container does **not** need to be restarted. The Lima VM and SSH master are healthy;
only the port forward entry is missing.

---

## Verifying the SSH Master is Running

Before running the fix command, confirm the SSH master is alive:

```bash
/usr/bin/ssh \
  -S "/Users/$USER/Library/Application Support/rancher-desktop/lima/0/ssh.sock" \
  -O check 127.0.0.1 2>&1
# Expected: Master running (pid=XXXXX)
```

If the master is **not** running, restart Rancher Desktop first, then apply the fix.

---

## Checking the Lima Host Agent Log

The full port forwarding event history is in the Lima host agent log:

```bash
# Show all port 5432 forwarding events
grep "5432" "$HOME/Library/Application Support/rancher-desktop/lima/0/ha.stderr.log"

# Show the last 20 log lines
tail -20 "$HOME/Library/Application Support/rancher-desktop/lima/0/ha.stderr.log"
```

Expected healthy output (when forwarding is working) would show no error lines for port
5432. The presence of repeated `"failed to set up forwarding tcp port 5432"` warnings
confirms this issue.

---

## Notes

- This is a macOS-side SSH restriction, not a Rancher Desktop bug per se. Linux users
  running Rancher Desktop do not experience this issue.
- Restarting Rancher Desktop does **not** permanently fix the issue — the manual forward
  command must be re-run each time the container is started or the machine is woken from
  sleep, until Rancher Desktop updates its Lima port forwarding logic.
- The `~/.ssh/config` permissions on the macOS host are **irrelevant** to this issue.
  Lima's SSH commands all use `-F /dev/null` and bypass `~/.ssh/config` entirely.
- The `docker ps` port mapping display (`0.0.0.0:5432->5432/tcp`) will always show as
  mapped regardless of whether the SSH forward is actually working. Use `lsof -i :5432`
  as the authoritative check.
