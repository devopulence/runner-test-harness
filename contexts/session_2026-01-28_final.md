# Session Context: Staleness Detection, Timeout Handling, Skipped Jobs Testing

**Date:** January 28, 2026
**Session Focus:** Fix stale workflow status, add timeout handling, improve concurrency timelines, prepare skipped jobs test

---

## 1. Summary

### Goals Completed
1. Fix horizontal bar chart scaling for high concurrency (150+ jobs) - **DONE**
2. Split job vs workflow concurrency into separate timelines - **DONE**
3. Fix stale workflow status issue (API returns `in_progress` when completed) - **DONE**
4. Add timeout handling to mark stuck workflows as `timed_out` - **DONE**
5. Add conditional jobs to workflow for testing skipped job filtering - **DONE (not yet pushed)**

### Current State
- All code changes implemented and tested on AWS
- Workflow changes (`build_job_multiple.yml`) need commit/push to test skipped jobs
- OpenShift testing pending for staleness/timeout fixes

### Key Findings
- Bulk GitHub API can return stale `in_progress` status
- 10-minute staleness threshold triggers individual fetch to verify
- 30-minute timeout marks remaining workflows as `timed_out`
- Job vs workflow concurrency identical when jobs run sequentially (`needs:`)

---

## 2. Files Modified

| File | Changes |
|------|---------|
| `src/orchestrator/post_hoc_analyzer.py` | 5:1 bar scale, separate job/workflow timelines, track both concurrent_jobs and concurrent_workflows |
| `src/orchestrator/workflow_tracker.py` | Staleness detection (>10 min), timed_out counting in failed totals |
| `src/orchestrator/scenario_runner.py` | Mark timed_out workflows after 30 min wait timeout |
| `.github/workflows/build_job_multiple.yml` | Added 2 conditional jobs (deploy-production, security-scan-extended) |

---

## 3. Open Items

| Task | Priority | Next Action |
|------|----------|-------------|
| Push workflow changes | High | `git add/commit/push` build_job_multiple.yml |
| Test skipped jobs on AWS | High | Run test, verify 4 jobs/workflow but only 2 counted |
| Test on OpenShift | High | Verify staleness detection and timed_out handling |
| Dynatrace/OTEL integration | Future | User asked about this, deferred |

---

## 4. Context Dump

<details>
<summary>Key Code Changes</summary>

### Staleness Detection (workflow_tracker.py:653-681)
```python
# Detect stale workflows - in_progress for too long (> 10 min since dispatch)
stale_run_ids = set()
stale_threshold_minutes = 10

for run_id, tracking_id in run_id_to_tracking.items():
    workflow_data = self.tracked_workflows[tracking_id]
    if workflow_data.get("status") == "in_progress":
        dispatch_time = workflow_data.get("dispatch_time")
        if dispatch_time:
            age_minutes = (now - dispatch_time).total_seconds() / 60
            if age_minutes > stale_threshold_minutes:
                stale_run_ids.add(run_id)

verify_run_ids = missing_run_ids | stale_run_ids
```

### Timeout Handling (scenario_runner.py:316-330)
```python
if elapsed > max_wait_minutes:
    logger.warning(f"Timeout waiting for workflows after {max_wait_minutes} minutes")
    for tracking_id, workflow in self.tracker.tracked_workflows.items():
        if workflow.get("status") == "in_progress":
            workflow["status"] = "completed"
            workflow["conclusion"] = "timed_out"
            logger.warning(f"Workflow {run_id} timed out - marking as timed_out")
    break
```

### Separate Timelines (post_hoc_analyzer.py)
```python
# Scale: 5 concurrent = 1 block
job_bar_width = (max_jobs + 4) // 5

# JOB CONCURRENCY TIMELINE
logger.info("JOB CONCURRENCY TIMELINE (runner utilization, scale: 5=█):")

# WORKFLOW CONCURRENCY TIMELINE
logger.info("WORKFLOW CONCURRENCY TIMELINE (pipelines in flight, scale: 5=█):")
```

### Conditional Jobs (build_job_multiple.yml)
```yaml
deploy-production:
  if: github.event.inputs.deploy_prod == 'true'  # Never true

security-scan-extended:
  if: github.event_name == 'schedule'  # Never true for dispatch
```

</details>

<details>
<summary>Commands to Complete</summary>

```bash
# Push workflow changes
cd /Users/johndesposito/pnc-work/pythonProject
git add .github/workflows/build_job_multiple.yml
git commit -m "Add conditional jobs to test skipped job filtering"
git push

# Run AWS test
python -m src.orchestrator.scenario_runner --env aws-ecs --profile concurrency_max
```

</details>

---

## Resume Instructions

1. Push workflow changes to GitHub
2. Run test on AWS - expect 360 jobs (4/workflow) but 180 counted (skipped filtered)
3. Deploy code to OpenShift
4. Run OpenShift test - verify staleness detection catches stuck workflows
5. Check for log messages: "Detected N stale in_progress runs" and "marking as timed_out"