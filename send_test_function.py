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

def send_test_function():
    """Send a test function to the TestFlavour queue"""
    try:
        # Initialize parser (same as test code)
        parser = FaasParser()
        
        # Serialize function using cloudpickle (same as test code)
        t_fc = base64.b64encode(cloudpickle.dumps(test_function)).decode("utf-8")
        
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
                "fc_hash": f"test_hash_{int(time.time())}",
                "params": param_list,
                "app_req_id": int(time.time())
            },
            "request_id": f"test_request_{int(time.time())}"
        }
        
        # Connect to RabbitMQ and send message (same broker as consumer)
        connection = pika.BlockingConnection(pika.URLParameters('amqp://rabbitadmin:rabbitadmin@172.20.0.3:5672'))
        channel = connection.channel()
        channel.queue_declare(queue='TestFlavour')
        
        channel.basic_publish(
            exchange='',
            routing_key='TestFlavour',
            body=json.dumps(message)
        )
        
        connection.close()
        print("✓ Test function sent successfully!")
        print(f"Function: {test_function.__name__}({a_param}, {b_param})")
        print(f"Expected result: {a_param + b_param}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Sending test function to TestFlavour queue...")
    success = send_test_function()
    
    if success:
        print("\nCheck metrics with:")
        print("curl http://localhost:9100/metrics | grep sr_histogram_func_exec_time_seconds")
    else:
        sys.exit(1)
