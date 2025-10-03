import re
import time
import argparse
import signal
import sys
from app.modules._logger import CognitLogger

cognit_logger = CognitLogger()

def get_vmid():
    with open("/var/run/one-context/one_env", "r") as file_one:
        patt = "VMID="
        for l in file_one:
            if re.search(patt, l):
                vmid = l.split("=")[1].replace("\"","")
                try:
                    if 'old_vmid' in locals() and vmid != old_vmid:
                        return "-1"
                    if 'old_vmid' in locals() and vmid == old_vmid:
                        vmid = vmid.replace("\n","")
                        return vmid
                    old_vmid = vmid
                except Exception as e:
                    cognit_logger.debug(f'Error while getting VM ID: {e}')

# Get VM ID once at module level (it won't change)
VM_ID = get_vmid()

def update_vm_template_with_metrics(vmid):
    """Update VM template with execution metrics using onegate command."""
    try:
        import subprocess
        import json
        
        # Get current metrics from Prometheus
        metrics_data = get_prometheus_metrics(vmid)
        
        if metrics_data:
            # Update VM template with metrics
            for metric_name, value in metrics_data.items():
                cmd = f"onegate vm update {vmid} --data \"{metric_name}={value}\""
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    cognit_logger.debug(f"Successfully updated {metric_name}={value}")
                else:
                    cognit_logger.error(f"Failed to update {metric_name}: {result.stderr}")
        
    except Exception as e:
        cognit_logger.error(f"Error updating VM template: {e}")

def get_prometheus_metrics(vmid):
    """Get all Prometheus metrics for the given VM ID in a structured format."""
    try:
        import requests
        from prometheus_client.parser import text_string_to_metric_families
        
        # Query Prometheus metrics
        response = requests.get("http://localhost:9100/metrics", timeout=5)
        if response.status_code != 200:
            return None
            
        metrics_text = response.text
        metrics_data = {}
        
        # Parse all metrics into a structured format
        for family in text_string_to_metric_families(metrics_text):
            for sample in family.samples:

                if 'vmid' in sample.labels:
                    if sample.labels['vmid'] != str(vmid):
                        continue
                
                metric_name = sample.name
                metric_labels = sample.labels
                metric_value = sample.value
                
                app_req_id = metric_labels.get('app_req_id')
                if app_req_id is None:
                    continue
                
                if metric_labels.get('function_outcome') == 'success':
                    if 'le' in metric_labels:
                        bucket_le = metric_labels['le']
                        base_name = metric_name.replace('_bucket', '')
                        
                        if bucket_le == "+Inf":
                            metrics_data[f"{base_name}_bucket_inf_app_req_id_{app_req_id}"] = metric_value
                        else:
                            try:
                                bucket_int = int(float(bucket_le))
                                if 'exec_time' in metric_name:
                                    metrics_data[f"{base_name}_bucket_{bucket_int}s_app_req_id_{app_req_id}"] = metric_value
                                elif 'input_size' in metric_name:
                                    metrics_data[f"{base_name}_bucket_{bucket_int}b_app_req_id_{app_req_id}"] = metric_value
                            except ValueError:
                                pass 
                    else:
                        # Success metrics without 'le' label (count, sum, etc.)
                        metrics_data[f"{metric_name}_app_req_id_{app_req_id}"] = metric_value
                
                # Metrics without function_outcome label (counters, gauges, etc.)
                elif 'function_outcome' not in metric_labels:
                    metrics_data[f"{metric_name}_app_req_id_{app_req_id}"] = metric_value
        
        # Calculate and store the average execution time for success per app_req_id
        for key in list(metrics_data.keys()):
            if 'sr_histogram_func_exec_time_seconds_count_app_req_id_' in key:
                app_id = key.replace('sr_histogram_func_exec_time_seconds_count_app_req_id_', '')
                total_func_exec_count = f"sr_histogram_func_exec_time_seconds_count_app_req_id_{app_id}"
                total_func_exec_time = f"sr_histogram_func_exec_time_seconds_sum_app_req_id_{app_id}"
                
                if total_func_exec_count in metrics_data and metrics_data[total_func_exec_count] > 0:
                    metrics_data[f"sr_exec_time_success_avg_app_req_id_{app_id}"] = round(
                        metrics_data[total_func_exec_time] / metrics_data[total_func_exec_count], 3
                    )
                    cognit_logger.info(f"Average execution time for app_req_id {app_id}: {metrics_data[f'sr_exec_time_success_avg_app_req_id_{app_id}']}")
        
        cognit_logger.debug(f"Total number of metrics for VM {vmid}: {len(metrics_data.keys())}")
        return metrics_data
        
    except Exception as e:
        cognit_logger.error(f"Error getting Prometheus metrics: {e}")
        return None

def main():
    """Main function to run periodic metrics injection."""
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Periodically inject Prometheus metrics into VM template')
    parser.add_argument('--interval', type=int, default=5,
                        help='Interval in seconds between metric injections (default: 5)')
    args = parser.parse_args()
    interval = args.interval
    
    cognit_logger.info(f"Starting Prometheus metrics injection service (interval: {interval}s)")
    
    if not VM_ID or VM_ID == "-1":
        cognit_logger.error("Failed to get VM ID. Exiting.")
        sys.exit(1)
    
    # Fetch and inject metrics every X seconds
    while True:
        try:
            cognit_logger.debug(f"Fetching and injecting metrics for VM {VM_ID}")
            update_vm_template_with_metrics(VM_ID)
            
            # Sleep for the specified interval
            time.sleep(interval)
            
        except Exception as e:
            cognit_logger.error(f"Error in main loop: {e}")
            time.sleep(interval)
    
    cognit_logger.info("Metrics injection service stopped")

if __name__ == "__main__":
    main()