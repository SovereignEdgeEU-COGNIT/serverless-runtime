from unittest.mock import Mock, patch
import threading
import pydantic
import pytest
import pika
import json
import time

from models.faas import ExecResponse, ExecutionMode, ExecReturnCode
from app.modules._rabbitmq_client import RabbitMQClient

RABBITMQ_HOST = "localhost"
REQUEST_QUEUE = "nature_flavour_request"
RESPONSE_QUEUE = "response_queue"

##############
# UNIT TESTS #
##############

@pytest.fixture
def rabbitmq_client():
    return RabbitMQClient(host=RABBITMQ_HOST, queue=REQUEST_QUEUE)

from unittest.mock import Mock

@patch("pika.URLParameters")
@patch("pika.BlockingConnection")
def test_connect_to_broker(mock_url_params, mock_pika, rabbitmq_client):

    # Mock the URL parameters
    mock_url_params.return_value = Mock()

    # Mock the connection and the channel
    mock_connection = Mock()
    mock_pika.return_value = mock_connection
    mock_connection.channel.return_value = Mock()
    
    # Mock the broker_logger with a mock info method
    rabbitmq_client.broker_logger = Mock()
    
    # Call the method under test
    result = rabbitmq_client._connect_to_broker()
    
    # Assert that the result is correct
    assert result == 0
    
    # Assert that the broker_logger's info method was called with the correct message
    rabbitmq_client.broker_logger.info.assert_called_with("Connected to RabbitMQ broker.")

@patch("pika.URLParameters")
@patch("pika.BlockingConnection")
def test_connect_to_broker_failure(mock_url_params, mock_pika, rabbitmq_client):

    # Mock the URL parameters
    mock_url_params.return_value = Mock()

    # Simulate a connection failure
    mock_pika.side_effect = Exception("failure")
    
    # Mock the broker_logger with an error method
    rabbitmq_client.broker_logger = Mock()
    
    # Call the method under test
    result = rabbitmq_client._connect_to_broker()
    
    # Assert that the result is -1, indicating failure
    assert result == -1
    
    # Assert that the broker_logger's error method was called with the expected message
    rabbitmq_client.broker_logger.error.assert_called_with("Connection error: failure")

@patch("requests.post")
def test_execute_callback(mock_post, rabbitmq_client):
    ch = Mock()
    method = Mock()
    properties = Mock()
    
    body = { 
        "mode": ExecutionMode.SYNC, 
        "payload": {    
            "lang": "PY", 
            "fc": "gAWVAAIAAAAAAACMF2Nsb3VkcGlja2xlLmNsb3VkcGlja2xllIwOX21ha2VfZnVuY3Rpb26Uk5QoaACMDV9idWlsdGluX3R5cGWUk5SMCENvZGVUeXBllIWUUpQoSwJLAEsASwJLAktDQwh8AHwBFwBTAJROhZQpjAF4lIwBeZSGlIxcL2hvbWUvYXB1ZW50ZS9jb2duaXQvZ2l0aHViLWRldmljZS1ydW50aW1lLXB5L2NvZ25pdC90ZXN0L2ludGVncmF0aW9uL3Rlc3RfaW50ZWdyYXRpb25fU00ucHmUjARzdW1hlEtvQwIIAZQpKXSUUpR9lE5OTnSUUpSMHGNsb3VkcGlja2xlLmNsb3VkcGlja2xlX2Zhc3SUjBJfZnVuY3Rpb25fc2V0c3RhdGWUk5RoFH2UfZQojAhfX25hbWVfX5RoDowMX19xdWFsbmFtZV9flGgOjA9fX2Fubm90YXRpb25zX1+UfZSMDl9fa3dkZWZhdWx0c19flE6MDF9fZGVmYXVsdHNfX5ROjApfX21vZHVsZV9flIwfaW50ZWdyYXRpb24udGVzdF9pbnRlZ3JhdGlvbl9TTZSMB19fZG9jX1+UTowLX19jbG9zdXJlX1+UTowXX2Nsb3VkcGlja2xlX3N1Ym1vZHVsZXOUXZSMC19fZ2xvYmFsc19flH2UdYaUhlIwLg==", 
            "fc_hash": "2eb03f11dd7e69b5194de245f56a47d03948f4f23e84ed3c7939231ce2f96753",
            "params": ["gAVLAi4=", "gAVLAy4="], 
            "app_req_id": 4993 
        },
        "request_id": "request_id"
    }

    mock_post.return_value.json.return_value = {"code": 200, "message": {"res": "success", "ret_code": ExecReturnCode.SUCCESS, "err": ""}}
    
    with patch.object(rabbitmq_client, "_send_result") as mock_send_result:
        rabbitmq_client._execute_callback(ch, method, properties, json.dumps(body))
    
    mock_post.assert_called_once_with("http://localhost:8000/v1/faas/execute-sync", json=body["payload"])
    mock_send_result.assert_called_once()
    ch.basic_ack.assert_called_once_with(delivery_tag=method.delivery_tag)

@patch("pika.BlockingConnection")
def test_send_result(mock_pika, rabbitmq_client):
    mock_channel = Mock()
    rabbitmq_client.channel = mock_channel
    response = ExecResponse(res="success", ret_code=ExecReturnCode.SUCCESS, err="")
    status_code = 200
    
    rabbitmq_client._send_result(response, status_code, "request_id")

    body = { "code": status_code, "message": json.loads(response.json()) }
    
    mock_channel.basic_publish.assert_called_once_with(
        exchange='results',
        routing_key="request_id",
        body=json.dumps(body)
    )

#####################
# INTEGRATION TESTS #
#####################

# Rabbit-mq middleware needs to be running

def setup_rabbitmq_channel():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=REQUEST_QUEUE)
    channel.queue_declare(queue=RESPONSE_QUEUE)
    channel.exchange_declare(exchange='results', exchange_type='direct')
    channel.queue_bind(exchange='results', queue=RESPONSE_QUEUE, routing_key="request_id")
    return connection, channel

@pytest.fixture(scope="module")
def rabbitmq_client():
    client = RabbitMQClient(host=RABBITMQ_HOST, queue=REQUEST_QUEUE)
    return client

@pytest.fixture(scope="module")
def rabbitmq_connection():
    connection, channel = setup_rabbitmq_channel()
    yield connection, channel
    connection.close()

def test_full_integration(rabbitmq_client, rabbitmq_connection):
    connection, channel = rabbitmq_connection

    response_message = None
    
    def on_response(ch, method, properties, body):
        nonlocal response_message
        response_message = json.loads(body)

        ch.basic_ack(delivery_tag=method.delivery_tag)

        result = pydantic.parse_obj_as(ExecResponse, response_message["message"])

        assert response_message is not None
        assert result.err == None
        assert result.ret_code == ExecReturnCode.SUCCESS
        assert result.res == "gAVLBS4="
        assert response_message["code"] == 200

        channel.stop_consuming()
    
    channel.basic_consume(queue=RESPONSE_QUEUE, on_message_callback=on_response)

    request_data = {
        "mode": ExecutionMode.SYNC,
        "payload": { 
            "lang": "PY", 
            "fc": "gAWVAAIAAAAAAACMF2Nsb3VkcGlja2xlLmNsb3VkcGlja2xllIwOX21ha2VfZnVuY3Rpb26Uk5QoaACMDV9idWlsdGluX3R5cGWUk5SMCENvZGVUeXBllIWUUpQoSwJLAEsASwJLAktDQwh8AHwBFwBTAJROhZQpjAF4lIwBeZSGlIxcL2hvbWUvYXB1ZW50ZS9jb2duaXQvZ2l0aHViLWRldmljZS1ydW50aW1lLXB5L2NvZ25pdC90ZXN0L2ludGVncmF0aW9uL3Rlc3RfaW50ZWdyYXRpb25fU00ucHmUjARzdW1hlEtvQwIIAZQpKXSUUpR9lE5OTnSUUpSMHGNsb3VkcGlja2xlLmNsb3VkcGlja2xlX2Zhc3SUjBJfZnVuY3Rpb25fc2V0c3RhdGWUk5RoFH2UfZQojAhfX25hbWVfX5RoDowMX19xdWFsbmFtZV9flGgOjA9fX2Fubm90YXRpb25zX1+UfZSMDl9fa3dkZWZhdWx0c19flE6MDF9fZGVmYXVsdHNfX5ROjApfX21vZHVsZV9flIwfaW50ZWdyYXRpb24udGVzdF9pbnRlZ3JhdGlvbl9TTZSMB19fZG9jX1+UTowLX19jbG9zdXJlX1+UTowXX2Nsb3VkcGlja2xlX3N1Ym1vZHVsZXOUXZSMC19fZ2xvYmFsc19flH2UdYaUhlIwLg==", 
            "fc_hash": "2eb03f11dd7e69b5194de245f56a47d03948f4f23e84ed3c7939231ce2f96753",
            "params": ["gAVLAi4=", "gAVLAy4="], 
            "app_req_id": 4993 
        },
        "request_id": "request_id"
    }
    
    broker_process = threading.Thread(target=rabbitmq_client.run, daemon=True)
    broker_process.start()
    
    time.sleep(2) 
    
    channel.basic_publish(
        exchange='',
        routing_key=REQUEST_QUEUE,
        body=json.dumps(request_data)
    )

    channel.start_consuming()

    
