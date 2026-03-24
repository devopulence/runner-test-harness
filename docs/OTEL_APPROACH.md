# OpenTelemetry Approach for GitHub Actions Real-Time Monitoring

## Goal

Introduce lightweight OpenTelemetry (OTel) tracing and metrics with custom tags into shared GitHub workflows to track the real-time performance of workflows and jobs. Traces and metrics are exported to Dynatrace via OTLP for live dashboards, alerting, and capacity planning.

---

## Why OTel in GitHub Actions?

Our current monitoring (Tasks 1-4) collects data after the fact via the GitHub API. This gives us historical analysis but has limitations:

| | API-Based (Current) | OTel In-Workflow (Proposed) |
|---|---|---|
| **Timing** | After completion | Real-time during execution |
| **Queue time** | Computed from timestamps | Measured live as it happens |
| **Step-level detail** | Limited to what GitHub exposes | Custom spans around any operation |
| **Custom context** | Only GitHub API fields | Any tag we define (team, environment, cost center) |
| **Alerting** | Requires polling | Dynatrace alerts on live traces |
| **Latency** | Minutes to hours | Seconds |

The two approaches are complementary — OTel gives real-time visibility, API collection gives historical breadth.

---

## Architecture

```
GitHub Actions Workflow
┌─────────────────────────────────────────────┐
│  Job: Build                                 │
│  ┌────────────────────────────────────────┐ │
│  │ Step: otel-start                       │ │
│  │   - Create root span (workflow)        │ │
│  │   - Create job span                    │ │
│  │   - Set ghi.* tags from github context │ │
│  │   - Export span ID to env              │ │
│  └────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────┐ │
│  │ Step: Checkout                         │ │
│  │ Step: Build                            │ │
│  │ Step: Test                             │ │
│  │   (normal workflow steps)              │ │
│  └────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────┐ │
│  │ Step: otel-finish (runs: always)       │ │
│  │   - End job span                       │ │
│  │   - Set duration tags                  │ │
│  │   - Set conclusion tag                 │ │
│  │   - Export all spans via OTLP          │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
          │
          │ OTLP/HTTP (protobuf)
          ▼
┌─────────────────────┐
│     Dynatrace       │
│  - Traces           │
│  - Metrics          │
│  - Dashboards       │
│  - Alerts           │
└─────────────────────┘
```

---

## Span Structure

Each workflow run produces a trace with the following span hierarchy:

```
Workflow Run (root span)
  ├── Job: build (child span)
  │     ├── Step: checkout (child span, optional)
  │     ├── Step: compile (child span, optional)
  │     └── Step: test (child span, optional)
  ├── Job: security-scan (child span)
  │     └── Step: scan (child span, optional)
  └── Job: deploy (child span)
        └── Step: deploy-prod (child span, optional)
```

- **Workflow span**: Created in the first job, shared across jobs via trace ID
- **Job spans**: One per job, captures queue time and execution time
- **Step spans** (optional): Wrap individual steps for fine-grained timing

---

## Custom Trace Tags (ghi.* namespace)

All custom attributes use the `ghi.` prefix (GitHub Infrastructure).

### Pipeline Identity

| Tag | Source | Example |
|---|---|---|
| `ghi.pipeline.name` | `github.workflow` | `CI Build` |
| `ghi.pipeline.id` | `github.workflow_ref` | `org/repo/.github/workflows/ci.yml@refs/heads/main` |
| `ghi.pipeline.run.id` | `github.run_id` | `21945738937` |
| `ghi.pipeline.run.number` | `github.run_number` | `1450` |
| `ghi.pipeline.run.attempt` | `github.run_attempt` | `1` |

### Repository Context

| Tag | Source | Example |
|---|---|---|
| `ghi.repo.name` | `github.event.repository.name` | `pythonProject` |
| `ghi.repo.full_name` | `github.repository` | `devopulence/pythonProject` |
| `ghi.repo.org` | `github.repository_owner` | `devopulence` |
| `ghi.branch` | `github.ref_name` | `main` |
| `ghi.commit.sha` | `github.sha` | `a556946eeb03ec927124886e3836db94dc59941c` |
| `ghi.event` | `github.event_name` | `push` |
| `ghi.actor` | `github.actor` | `johndesp` |

### Job Context (on job spans)

| Tag | Source | Example |
|---|---|---|
| `ghi.job.name` | `github.job` | `build` |
| `ghi.job.id` | Set at finish | `63382699393` |
| `ghi.job.status` | Set at finish | `completed` |
| `ghi.job.conclusion` | Set at finish (`job.status`) | `success` |

### Runner Info (auto-detected at runtime)

| Tag | Source | Example |
|---|---|---|
| `ghi.runner.name` | `runner.name` | `ecs-runner-SvC3C1flez7ic` |
| `ghi.runner.type` | Derived from labels | `self-hosted` |
| `ghi.runner.os` | `runner.os` | `Linux` |
| `ghi.runner.labels` | From job config | `self-hosted,ecs-fargate,aws,linux` |
| `ghi.runner.group` | Runner group name | `Default` |
| `ghi.runner.platform` | User-provided or derived | `openshift` |

### Performance (computed at job/workflow end)

| Tag | Source | Example |
|---|---|---|
| `ghi.queue.duration_ms` | `started_at - created_at` | `6000` |
| `ghi.execution.duration_ms` | `completed_at - started_at` | `297000` |
| `ghi.total.duration_ms` | `completed_at - created_at` | `303000` |

### Step Context (on step spans, optional)

| Tag | Source | Example |
|---|---|---|
| `ghi.step.name` | Step name | `Build Phase 1 - Compilation` |
| `ghi.step.number` | Step order | `6` |
| `ghi.step.conclusion` | Set at step end | `success` |

### Organizational (user-provided via workflow inputs or env vars)

| Tag | Source | Example |
|---|---|---|
| `ghi.environment` | Workflow input or env var | `production` |
| `ghi.team` | Workflow input or env var | `platform-engineering` |
| `ghi.cost_center` | Workflow input or env var | `INFRA-001` |

---

## OTel Metrics (alongside traces)

In addition to traces, emit OTel metrics for aggregate dashboards:

| Metric | Type | Tags | Description |
|---|---|---|---|
| `ghi.workflow.duration` | Histogram | pipeline, repo, event, conclusion | End-to-end workflow time |
| `ghi.job.duration` | Histogram | job, repo, runner, conclusion | Job execution time |
| `ghi.job.queue_time` | Histogram | job, repo, runner | Time waiting for a runner |
| `ghi.workflow.count` | Counter | repo, event, conclusion | Workflow run count |
| `ghi.job.count` | Counter | repo, runner, conclusion | Job count |
| `ghi.step.duration` | Histogram | step, job, repo | Per-step timing |

These enable Dynatrace dashboards like:
- P95 queue time over time
- Workflow success rate by repo
- Runner utilization heatmap
- Build duration trends

---

## Implementation Approach

### Option A: Shared Composite Action (Recommended)

Create a reusable GitHub Action that workflows call at start and finish:

```yaml
# In any workflow:
jobs:
  build:
    runs-on: [self-hosted, linux]
    steps:
      - name: Start OTel Trace
        uses: your-org/ghi-otel-action@v1
        with:
          action: start
          dynatrace-endpoint: ${{ secrets.DT_OTLP_ENDPOINT }}
          dynatrace-token: ${{ secrets.DT_OTLP_TOKEN }}
          # Optional org tags
          team: platform-engineering
          environment: production

      - name: Checkout
        uses: actions/checkout@v4

      - name: Build
        run: make build

      - name: Test
        run: make test

      - name: End OTel Trace
        if: always()
        uses: your-org/ghi-otel-action@v1
        with:
          action: finish
```

**How it works:**
1. `start` step: Creates spans, sets all `ghi.*` tags from `github` context, writes trace/span IDs to `$GITHUB_ENV`
2. Normal steps run as usual
3. `finish` step (runs always): Ends spans, computes durations, sets conclusion, exports via OTLP

**Advantages:**
- Two lines added to any workflow
- All tags auto-populated from `github` context
- No changes to existing build steps
- Lightweight — just shell + curl to OTLP endpoint, or a small Python/Node OTel SDK

### Option B: Wrapper Workflow (for shared workflows)

For shared/reusable workflows, embed OTel into the shared workflow itself:

```yaml
# shared-build.yml (reusable workflow)
on:
  workflow_call:
    inputs:
      team:
        type: string
        default: ''
      environment:
        type: string
        default: ''

jobs:
  build:
    runs-on: [self-hosted, linux]
    steps:
      - uses: your-org/ghi-otel-action@v1
        with:
          action: start
          team: ${{ inputs.team }}
          environment: ${{ inputs.environment }}

      # ... shared build steps ...

      - uses: your-org/ghi-otel-action@v1
        if: always()
        with:
          action: finish
```

Calling workflows get tracing for free:

```yaml
# Any team's workflow
jobs:
  build:
    uses: your-org/shared-workflows/.github/workflows/shared-build.yml@v1
    with:
      team: my-team
      environment: staging
```

### Option C: Lightweight Shell-Only (No SDK)

For environments where installing packages is restricted, use pure shell + curl to send OTLP:

```bash
# Generate trace ID and span ID
TRACE_ID=$(openssl rand -hex 16)
SPAN_ID=$(openssl rand -hex 8)
START_TIME=$(date +%s%N)

# ... build steps run ...

END_TIME=$(date +%s%N)

# Send span via OTLP/HTTP JSON
curl -X POST "${DT_OTLP_ENDPOINT}/v1/traces" \
  -H "Content-Type: application/json" \
  -H "Authorization: Api-Token ${DT_TOKEN}" \
  -d '{
    "resourceSpans": [{
      "resource": {
        "attributes": [
          {"key": "service.name", "value": {"stringValue": "github-actions"}},
          {"key": "ghi.repo.full_name", "value": {"stringValue": "'${GITHUB_REPOSITORY}'"}}
        ]
      },
      "scopeSpans": [{
        "spans": [{
          "traceId": "'${TRACE_ID}'",
          "spanId": "'${SPAN_ID}'",
          "name": "'${GITHUB_WORKFLOW}'",
          "startTimeUnixNano": "'${START_TIME}'",
          "endTimeUnixNano": "'${END_TIME}'",
          "attributes": [
            {"key": "ghi.pipeline.run.id", "value": {"stringValue": "'${GITHUB_RUN_ID}'"}},
            {"key": "ghi.actor", "value": {"stringValue": "'${GITHUB_ACTOR}'"}},
            {"key": "ghi.branch", "value": {"stringValue": "'${GITHUB_REF_NAME}'"}}
          ]
        }]
      }]
    }]
  }'
```

---

## Dynatrace Integration

### OTLP Endpoint Configuration

Dynatrace accepts OTLP via:
- **SaaS**: `https://{environment-id}.live.dynatrace.com/api/v2/otlp/v1/traces`
- **Managed**: `https://{your-domain}/e/{environment-id}/api/v2/otlp/v1/traces`

Required secrets in GitHub:
- `DT_OTLP_ENDPOINT` — Dynatrace OTLP base URL
- `DT_OTLP_TOKEN` — API token with `openTelemetryTrace.ingest` and `metrics.ingest` scopes

### Dynatrace Dashboards

With the `ghi.*` tags, you can build dashboards for:

1. **CI/CD Overview**: Workflow count, success rate, avg duration by repo
2. **Queue Time Monitor**: P50/P95/P99 queue times, alert when P95 > threshold
3. **Runner Utilization**: Jobs per runner, runner type distribution
4. **Failure Analysis**: Failure rate by repo, by branch, by actor
5. **Trend Analysis**: Build duration trends over days/weeks
6. **Team View**: Filter all metrics by `ghi.team` for team-specific dashboards
7. **Capacity Planning**: Concurrent jobs over time, saturation alerts

### Alerting Examples

| Alert | Condition | Action |
|---|---|---|
| Queue time spike | `ghi.job.queue_time` P95 > 5 min for 10 min | Page oncall, investigate runner capacity |
| Failure rate increase | `ghi.workflow.count{conclusion=failure}` > 20% for 30 min | Notify team channel |
| Build duration regression | `ghi.job.duration` P50 increases > 50% vs 7-day avg | Notify repo owners |
| Runner saturation | All runners busy for > 10 min continuous | Scale up alert |

---

## Rollout Plan

### Phase 1: Proof of Concept
- Build the `ghi-otel-action` composite action
- Instrument 1-2 workflows in `pnc-sandbox`
- Verify traces appear in Dynatrace
- Validate all `ghi.*` tags are populated correctly

### Phase 2: Shared Workflow Integration
- Embed OTel into shared/reusable workflows
- Teams get tracing automatically when using shared workflows
- Build initial Dynatrace dashboards

### Phase 3: Org-Wide Rollout
- Document adoption guide for teams
- Add organizational tags (`ghi.team`, `ghi.cost_center`)
- Build alerting rules
- Combine OTel real-time data with API-based historical analysis

### Phase 4: Advanced
- Step-level spans for fine-grained bottleneck detection
- Correlate with application traces (link deployment span to app startup)
- Cost tracking per team/repo using `ghi.cost_center`

---

## Requirements

| Requirement | Detail |
|---|---|
| **Dynatrace** | OTLP ingest enabled, API token with trace/metrics ingest scopes |
| **GitHub Secrets** | `DT_OTLP_ENDPOINT`, `DT_OTLP_TOKEN` at org level |
| **Runner access** | Runners must be able to reach Dynatrace OTLP endpoint (network/proxy) |
| **Shared action repo** | Host `ghi-otel-action` in an internal repo accessible to all workflows |

---

## Relationship to Existing Monitoring

| Component | Purpose | Status |
|---|---|---|
| Task 1: Storage | JSON file storage for daily stats | Complete |
| Task 2: GitHub Client | API client with pagination/rate limiting | Complete |
| Task 3: Workflow Run Collector | Collect runs via API (historical) | Complete |
| Task 4: Job Collector | Collect jobs via API (historical) | Complete |
| **OTel Tracing** | **Real-time traces from inside workflows** | **Proposed** |
| Monitoring Dashboard | Electron app for visualizing collected data | Complete |

The API-based collection and OTel tracing serve different purposes:
- **API collection**: Broad historical analysis, backfill, org-wide sweeps
- **OTel tracing**: Real-time performance monitoring, alerting, live dashboards

Both feed into the same goal: understanding and optimizing CI/CD performance across the organization.
