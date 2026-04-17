# Rancher Desktop Specific Fix

This guide addresses permission, file sharing, and TLS/SSL issues specific to Rancher Desktop when running PostgreSQL 18 with pgvector and/or Apache AGE.

> **See also:**
> - [MacBook Troubleshooting Guide](pgvector-fix-on-macbook.md) — general PG18 startup fixes
> - [Apache AGE Installation Guide](../apache_age_installation_guide.md) — graph extension setup and TLS certificate fixes

---

## Docker Pull 403 Forbidden on Windows (Corporate Proxy / CA Certificate Issue)

When pulling images from Docker Hub on Windows with Rancher Desktop, you may see:

```
Error response from daemon: unknown: failed to resolve reference "docker.io/pgvector/pgvector:pg18":
unexpected status from HEAD request to https://registry-1.docker.io/v2/pgvector/pgvector/manifests/pg18: 403 Forbidden
```

This is caused by corporate SSL/TLS inspection proxies (e.g., Zscaler, Netskope, Palo Alto) intercepting HTTPS connections. The proxy re-signs traffic with a corporate root CA that Rancher Desktop's WSL VM doesn't trust.

### Fix: Inject Corporate CA Certificate via File Explorer

On locked-down Windows machines where WSL terminal access is restricted, you can inject the corporate CA certificate directly through File Explorer:

1. Obtain your corporate root CA certificate (`.pem` or `.crt` format)
   - Export from Windows Certificate Manager: `certmgr.msc` → Trusted Root Certification Authorities
   - Or ask IT/Security for the proxy CA bundle
2. If the file has a `.pem` extension, rename it to `.crt`
3. Open **Windows File Explorer** and paste this path in the address bar:
   ```
   \\wsl$\rancher-desktop\usr\local\share\ca-certificates
   ```
4. Copy the `.crt` file into this folder
5. Restart Rancher Desktop
6. Verify: `docker pull pgvector/pgvector:pg18`

> **Why this works:** Rancher Desktop runs a WSL2 distribution named `rancher-desktop`. The `\\wsl$\` UNC path lets you access its filesystem from File Explorer without needing a WSL terminal. On startup, Rancher Desktop runs `update-ca-certificates` which picks up any `.crt` files in this directory.

### Alternative: Docker save/load (Immediate Workaround)

If CA certificate injection isn't possible, transfer the image offline from a machine that can pull it:

**On an unrestricted machine (e.g., macOS):**

```bash
docker pull pgvector/pgvector:pg18
docker save pgvector/pgvector:pg18 -o pgvector-pg18.tar
```

**On the Windows machine (PowerShell or cmd):**

```bash
docker load -i pgvector-pg18.tar
```

---

## Mount Type Fix on MacBooks

If `chown` doesn't work, it's often because of how Rancher Desktop handles file sharing on macOS.

1. Open Rancher Desktop Preferences.
2. Go to Virtual Machine > Mount Type.
3. Switch the mount type to `9p` (instead of `VirtioFS` or `reverse-sshfs`).
4. Restart Rancher Desktop. This often resolves "Permission Denied" errors that chown alone cannot fix on a Mac.

## Recommended 9p Settings for Postgres/pgvector

For database workloads like Postgres, these settings are the most stable:

- **Cache Mode: `mmap` (Default)**

	- _Why_: This is generally the most compatible with database file-locking mechanisms on macOS. If you experience extreme slowness, you can try loose, but it risks data corruption if the VM crashes.

- **Memory Size in KiB (msize): 128 (Default) or 1024**

	- _Why_: This is the packet size for data transfer. For database operations, increasing this to 1024 (1MB) or higher (up to 1400 in some stable tests) can improve performance for larger data writes, though the default 128 is sufficient for startup.

- **Protocol Version: 9p2000.L (Default)**

	- _Why_: The `.L` stands for Linux. Since the Rancher VM runs Linux, this version provides the best support for Linux-specific file attributes and features required by Postgres.

- **Security Model: mapped-xattr (Change from Default)**

	- _Why_: The default `none` often causes the chown errors you are seeing because it doesn't translate Mac permissions to Linux permissions correctly. `mapped-xattr` stores the Linux-side ownership (like UID 999) in extended attributes on your Mac, which often resolves "Operation not permitted" errors during container startup.

## Final Checklist for your Compose File

Even with these settings, ensure your `docker-compose.yaml` explicitly uses the postgres user ID so the container doesn't try to perform restricted chown operations on the mount.

**For pgvector only:**

```yaml
services:
  pgvectordb:
    image: pgvector/pgvector:pg18
    user: "999:999"
    volumes:
      - ./data/pgvectordb:/var/lib/postgresql/18/docker
    environment:
      - PGDATA=/var/lib/postgresql/18/docker/pgdata
    # ... rest of your config
```

**For pgvector + Apache AGE (custom build):**

```yaml
services:
  pgvectordb:
    build:
      context: .
      dockerfile: Dockerfile.pgvector-age
    image: perfmem-pgvector-age:latest
    container_name: perfmem-pgvector-age
    user: "999:999"
    volumes:
      - ./data/pgvectordb:/var/lib/postgresql/18/docker
    environment:
      - PGDATA=/var/lib/postgresql/18/docker/pgdata
    # ... rest of your config
```

> **Note:** The PG18 data directory changed to `/var/lib/postgresql/18/docker`. If upgrading from PG16, update your volume mount path accordingly.

## TLS Certificate Issues During Docker Build (Corporate Environments)

If building the Apache AGE custom image fails with `server certificate verification failed` during `git clone`, this is a TLS inspection issue — not a Rancher Desktop issue. If you've already injected the corporate CA into the WSL VM (see [Docker Pull 403 Forbidden](#docker-pull-403-forbidden-on-windows-corporate-proxy--ca-certificate-issue) above), the build-time `git clone` may still fail because the CA is trusted by the Docker daemon but not inside the build container. See the [Apache AGE Installation Guide — Corporate Environment Build](../apache_age_installation_guide.md#corporate-environment-build-tlsssl-certificate-issues) for the build-specific fix.
