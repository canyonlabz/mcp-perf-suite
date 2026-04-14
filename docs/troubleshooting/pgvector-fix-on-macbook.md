# Fix to starting up pg18 on MacBook & Rancher Desktop

This guide covers common issues when running PostgreSQL 18 (with pgvector and optionally Apache AGE) on MacBooks using Docker or Rancher Desktop.

> **See also:**
> - [pgvector Installation Guide](../pgvector_installation_guide.md) — standard installation steps
> - [Apache AGE Installation Guide](../apache_age_installation_guide.md) — graph extension setup
> - [Rancher Desktop Fix](rancher-desktop-fix.md) — mount type and file sharing fixes

---

## Step 1: Configure `docker-compose.yaml`

Use the below YAML for MacBooks and Rancher Desktop configurations.

**For pgvector only:**

```yaml
services:
  pgvectordb:
    image: pgvector/pgvector:pg18
    container_name: pgvector
    user: "999:999"
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - ./data/pgvectordb:/var/lib/postgresql/18/docker
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
      - PGDATA=/var/lib/postgresql/18/docker/pgdata
    restart: unless-stopped
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
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - ./data/pgvectordb:/var/lib/postgresql/18/docker
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
      - PGDATA=/var/lib/postgresql/18/docker/pgdata
    restart: unless-stopped
```

> **Key differences:** The AGE variant uses `build:` instead of `image:` to compile Apache AGE from source. See the [Apache AGE Installation Guide](../apache_age_installation_guide.md) for build instructions and corporate TLS certificate fixes.

## Step 2: Set chmod 777 on `docker/data` folder

In order to allow for PostgreSQL to start properly, you need to provide permissions to write to the folder and all subfolders by running the command:

```bash
cd mcp-perf-suite/docker/
sudo chmod -R 777 data/
```

## Step 3: Set chown to PostgreSQL UID/GID for `docker/data`

As a requirement for startup, PostgreSQL 18+ requires that the `data` folder and subfolders be assigned to the PostgreSQL UID/GID that the container uses internally which is `999:999`

```bash
sudo chown -R 999:999 data/
```

**NOTE:** You might need to re-run `Step 2` and `Step 3` if you are still getting an error on start-up as subfolders are created (e.g. `docker/data/pgvectordb`)

## Step 4: Run the `docker-compose` startup command

For the standard pgvector image:

```bash
docker compose up -d
```

For the pgvector + Apache AGE custom build:

```bash
docker compose -f docker-compose-mac.yaml up -d --build
```

> **Note:** The `--build` flag is only needed for the first build or when the Dockerfile changes. Subsequent starts can omit it.

## Step 5: Connect to the database

Connect using the `psql` client:

```bash
psql -h localhost -U perfadmin -d perfmemory -p 5432
```

Verify the extensions are available:

```sql
-- pgvector
SELECT * FROM pg_extension;

-- Apache AGE (if installed)
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
SELECT * FROM ag_catalog.ag_graph;
```



---

# Examples of Successful Startup

## Example 1: First time Start-up

The below is an example of the output from the command-line you would see if running in non-detached mode.

```shell
$ docker-compose -f docker-compose.yaml up
WARN[0000] No services to build                         
[+] up 2/2
 ✔ Network docker_default Created                     0.0s 
 ✔ Container pgvector     Created                     0.0s 
Attaching to pgvector
pgvector  | The files belonging to this database system will be owned by user "postgres".
pgvector  | This user must also own the server process.
pgvector  | 
pgvector  | The database cluster will be initialized with locale "en_US.utf8".
pgvector  | The default database encoding has accordingly been set to "UTF8".
pgvector  | The default text search configuration will be set to "english".
pgvector  | 
pgvector  | Data page checksums are enabled.
pgvector  | 
pgvector  | fixing permissions on existing directory /var/lib/postgresql/18/docker/pgdata ... ok
pgvector  | creating subdirectories ... ok
pgvector  | selecting dynamic shared memory implementation ... posix
pgvector  | selecting default "max_connections" ... 100
pgvector  | selecting default "shared_buffers" ... 128MB
pgvector  | selecting default time zone ... Etc/UTC
pgvector  | creating configuration files ... ok
pgvector  | running bootstrap script ... ok
pgvector  | performing post-bootstrap initialization ... ok
pgvector  | syncing data to disk ... ok
pgvector  | 
pgvector  | 
pgvector  | Success. You can now start the database server using:
pgvector  | 
pgvector  |     pg_ctl -D /var/lib/postgresql/18/docker/pgdata -l logfile start
pgvector  | 
pgvector  | initdb: warning: enabling "trust" authentication for local connections
pgvector  | initdb: hint: You can change this by editing pg_hba.conf or using the option -A, or --auth-local and --auth-host, the next time you run initdb.
pgvector  | waiting for server to start....2026-04-03 18:42:13.540 UTC [35] LOG:  starting PostgreSQL 18.3 (Debian 18.3-1.pgdg12+1) on aarch64-unknown-linux-gnu, compiled by gcc (Debian 12.2.0-14+deb12u1) 12.2.0, 64-bit
pgvector  | 2026-04-03 18:42:13.542 UTC [35] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
pgvector  | 2026-04-03 18:42:13.605 UTC [41] LOG:  database system was shut down at 2026-04-03 18:41:51 UTC
pgvector  | 2026-04-03 18:42:13.740 UTC [35] LOG:  database system is ready to accept connections
pgvector  |  done
pgvector  | server started
pgvector  | CREATE DATABASE
pgvector  | 
pgvector  | 
pgvector  | /usr/local/bin/docker-entrypoint.sh: ignoring /docker-entrypoint-initdb.d/*
pgvector  | 
pgvector  | waiting for server to shut down...2026-04-03 18:42:20.843 UTC [35] LOG:  received fast shutdown request
pgvector  | 2026-04-03 18:42:20.848 UTC [35] LOG:  aborting any active transactions
pgvector  | 2026-04-03 18:42:20.850 UTC [35] LOG:  background worker "logical replication launcher" (PID 44) exited with exit code 1
pgvector  | 2026-04-03 18:42:20.851 UTC [39] LOG:  shutting down
pgvector  | .2026-04-03 18:42:20.855 UTC [39] LOG:  checkpoint starting: shutdown immediate
pgvector  | .2026-04-03 18:42:22.954 UTC [39] LOG:  checkpoint complete: wrote 941 buffers (5.7%), wrote 3 SLRU buffers; 0 WAL file(s) added, 0 removed, 0 recycled; write=1.725 s, sync=0.291 s, total=2.104 s; sync files=303, longest=0.010 s, average=0.001 s; distance=4334 kB, estimate=4334 kB; lsn=0/1B92F48, redo lsn=0/1B92F48
pgvector  | 2026-04-03 18:42:23.068 UTC [35] LOG:  database system is shut down
pgvector  |  done
pgvector  | server stopped
pgvector  | 
pgvector  | PostgreSQL init process complete; ready for start up.
pgvector  | 
pgvector  | 2026-04-03 18:42:23.172 UTC [1] LOG:  starting PostgreSQL 18.3 (Debian 18.3-1.pgdg12+1) on aarch64-unknown-linux-gnu, compiled by gcc (Debian 12.2.0-14+deb12u1) 12.2.0, 64-bit
pgvector  | 2026-04-03 18:42:23.173 UTC [1] LOG:  listening on IPv4 address "0.0.0.0", port 5432
pgvector  | 2026-04-03 18:42:23.173 UTC [1] LOG:  listening on IPv6 address "::", port 5432
pgvector  | 2026-04-03 18:42:23.177 UTC [1] LOG:  listening on Unix socket "/var/run/postgresql/.s.PGSQL.5432"
pgvector  | 2026-04-03 18:42:23.241 UTC [57] LOG:  database system was shut down at 2026-04-03 18:42:22 UTC
pgvector  | 2026-04-03 18:42:23.386 UTC [1] LOG:  database system is ready to accept connections
pgvector  | 2026-04-03 18:47:23.343 UTC [55] LOG:  checkpoint starting: time
pgvector  | 2026-04-03 18:47:27.815 UTC [55] LOG:  checkpoint complete: wrote 37 buffers (0.2%), wrote 3 SLRU buffers; 0 WAL file(s) added, 0 removed, 0 recycled; write=4.149 s, sync=0.073 s, total=4.472 s; sync files=12, longest=0.039 s, average=0.007 s; distance=271 kB, estimate=271 kB; lsn=0/1BD6C10, redo lsn=0/1BD6BB8
```

---

## Example 2: First Time Login & Adding `pgvector` Extension

```
$ psql -h localhost -U perfadmin -d perfmemory -p 5432
Password for user perfadmin: 
psql (18.3)
Type "help" for help.

perfmemory=# CREATE EXTENSION vector;
CREATE EXTENSION
perfmemory=# SELECT * FROM pg_extension;
  oid  | extname | extowner | extnamespace | extrelocatable | extversion | extconfig | extcondition 
-------+---------+----------+--------------+----------------+------------+-----------+--------------
 13579 | plpgsql |       10 |           11 | f              | 1.0        |           | 
 16389 | vector  |       10 |         2200 | t              | 0.8.2      |           | 
(2 rows)

```

---

## Example 3: First Time Setup of Database Tables & Indexes

```
perfmemory=# CREATE TABLE IF NOT EXISTS debug_sessions (
perfmemory(#     id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
perfmemory(#     system_under_test       TEXT NOT NULL,
perfmemory(#     test_run_id             TEXT NOT NULL,
perfmemory(#     script_name             TEXT,
perfmemory(#     auth_flow_type          TEXT,
perfmemory(#     environment             TEXT,
perfmemory(#     total_iterations        INT,
perfmemory(#     final_outcome           TEXT NOT NULL,
perfmemory(#     resolution_attempt_id   UUID,
perfmemory(#     created_by              TEXT,
perfmemory(#     notes                   TEXT,
perfmemory(#     started_at              TIMESTAMPTZ NOT NULL,
perfmemory(#     completed_at            TIMESTAMPTZ,
perfmemory(#     created_at              TIMESTAMPTZ DEFAULT NOW()
perfmemory(# );
CREATE TABLE
perfmemory=# CREATE TABLE IF NOT EXISTS debug_attempts (
perfmemory(#     id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
perfmemory(#     session_id          UUID NOT NULL REFERENCES debug_sessions(id),
perfmemory(#     iteration_number    INT NOT NULL,
perfmemory(# 
perfmemory(#     -- Metadata (filtering)
perfmemory(#     error_category      TEXT,
perfmemory(#     severity            TEXT,
perfmemory(#     response_code       TEXT,
perfmemory(#     outcome             TEXT NOT NULL,
perfmemory(# 
perfmemory(#     -- Stored (returned with search results)
perfmemory(#     hostname            TEXT,
perfmemory(#     sampler_name        TEXT,
perfmemory(#     api_endpoint        TEXT,
perfmemory(#     symptom_text        TEXT NOT NULL,
perfmemory(#     diagnosis           TEXT,
perfmemory(#     fix_description     TEXT,
perfmemory(#     fix_type            TEXT,
perfmemory(#     component_type      TEXT,
perfmemory(#     manifest_excerpt    TEXT,
perfmemory(# 
perfmemory(#     -- System
perfmemory(#     embedding_model     TEXT NOT NULL,
perfmemory(#     embedding           vector(1536),
perfmemory(#     is_verified         BOOLEAN DEFAULT FALSE,
perfmemory(#     is_active           BOOLEAN DEFAULT TRUE,
perfmemory(#     confirmed_count     INT DEFAULT 1,
perfmemory(#     created_at          TIMESTAMPTZ DEFAULT NOW()
perfmemory(# );
CREATE TABLE
perfmemory=# ALTER TABLE debug_sessions
perfmemory-#     ADD CONSTRAINT fk_resolution_attempt
perfmemory-#     FOREIGN KEY (resolution_attempt_id)
perfmemory-#     REFERENCES debug_attempts(id);
ALTER TABLE
perfmemory=# CREATE INDEX IF NOT EXISTS idx_attempts_embedding
perfmemory-#     ON debug_attempts
perfmemory-#     USING hnsw (embedding vector_cosine_ops)
perfmemory-#     WITH (m = 16, ef_construction = 64);
CREATE INDEX
perfmemory=# CREATE INDEX IF NOT EXISTS idx_attempts_error_category
perfmemory-#     ON debug_attempts (error_category);
CREATE INDEX
perfmemory=# CREATE INDEX IF NOT EXISTS idx_attempts_outcome
perfmemory-#     ON debug_attempts (outcome);
CREATE INDEX
perfmemory=# CREATE INDEX IF NOT EXISTS idx_attempts_session_id
perfmemory-#     ON debug_attempts (session_id);
CREATE INDEX
perfmemory=# CREATE INDEX IF NOT EXISTS idx_attempts_hostname
perfmemory-#     ON debug_attempts (hostname);
CREATE INDEX
perfmemory=# CREATE INDEX IF NOT EXISTS idx_sessions_system
perfmemory-#     ON debug_sessions (system_under_test);
CREATE INDEX
perfmemory=# CREATE INDEX IF NOT EXISTS idx_sessions_environment
perfmemory-#     ON debug_sessions (environment);
CREATE INDEX
perfmemory=# CREATE INDEX IF NOT EXISTS idx_sessions_outcome
perfmemory-#     ON debug_sessions (final_outcome);
CREATE INDEX
```

---

## Example 4: Validate Tables & Indexes Created

```
perfmemory=# \dt
               List of tables
 Schema |      Name      | Type  |   Owner   
--------+----------------+-------+-----------
 public | debug_attempts | table | perfadmin
 public | debug_sessions | table | perfadmin
(2 rows)

perfmemory=# \d+
                                          List of relations
 Schema |      Name      | Type  |   Owner   | Persistence | Access method |    Size    | Description 
--------+----------------+-------+-----------+-------------+---------------+------------+-------------
 public | debug_attempts | table | perfadmin | permanent   | heap          | 8192 bytes | 
 public | debug_sessions | table | perfadmin | permanent   | heap          | 8192 bytes | 
(2 rows)

perfmemory=# \dx
                                      List of installed extensions
  Name   | Version | Default version |   Schema   |                     Description                      
---------+---------+-----------------+------------+------------------------------------------------------
 plpgsql | 1.0     | 1.0             | pg_catalog | PL/pgSQL procedural language
 vector  | 0.8.2   | 0.8.2           | public     | vector data type and ivfflat and hnsw access methods
(2 rows)

perfmemory=# \di
                              List of indexes
 Schema |            Name             | Type  |   Owner   |     Table      
--------+-----------------------------+-------+-----------+----------------
 public | debug_attempts_pkey         | index | perfadmin | debug_attempts
 public | debug_sessions_pkey         | index | perfadmin | debug_sessions
 public | idx_attempts_embedding      | index | perfadmin | debug_attempts
 public | idx_attempts_error_category | index | perfadmin | debug_attempts
 public | idx_attempts_hostname       | index | perfadmin | debug_attempts
 public | idx_attempts_outcome        | index | perfadmin | debug_attempts
 public | idx_attempts_session_id     | index | perfadmin | debug_attempts
 public | idx_sessions_environment    | index | perfadmin | debug_sessions
 public | idx_sessions_outcome        | index | perfadmin | debug_sessions
 public | idx_sessions_system         | index | perfadmin | debug_sessions
(10 rows)

perfmemory=# \d debug_attempts
                             Table "public.debug_attempts"
      Column      |           Type           | Collation | Nullable |      Default      
------------------+--------------------------+-----------+----------+-------------------
 id               | uuid                     |           | not null | gen_random_uuid()
 session_id       | uuid                     |           | not null | 
 iteration_number | integer                  |           | not null | 
 error_category   | text                     |           |          | 
 severity         | text                     |           |          | 
 response_code    | text                     |           |          | 
 outcome          | text                     |           | not null | 
 hostname         | text                     |           |          | 
 sampler_name     | text                     |           |          | 
 api_endpoint     | text                     |           |          | 
 symptom_text     | text                     |           | not null | 
 diagnosis        | text                     |           |          | 
 fix_description  | text                     |           |          | 
 fix_type         | text                     |           |          | 
 component_type   | text                     |           |          | 
 manifest_excerpt | text                     |           |          | 
 embedding_model  | text                     |           | not null | 
 embedding        | vector(1536)             |           |          | 
 is_verified      | boolean                  |           |          | false
 is_active        | boolean                  |           |          | true
 confirmed_count  | integer                  |           |          | 1
 created_at       | timestamp with time zone |           |          | now()
Indexes:
    "debug_attempts_pkey" PRIMARY KEY, btree (id)
    "idx_attempts_embedding" hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')
    "idx_attempts_error_category" btree (error_category)
    "idx_attempts_hostname" btree (hostname)
    "idx_attempts_outcome" btree (outcome)
    "idx_attempts_session_id" btree (session_id)
Foreign-key constraints:
    "debug_attempts_session_id_fkey" FOREIGN KEY (session_id) REFERENCES debug_sessions(id)
Referenced by:
    TABLE "debug_sessions" CONSTRAINT "fk_resolution_attempt" FOREIGN KEY (resolution_attempt_id) REFERENCES debug_attempts(id)

perfmemory=# \d debug_sessions
                                Table "public.debug_sessions"
        Column         |           Type           | Collation | Nullable |      Default      
-----------------------+--------------------------+-----------+----------+-------------------
 id                    | uuid                     |           | not null | gen_random_uuid()
 system_under_test     | text                     |           | not null | 
 test_run_id           | text                     |           | not null | 
 script_name           | text                     |           |          | 
 auth_flow_type        | text                     |           |          | 
 environment           | text                     |           |          | 
 total_iterations      | integer                  |           |          | 
 final_outcome         | text                     |           | not null | 
 resolution_attempt_id | uuid                     |           |          | 
 created_by            | text                     |           |          | 
 notes                 | text                     |           |          | 
 started_at            | timestamp with time zone |           | not null | 
 completed_at          | timestamp with time zone |           |          | 
 created_at            | timestamp with time zone |           |          | now()
Indexes:
    "debug_sessions_pkey" PRIMARY KEY, btree (id)
    "idx_sessions_environment" btree (environment)
    "idx_sessions_outcome" btree (final_outcome)
    "idx_sessions_system" btree (system_under_test)
Foreign-key constraints:
    "fk_resolution_attempt" FOREIGN KEY (resolution_attempt_id) REFERENCES debug_attempts(id)
Referenced by:
    TABLE "debug_attempts" CONSTRAINT "debug_attempts_session_id_fkey" FOREIGN KEY (session_id) REFERENCES debug_sessions(id)
```

---

# Extra Vector Dimensions Validations

**Why dimensions matter**

In `pgvector`, the dimensionality is fixed when you create the column (e.g., `vector(768)`). If you try to insert a vector with a different number of dimensions later, PostgreSQL will throw an error. It is always a good idea to verify this matches the output of your embedding model (like OpenAI's `text-embedding-3-small`, which is 1536).

## Validation 1: Using the `vector_dims` Function

```sql
SELECT vector_dims(embedding_column) FROM your_table_name LIMIT 1;
```
---

## Validation 2: Querying the System Catalogs (Advanced)

```sql
SELECT column_name, data_type, character_maximum_length 
FROM information_schema.columns 
WHERE data_type = 'user-defined' AND udt_name = 'vector' AND table_name = 'your_table_name';
```



