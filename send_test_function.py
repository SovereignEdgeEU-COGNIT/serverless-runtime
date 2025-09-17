#!/usr/bin/env python3
"""
Concise script to send a test function to TestFlavour queue using the same serialization as the test code.
This runs from the same VM as the consumer, so cloudpickle versions should match.
"""

import base64
import cloudpickle
import pika
import json
import time
import sys
import os

# Add the app directory to Python path to import modules
sys.path.append('/root/serverless-runtime/app')

from modules._faas_parser import FaasParser
from models.faas import ExecutionMode

def test_function(x, y):
    """Simple test function that adds two numbers and sleeps a bit"""
    time.sleep(0.5)  # Simulate some work
    return x + y

def send_test_function(num_messages=1):
    """Send test functions to the TestFlavour queue"""
    try:
        # Initialize parser (same as test code)
        parser = FaasParser()
        
        # Serialize function using cloudpickle (same as test code)
        t_fc = base64.b64encode(cloudpickle.dumps(test_function)).decode("utf-8")
        
        # Connect to RabbitMQ (same broker as consumer)
        connection = pika.BlockingConnection(pika.URLParameters('amqp://rabbitadmin:rabbitadmin@172.20.0.3:5672'))
        channel = connection.channel()
        channel.queue_declare(queue='TestFlavour')
        
        print(f"Sending {num_messages} test function(s) to TestFlavour queue...")
        
        for i in range(num_messages):
            # Serialize parameters (same as test code)
            a_param = 5
            b_param = 3
            param_list = []
            param_list.append(parser.serialize(a_param))
            param_list.append(parser.serialize(b_param))
            
            # Create message (same format as test code)
            message = {
                "mode": ExecutionMode.SYNC,
                "payload": {
                    "lang": "PY",
                    "fc": t_fc,
                    "fc_hash": f"test_hash_{int(time.time())}_{i}",
                    "params": param_list,
                    "app_req_id": int(time.time()) + i
                },
                "request_id": f"test_request_{int(time.time())}_{i}"
            }
            
            channel.basic_publish(
                exchange='',
                routing_key='TestFlavour',
                body=json.dumps(message)
            )
            
            print(f"✓ Message {i+1}/{num_messages} sent successfully!")
            
            # Small delay between messages
            if i < num_messages - 1:
                time.sleep(0.1)
        
        connection.close()
        print(f"\n✓ All {num_messages} test function(s) sent successfully!")
        print(f"Function: {test_function.__name__}({a_param}, {b_param})")
        print(f"Expected result: {a_param + b_param}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    import argparse
    
    # Create argument parser
    parser = argparse.ArgumentParser(description="Send test functions to TestFlavour queue")
    parser.add_argument("--count", "-c", type=int, default=1, 
                       help="Number of test functions to send (default: 1)")
    
    # Parse arguments
    args = parser.parse_args()
    
    print(f"Sending {args.count} test function(s) to TestFlavour queue...")
    success = send_test_function(args.count)
    
    if success:
        print("\nCheck metrics with:")
        print("curl http://localhost:9100/metrics | grep sr_histogram_func_exec_time_seconds")
    else:
        sys.exit(1)
