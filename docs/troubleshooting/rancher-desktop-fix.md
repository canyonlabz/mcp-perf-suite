# Rancher Desktop Specific Fix

This guide addresses permission and file sharing issues specific to Rancher Desktop on macOS when running PostgreSQL 18 with pgvector and/or Apache AGE.

> **See also:**
> - [MacBook Troubleshooting Guide](pgvector-fix-on-macbook.md) — general PG18 startup fixes
> - [Apache AGE Installation Guide](../apache_age_installation_guide.md) — graph extension setup and TLS certificate fixes

---

## Mount Type Fix

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

If building the Apache AGE custom image fails with `server certificate verification failed` during `git clone`, this is a TLS inspection issue — not a Rancher Desktop issue. See the [Apache AGE Installation Guide — Corporate Environment Build](../apache_age_installation_guide.md#corporate-environment-build-tlsssl-certificate-issues) for the fix.
