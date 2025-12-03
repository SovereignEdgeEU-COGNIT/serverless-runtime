# Changelog - Inject RabbitMQ Prometheus Metrics into VM User Template
## Overview
Migrated from custom Prometheus collector pattern to direct metric instantiation for improved real-time observability and better metric semantics. The new system provides fine-grained tracking of function execution lifecycle with proper labeling.

## Why This Change?
- **Better observability**: Histograms provide percentiles, averages, and distribution instead of single point-in-time gauges
- **Real-time tracking**: Metrics update at execution start/completion rather than only on scrape
- **Fine-grained labels**: Track by VM, function hash, and request ID for better debugging
- **Reduced complexity**: Direct metric objects are simpler than custom collectors

## New Metrics

### Execution Tracking
- `function_duration_seconds` - Histogram of execution time (labels: `vm`, `fc_hash`, `app_req_id`)
- `vm_current_function` - Binary gauge (1=running, 0=idle) per function
- `vm_function_start_timestamp_seconds` - Unix timestamp when execution started
- `vm_is_executing` - Global VM busy/idle indicator

### Enhanced Histograms
- `sr_histogram_func_exec_time_seconds` - Added `function_outcome` label (success/error)
- `sr_histogram_func_input_size_bytes` - Added `function_outcome` label (success/error)

## New Functions
- `update_function_metrics_on_start()` - Initialize metrics when execution begins
- `update_function_metrics_on_completion()` - Finalize metrics when execution ends
- Enhanced `update_histogram_metrics()` with async execution support

## Deprecated (Commented Out)
The `CognitFuncExecCollector` class no longer yields most metrics:
- ~~`sr_last_func_exec_time`~~ → Replaced by `function_duration_seconds`
- ~~`sr_func_status`~~ → Replaced by `vm_current_function` + `vm_is_executing`
- ~~`sr_func_succeeded_total`~~ → Use histogram `function_outcome` labels
- ~~`sr_func_failed_total`~~ → Use histogram `function_outcome` labels

**Note**: Only `sr_func_executed_total` remains active.  `CognitFuncExecCollector` should entirely be removed in future cleanup.

## Additional notes
- **Labels**: Note label name changes (`vmid` → `vm`, added `fc_hash` and `app_req_id`)