# Troubleshooting Apache AGE-Viewer on MacBook

This guide covers common issues when installing and running Apache AGE-Viewer on macOS, particularly with Node.js 18+ and Apple Silicon (M1/M2/M3/M4).

> **See also:**
> - [Apache AGE-Viewer Guide](../apache_age_viewer_guide.md) — Cypher queries for graph visualization
> - [Apache AGE Installation Guide](../apache_age_installation_guide.md) — Database and graph schema setup
> - [MacBook Troubleshooting Guide](pgvector-fix-on-macbook.md) — PostgreSQL 18 startup fixes

---

## Issue 1: `ERR_OSSL_EVP_UNSUPPORTED` on `npm run start`

**Symptom:**

Running `npm run start` produces a long stack trace containing:

```
Error: error:0308010C:digital envelope routines::unsupported
    at new Hash (node:internal/crypto/hash:...)
    ...
    code: 'ERR_OSSL_EVP_UNSUPPORTED'
```

**Cause:**

AGE-Viewer uses an older version of Webpack that relies on legacy OpenSSL algorithms (MD4) which were disabled by default in Node.js 17+.

**Fix:**

Set the OpenSSL legacy provider flag before starting the viewer:

```bash
export NODE_OPTIONS=--openssl-legacy-provider
npm run start
```

To make this permanent, add the export to your shell profile:

```bash
echo 'export NODE_OPTIONS=--openssl-legacy-provider' >> ~/.zshrc
source ~/.zshrc
```

---

## Issue 2: `Cannot find module '@babel/runtime/helpers/interopRequireDefault'`

**Symptom:**

```
Error: Cannot find module '@babel/runtime/helpers/interopRequireDefault'
Require stack:
- .../age-viewer/backend/src/controllers/cypherController.js
- .../age-viewer/backend/src/routes/cypherRouter.js
- .../age-viewer/backend/src/app.js
- .../age-viewer/backend/src/bin/www.js
```

**Cause:**

The backend dependencies were not correctly installed during the initial `npm run setup`. The `@babel/runtime` package is missing.

**Fix:**

1. Install the missing dependency from the root `age-viewer` directory:

   ```bash
   npm install @babel/runtime
   ```

2. If the error persists, perform a clean reinstall:

   ```bash
   rm -rf node_modules package-lock.json
   cd frontend && rm -rf node_modules package-lock.json && cd ..
   cd backend && rm -rf node_modules package-lock.json && cd ..
   npm run setup
   npm run build-back
   ```

3. Then start with the OpenSSL flag:

   ```bash
   export NODE_OPTIONS=--openssl-legacy-provider
   npm run start
   ```

---

## Issue 3: `Unable to resolve path to module 'cytoscape/src/util'`

**Symptom:**

The frontend fails to compile with an error referencing `cytoscape/src/util` in `CypherResultTable.jsx`. This is a known bug in the AGE-Viewer frontend ([apache/age-viewer#184](https://github.com/apache/age-viewer/issues/184), [apache/age-viewer#187](https://github.com/apache/age-viewer/issues/187)).

**Cause:**

The code imports a `uuid` utility from an internal Cytoscape path that doesn't exist in the installed version of the `cytoscape` package.

**Fix:**

1. Install the replacement module in the frontend directory:

   ```bash
   cd frontend
   npm install react-uuid
   ```

2. Open `frontend/src/components/cypherresult/presentations/CypherResultTable.jsx` and find line 23.

   Replace:

   ```javascript
   import { uuid } from 'cytoscape/src/util';
   ```

   With:

   ```javascript
   import uuid from 'react-uuid';
   ```

3. Return to the root directory and restart:

   ```bash
   cd ..
   export NODE_OPTIONS=--openssl-legacy-provider
   npm run start
   ```

---

## Issue 4: `Backend Connection Failed` After Restart

**Symptom:**

AGE-Viewer loads in the browser but displays "Backend Connection Failed" when trying to connect to the database.

**Possible causes and fixes:**

1. **OpenSSL flag not set** — If you opened a new terminal, the `NODE_OPTIONS` variable is not set. Re-run:

   ```bash
   export NODE_OPTIONS=--openssl-legacy-provider
   npm run start
   ```

2. **Database container not running** — Verify the PostgreSQL container is up:

   ```bash
   docker ps
   ```

3. **Wrong connection details** — In the AGE-Viewer connection form, use:
   - **Connect URL:** `localhost`
   - **Connect Port:** The port mapped in your `docker-compose` file (e.g., `5432`)
   - **Database Name:** `perfmemory` (or whatever your `POSTGRES_DB` is set to)
   - **User/Password:** Your `POSTGRES_USER` and `POSTGRES_PASSWORD` values

4. **AGE not loaded in the database** — Connect via `psql` and verify:

   ```sql
   CREATE EXTENSION IF NOT EXISTS age;
   LOAD 'age';
   SET search_path = ag_catalog, "$user", public;
   SELECT * FROM ag_catalog.ag_graph;
   ```

---

## Apple Silicon Notes

- If `npm run build-back` fails with native compilation errors, ensure you have the build dependencies installed via Homebrew:

  ```bash
  brew install python@3.11
  brew install make
  ```

- Some backend packages require `node-gyp` for native compilation on M-series chips. If you see `gyp ERR!` errors, install it globally:

  ```bash
  npm install -g node-gyp
  ```

---

## Quick Start Cheatsheet

For subsequent launches after initial setup is complete:

```bash
cd age-viewer
export NODE_OPTIONS=--openssl-legacy-provider
npm run start
```

Then open [http://localhost:3000](http://localhost:3000) and connect to your database.
