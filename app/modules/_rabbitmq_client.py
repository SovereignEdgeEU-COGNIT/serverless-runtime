from models.faas import ExecResponse, ExecutionMode
from modules._logger import CognitLogger

import threading
import pydantic
import requests
import pika
import json

class RabbitMQClient:

    def __init__(self, host: str, queue: str):
        """
        Initializes the RabbitMQ broker connection parameters.

        Args:
            host (str): The hostname or IP address of the RabbitMQ broker. Defaults to 'localhost'.
            queue (str): The name of the queue to connect to. Defaults to 'flavour_queue'.
        """

        self.host = host
        self.queue = queue
        self.channel = None
        self.connection = None
        self.broker_logger = CognitLogger()
        
    def _connect_to_broker(self) -> int:
        """
        Connects to the RabbitMQ broker on the specified host.

        Returns:
            int: 0 if the connection is successful, -1 if there is an error.
        """
        try:

            params = pika.URLParameters(self.host)
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            self.broker_logger.info("Connected to RabbitMQ broker.")
            return 0
        
        except Exception as e:

            self.broker_logger.error(f"Connection error: {e}")
            return -1
        
    def run(self):
        """
        Connects to the queue and listens for incoming JSON messages.

        If the connection fails, logs an error and exits the program.

        """

        if self._connect_to_broker() == -1:

            self.broker_logger.error("Unable to connect to RabbitMQ broker. Exiting...")
            exit(-1)

        # Declare queue
        self.channel.queue_declare(queue=self.queue)
        
        # Set callback to handle incoming messages
        self.channel.basic_consume(queue=self.queue, on_message_callback=self._execute_callback)
        self.broker_logger.info("Waiting for executions...")

        # Listen indefinitely
        try: 

            self.channel.start_consuming()

        except Exception as e:

            self.broker_logger.error(f"Error in message consumption: {e}")
            exit(-1)
    
    def _execute_callback(self, ch, method, properties, body):
        """
        Callback function that processes received JSON messages.

        Args:
            ch: The RabbitMQ channel object.
            method: Provides delivery information such as the delivery tag.
            properties: Message properties including reply_to and correlation_id.
            body: The message body, expected to be a JSON-formatted string.
        """

        thread = threading.Thread(target=self._process_message, args=(ch, method, body))
        thread.daemon = True
        thread.start()

    def _process_message(self, ch, method, body):
        """
        Processes incoming messages from the RabbitMQ queue.

        Args:
            ch: The RabbitMQ channel object.
            method: Provides delivery information such as the delivery tag.
            body: The message body, expected to be a JSON-formatted string.
        """

        try:

            # Receive JSON message
            request_data = json.loads(body)
            exec_mode = request_data["mode"]
            exec_response = request_data["payload"]
            request_id = request_data["request_id"]

            # Determine execution mode
            if exec_mode == ExecutionMode.SYNC:

                uri = "http://localhost:8000/v1/faas/execute-sync"

            elif exec_mode == ExecutionMode.ASYNC:

                uri = "http://localhost:8000/v1/faas/execute-sync"  # TODO: Async executions should be handled differently

            # Send JSON to local REST API
            response = requests.post(uri, json=exec_response)
            response_data = response.json()
            status_code = response.status_code
            
            self.broker_logger.info("Response received: " + str(response_data))
            self.broker_logger.info("Of type: " + str(type(response_data)))
            
            # Parse execution response
            exec_response = pydantic.parse_obj_as(ExecResponse, response_data)
            
            # Send response to temporary queue
            self._send_result(exec_response, status_code, request_id)

        except Exception as e:

            self.broker_logger.error(f"Error processing message: {e}")

        finally:

            ch.basic_ack(delivery_tag=method.delivery_tag)
    
    def _send_result(self, response: ExecResponse, status_code: int, request_id: str):
        """
        Sends the execution result to a temporary queue.

        Args:
            response (ExecResponse): The execution response object.
            request_id (str): The name of the temporary queue where the response should be sent.
            correlation_id (str): A unique identifier for correlating requests and responses.
        """

        body = { 
            "code": status_code, 
            "message": json.loads(response.json())
        }
        
        self.broker_logger.debug("Body: " + json.dumps(body))
        self.broker_logger.debug("of type: " + str(type(body)))

        # Publish the response to the temporary queue
        self.channel.basic_publish(
            exchange='results',
            routing_key=request_id,
            body=json.dumps(body)
        )

        self.broker_logger.info("Response sent to temporary queue.")