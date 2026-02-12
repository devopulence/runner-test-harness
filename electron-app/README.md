# Runner Test Results Viewer

Electron application for viewing and analyzing GitHub Runner performance test results.

## Prerequisites

- Node.js 22.14.0+ (company approved version)

## Setup on Corporate Mac

### 1. Clone the repo

```bash
git clone <repo-url>
cd pythonProject/electron-app
```

### 2. Handle SSL certificate issues

Corporate proxies may block npm registry connections. If you get `unable to get local issuer certificate` errors, run:

```bash
export NODE_TLS_REJECT_UNAUTHORIZED=0
```

**Note:** This disables TLS verification for the current terminal session only. Unset it after install:

```bash
unset NODE_TLS_REJECT_UNAUTHORIZED
```

### 3. Install dependencies

```bash
npm install
```

The `package.json` is configured to:
- Install **Electron 40.2.1** (exact version pinned, no caret)
- Use a **local `node-24.10.13.tgz`** file for `@types/node` to avoid Artifactory version blocks

### 4. Run the app

```bash
npm start
```

## Troubleshooting

### `@types/node` version blocked by Artifactory

The `node-24.10.13.tgz` file is committed to the repo. The `package.json` references it as `"@types/node": "file:node-24.10.13.tgz"` so npm uses the local file instead of fetching from Artifactory.

### Electron version resolves to wrong version

The Electron version is pinned to exactly `40.2.1` (no `^` prefix) to prevent npm from resolving to a newer version that may pull dependencies not available in Artifactory.

### SSL certificate errors during `npm install`

```bash
# Temporary fix - disables TLS verification for current session
export NODE_TLS_REJECT_UNAUTHORIZED=0
npm install
unset NODE_TLS_REJECT_UNAUTHORIZED
```

### App won't launch

Verify Electron installed correctly:

```bash
npx electron --version
# Should output: v40.2.1
```

## What's in the Viewer

The app auto-discovers all environment directories under `../test_results/` (e.g. `aws-ecs`, `openshift-sandbox`).

### Layout

- **Environment Bar** (header): Clickable badges for each environment - click to switch
- **Tabs**: One per test type (capacity, concurrency, load, performance, spike, stress, validation)
- **Sidebar**: Flavor selector (fast, light, medium) with success rate badges

### Per Test Run

- **KPI Cards**: Workflows, jobs, success rate, throughput, queue/exec times, runner utilization
- **Charts**: Queue vs execution time, runner utilization, queue distribution, total time trends
- **Analysis**: Capacity metrics, optimization recommendations, queue growth trends
- **Runner Distribution**: Per-runner job counts and busy time
- **Job Details**: Filterable table with timing and status per job

### Adding New Environments

Just create a new directory under `test_results/` with test result folders inside. The app picks it up automatically on next launch. Folder naming convention: `{type}_{flavor}_{date}_{time}_{hash}/`
