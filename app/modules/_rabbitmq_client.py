from models.faas import ExecResponse, ExecutionMode
from modules._logger import CognitLogger

import threading
import pydantic
import requests
import pika
import json
import time

class RabbitMQClient:
    """
    Thread-safe RabbitMQ consumer that delegates heavy message processing
    to background threads and maintains stable heartbeats.
    """

    def __init__(self, host: str, queue: str):
        """
        Initializes the RabbitMQ broker connection parameters.
        Args:
            host (str): The RabbitMQ broker URL (amqp://user:pass@host/vhost?heartbeat=300).
            queue (str): Queue name to consume messages from.
        """

        self.host = host
        self.queue = queue
        self.channel = None
        self.connection = None
        self.should_stop = threading.Event()
        self.broker_logger = CognitLogger()

    # ------------------- Connection Management ------------------- #

    def _connect_to_broker(self) -> int:
        """
        Connect to RabbitMQ broker with heartbeat and timeouts.

        Returns:
            int: 0 on success, -1 on failure.
        """

        try:

            params = pika.URLParameters(self.host)
            params.heartbeat = 60
            params.blocked_connection_timeout = 600

            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.queue, durable=True)

            self.broker_logger.info("Connected to RabbitMQ broker.")
            return 0

        except Exception as e:

            self.broker_logger.error(f"Connection error: {e}")
            return -1

    # ------------------- Consumer Loop ------------------- #

    def run(self):
        """
        Start consuming messages indefinitely with auto-reconnect.

        This method runs in the main thread and spawns worker threads for processing.
        """

        while not self.should_stop.is_set():

            if self._connect_to_broker() == -1:

                self.broker_logger.error("Unable to connect. Retrying in 5s...")
                time.sleep(5)
                continue

            try:

                self.channel.basic_qos(prefetch_count=1)
                self.channel.basic_consume(
                    queue=self.queue,
                    on_message_callback=self._execute_callback
                )

                self.broker_logger.info("Waiting for executions...")
                self.channel.start_consuming()

            except pika.exceptions.AMQPHeartbeatTimeout:

                self.broker_logger.warning("Missed heartbeat — reconnecting...")
                continue

            except pika.exceptions.StreamLostError:

                self.broker_logger.warning("Connection lost — reconnecting...")
                continue

            except Exception as e:

                self.broker_logger.error(f"Error in message consumption: {e}")
                time.sleep(5)
                continue

    # ------------------- Callback & Processing ------------------- #

    def _execute_callback(self, ch, method, properties, body):
        """
        Spawns a worker thread to process a message.

        Args:
            ch: Channel object.
            method: Method frame with delivery tag.
            properties: Properties of the message.
            body: Message body (bytes).
        """

        worker = threading.Thread(
            target=self._process_message, args=(ch, method, body), daemon=True
        )
        worker.start()

    def _process_message(self, ch, method, body):
        """
        Processes a single message and sends results back.
        
        Args:
            ch: Channel object.
            method: Method frame with delivery tag.
            body: Message body (bytes).
        """
        try:
            request_data = json.loads(body)
            exec_mode = request_data.get("mode")
            exec_payload = request_data.get("payload")
            request_id = request_data.get("request_id")

            self.broker_logger.info(f"🔧 Processing new message [ID={request_id}]")

            # Determine URI
            if exec_mode == ExecutionMode.SYNC:
                uri = "http://localhost:8000/v1/faas/execute-sync"
            else:
                uri = "http://localhost:8000/v1/faas/execute-sync"

            # Send to local API
            response = requests.post(uri, json=exec_payload)
            status_code = response.status_code
            response_data = response.json()

            self.broker_logger.info(f"Response received [{status_code}] for {request_id}")

            # Parse and send result
            exec_response = pydantic.parse_obj_as(ExecResponse, response_data)
            self._send_result(exec_response, status_code, request_id)

        except Exception as e:
            self.broker_logger.error(f"Error processing message: {e}")

        finally:

            try:
                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                self.broker_logger.warning(f"Ack failed: {e}")

    # ------------------- Thread-safe Publisher ------------------- #

    def _send_result(self, response: ExecResponse, status_code: int, request_id: str):
        """
        Sends execution result to a results exchange using a short-lived connection.
        This avoids heartbeat loss due to thread-unsafe shared connections.

        Args:
            response (ExecResponse): The execution response to send.
            status_code (int): HTTP status code of the execution.
            request_id (str): Unique identifier for the request.
        """
        try:

            params = pika.URLParameters(self.host)
            params.heartbeat = 60

            with pika.BlockingConnection(params) as conn:

                channel = conn.channel()
                body = {
                    "code": status_code,
                    "message": json.loads(response.json())
                }
                channel.basic_publish(
                    exchange="results",
                    routing_key=request_id,
                    body=json.dumps(body)
                )

            self.broker_logger.info(f"Sent response to [{request_id}]")

        except Exception as e:
            self.broker_logger.error(f"Error sending result for {request_id}: {e}")


    def stop(self):
        """
        Gracefully stops the consumer loop and closes connections.
        """

        self.should_stop.set()

        try:

            if self.channel and self.channel.is_open:
                self.channel.stop_consuming()

            if self.connection and self.connection.is_open:
                self.connection.close()

            self.broker_logger.info("Stopped RabbitMQ client gracefully.")

        except Exception as e:
            self.broker_logger.warning(f"Error during shutdown: {e}")
