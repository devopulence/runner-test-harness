# Unused Files Inventory

Generated: 2025-01-08

This document lists all files that are NOT actively used by the main application (`run_tests.py`).

---

## Summary

| Category | Count |
|----------|-------|
| Deprecated Python Scripts | 8 |
| Unused Analysis/Debug Scripts | 9 |
| Unused Test Workflows | 5 |
| Unused/Outdated Documentation | 10 |
| Unused Configuration | 1 |
| Terraform Infrastructure (separate) | 7 |
| **TOTAL** | **40** |

---

## Deprecated Python Scripts (8 files)

Old framework replaced by `run_tests.py` + `src/orchestrator/`:

| File | Replaced By |
|------|-------------|
| `dispatcher.py` | `main.py` (trigger_workflow_dispatch) |
| `config_manager.py` | `src/orchestrator/environment_switcher.py` |
| `metrics_collector.py` | `src/orchestrator/enhanced_metrics.py` |
| `test_harness.py` | `run_tests.py` + `src/orchestrator/scenario_runner.py` |
| `quick_test.py` | `run_tests.py -p validation` |
| `test_4_runners.py` | `run_tests.py -e aws_ecs` |
| `test_ecs_simple.py` | `run_tests.py -e aws_ecs` |
| `demonstrate_4_runner_limit.py` | `run_tests.py` with profiles |

---

## Unused Analysis/Debug Scripts (9 files)

Functionality now integrated into main flow:

| File | Status |
|------|--------|
| `analyze_test_results.py` | Integrated into run_tests.py |
| `analyze_specific_test.py` | Manual tool, not in main flow |
| `generate_report.py` | Replaced by scenario_runner.generate_report() |
| `capture_current_metrics.py` | Replaced by workflow_tracker |
| `debug_tracking.py` | Debugging only |
| `debug_single_workflow.py` | Debugging only |
| `demonstrate_test_tracking.py` | Demo script |
| `test_tracking_integration.py` | Integration test |
| `wait_and_analyze.py` | Replaced by scenario_runner wait logic |

---

## Unused Test Workflows (5 files)

In `test_workflows/` directory - not referenced in configs:

- `test_workflows/simple_test.yml`
- `test_workflows/complex_test.yml`
- `test_workflows/medium_test.yml`
- `test_workflows/parallel_jobs.yml`
- `test_workflows/data_processing.yml`

**Note**: `test_workflows/runner_test.yml` IS referenced in some docs but not actively used.

---

## Unused/Outdated Documentation (10 files)

| File | Replaced By |
|------|-------------|
| `3_DAY_SPRINT_PLAN.md` | Historical - outdated |
| `HOW_4_RUNNER_SIMULATION_WORKS.md` | Environment configs |
| `RUN_4_RUNNER_TESTS.md` | `docs/USER_GUIDE.md` |
| `RUNNER_LIMITS.md` | `RUNNER_JOB_CONSTRAINTS.md` |
| `RUNNER_JOB_CONSTRAINTS.md` | Content in other docs |
| `TEST_HARNESS_README.md` | `docs/USER_GUIDE.md` |
| `TESTING_STRATEGIES.md` | `docs/TEST_CONFIGURATIONS.md` |
| `SETUP_GUIDE.md` | `docs/USER_GUIDE.md` |
| `ARCHITECTURE.md` | Partially outdated |
| `ECS_FARGATE_TESTING_STRATEGY.md` | Environment configs |

---

## Unused Configuration (1 file)

| File | Replaced By |
|------|-------------|
| `config.yaml` | `config/base_config.yaml` + `config/environments/*.yaml` |

---

## Terraform Infrastructure (7 files)

These are for AWS infrastructure deployment - separate concern from Python app:

- `terraform/00-provider.tf`
- `terraform/01-network.tf`
- `terraform/02-iam.tf`
- `terraform/03-secrets.tf`
- `terraform/04-ecs.tf`
- `terraform/README.md`
- `terraform/STEP_BY_STEP.md`

**Decision**: Keep if planning to deploy AWS ECS, remove if using existing infrastructure only.

---

## Actively Used Files (Reference)

### Core Application
- `run_tests.py` - Main entry point
- `main.py` - Workflow dispatch function
- `src/orchestrator/environment_switcher.py`
- `src/orchestrator/scenario_runner.py`
- `src/orchestrator/workflow_tracker.py`
- `src/orchestrator/enhanced_metrics.py`
- `src/analysis/test_specific_analyzer.py`
- `src/analysis/performance_analyzer.py`
- `src/reporting/report_generator.py`

### Configuration
- `config/base_config.yaml`
- `config/environments/aws_ecs.yaml`
- `config/environments/openshift_prod.yaml`

### Workflows
- `.github/workflows/build_job.yml` - Only active workflow

### Documentation (Current)
- `docs/USER_GUIDE.md`
- `docs/OPENSHIFT_MIGRATION.md`
- `docs/TEST_CONFIGURATIONS.md`
- `docs/TEST_SPECIFIC_ANALYSIS.md`
- `README.md`
- `CLAUDE.md`

---

## Recommended Cleanup Commands

```bash
# Remove deprecated Python scripts
rm dispatcher.py config_manager.py metrics_collector.py test_harness.py
rm quick_test.py test_4_runners.py test_ecs_simple.py demonstrate_4_runner_limit.py

# Remove unused analysis/debug scripts
rm analyze_test_results.py analyze_specific_test.py generate_report.py
rm capture_current_metrics.py debug_tracking.py debug_single_workflow.py
rm demonstrate_test_tracking.py test_tracking_integration.py wait_and_analyze.py

# Remove unused test workflows
rm -rf test_workflows/

# Remove outdated documentation
rm 3_DAY_SPRINT_PLAN.md HOW_4_RUNNER_SIMULATION_WORKS.md RUN_4_RUNNER_TESTS.md
rm RUNNER_LIMITS.md RUNNER_JOB_CONSTRAINTS.md TEST_HARNESS_README.md
rm TESTING_STRATEGIES.md SETUP_GUIDE.md ARCHITECTURE.md ECS_FARGATE_TESTING_STRATEGY.md

# Remove old config
rm config.yaml

# Optional: Remove terraform if not needed
rm -rf terraform/
```