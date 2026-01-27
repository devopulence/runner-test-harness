# Session Context: Staleness Detection, Timeout Handling, Skipped Jobs

**Date:** January 27, 2026
**Session Focus:** Fix stale workflow status, add timeout handling, test skipped jobs filtering, improve concurrency timelines

---

## 1. Summary

### Goals
- Fix horizontal bar chart scaling for high concurrency (150+ jobs)
- Split job vs workflow concurrency into separate timelines
- Fix stale workflow status issue where API returns `in_progress` but workflow is actually completed
- Add timeout handling to mark stuck workflows as `timed_out`
- Add conditional jobs to test skipped jobs filtering

### Completed Tasks

1. **Bar Chart Scaling** - Changed from 1:1 to 5:1 scale (5 concurrent = 1 block)
   - `post_hoc_analyzer.py:628-629`

2. **Separate Job/Workflow Timelines** - Split combined chart into two distinct timelines
   - JOB CONCURRENCY TIMELINE (runner utilization)
   - WORKFLOW CONCURRENCY TIMELINE (pipelines in flight)
   - `post_hoc_analyzer.py:626-665`

3. **Staleness Detection** - Force individual fetch for workflows `in_progress` > 10 minutes
   - Detects when bulk API returns stale status
   - `workflow_tracker.py:653-681`

4. **Timeout Handling** - Mark workflows as `timed_out` after 30 minute wait
   - Sets `status: "completed"`, `conclusion: "timed_out"`
   - Counts in `failed` total with separate `timed_out` count
   - `scenario_runner.py:316-330`, `workflow_tracker.py:581-584,916-919`

5. **Conditional Jobs for Testing** - Added 2 jobs that never run to `build_job_multiple.yml`
   - `deploy-production` (condition: `deploy_prod == 'true'`)
   - `security-scan-extended` (condition: `event_name == 'schedule'`)
   - Tests skipped job filtering

### Current State
- All code changes implemented
- Workflow changes need to be committed and pushed to test skipped jobs
- AWS tests passing with 90 workflows, 180 jobs

### Key Findings
- Bulk API can return stale `in_progress` status even when workflow is completed
- 30 minute straggler wait was letting stuck workflows time out without proper accounting
- Job vs workflow concurrency are identical when jobs run sequentially (due to `needs:`)

---

## 2. Files Created/Modified

| File | Type | Changes |
|------|------|---------|
| `src/orchestrator/post_hoc_analyzer.py` | Modified | 5:1 bar scale, separate job/workflow timelines |
| `src/orchestrator/workflow_tracker.py` | Modified | Staleness detection (10 min), timed_out counting |
| `src/orchestrator/scenario_runner.py` | Modified | Mark timed_out workflows after 30 min wait |
| `.github/workflows/build_job_multiple.yml` | Modified | Added 2 conditional jobs for skipped filtering test |
| `contexts/session_2026-01-25_pagination_metrics_fixes.md` | Created | Previous session context |

### Key Code Changes

**workflow_tracker.py - Staleness Detection (lines 653-681)**
```python
# Detect stale workflows - in_progress for too long (> 10 min since dispatch)
stale_run_ids = set()
now = datetime.now(timezone.utc)
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

**scenario_runner.py - Timeout Handling (lines 316-330)**
```python
if elapsed > max_wait_minutes:
    logger.warning(f"Timeout waiting for workflows after {max_wait_minutes} minutes")
    # Mark remaining in_progress workflows as timed_out
    for tracking_id, workflow in self.tracker.tracked_workflows.items():
        if workflow.get("status") == "in_progress":
            workflow["status"] = "completed"
            workflow["conclusion"] = "timed_out"
            logger.warning(f"Workflow {run_id} timed out - marking as timed_out")
    break
```

**post_hoc_analyzer.py - Separate Timelines (lines 626-665)**
```python
# JOB CONCURRENCY TIMELINE
logger.info("JOB CONCURRENCY TIMELINE (runner utilization, scale: 5=█):")
for entry in timeline:
    bar_width = (entry["concurrent_jobs"] + 4) // 5
    ...
logger.info(f"  Peak: {max_jobs} jobs")

# WORKFLOW CONCURRENCY TIMELINE
logger.info("WORKFLOW CONCURRENCY TIMELINE (pipelines in flight, scale: 5=█):")
for entry in timeline:
    bar_width = (entry["concurrent_workflows"] + 4) // 5
    ...
logger.info(f"  Peak: {max_workflows} workflows")
```

**build_job_multiple.yml - Conditional Jobs**
```yaml
deploy-production:
  if: github.event.inputs.deploy_prod == 'true'  # Never true
  ...

security-scan-extended:
  if: github.event_name == 'schedule'  # Never true for workflow_dispatch
  ...
```

---

## 3. Open Items

| Task | Status | Next Action |
|------|--------|-------------|
| Test skipped jobs on AWS | Pending | Commit/push workflow, run test, verify 4 jobs/workflow but only 2 counted |
| Run on OpenShift with new fixes | Pending | Deploy code, verify staleness detection and timed_out handling work |
| Consider reducing staleness threshold | Optional | 10 min may be too long, could reduce to 5 min |

---

## 4. Context Dump

<details>
<summary>Session Details</summary>

### Problem: Stale Workflow Status
- **Symptom**: Harness shows 1 workflow `in_progress`, GitHub UI shows none running
- **Root Cause**: Bulk API returns cached/stale status
- **Fix**: Force individual fetch for workflows `in_progress` > 10 minutes

### Problem: Workflows Not Accounted After Timeout
- **Symptom**: After 30 min wait, stuck workflows not counted in success/failed
- **Root Cause**: Timeout just breaks loop, doesn't mark workflows
- **Fix**: Mark remaining `in_progress` as `timed_out`, count in `failed`

### Problem: Job vs Workflow Charts Identical
- **Symptom**: Both timelines show same numbers
- **Root Cause**: Sequential jobs (`needs:`) mean 1 job per workflow at any time
- **Explanation**: Charts would differ only with parallel jobs

### Test Results (AWS ECS, before workflow change)
- 90 workflows, 180 jobs (2 per workflow)
- Max 4 concurrent jobs/workflows
- Queue time: 0-17.6 min (mean 9.0 min)
- Execution time: 1.4-2.0 min (mean 1.6 min)

### Commands to Complete Setup
```bash
# Commit and push workflow changes
git add .github/workflows/build_job_multiple.yml
git commit -m "Add conditional jobs to test skipped job filtering"
git push

# Then run test to verify skipped jobs filtered
```

</details>

---

## Resume Instructions

To continue this work:
1. Commit and push the workflow changes to test skipped jobs filtering
2. Run test on AWS - verify 4 jobs per workflow but only 2 counted in metrics
3. Deploy to OpenShift and verify staleness detection + timeout handling
4. Check logs for: "Detected N stale in_progress runs" and "marking as timed_out"
