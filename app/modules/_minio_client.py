from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from modules._logger import CognitLogger
import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    ConnectTimeoutError,
    ReadTimeoutError,
)

import os # For "download_files_with_prefix" method, can be deleted if method will not be used.
import json
from io import BytesIO

cognit_logger = CognitLogger()

class MinioClient:
    def __init__(self, endpoint_url, access_key, secret_key):
        """
        Initialize the MinIO client.

        :param endpoint_url: URL of the MinIO server (e.g., http://localhost:9000).
        :param access_key: Access key for authentication.
        :param secret_key: Secret key for authentication.
        """
        try:
            cognit_logger.debug("Initializing MinIO client...")
            timeout_config = Config(
                connect_timeout=5,      # seconds to establish the TCP connection
                read_timeout=10,        # seconds to wait for a byte of response
                retries={"mode": "standard"}  # better default retry/backoff behavior
            )
            self.s3_client = boto3.client(
                's3',
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=timeout_config
            )
            cognit_logger.debug("MinIO client initialized successfully.")
        except (NoCredentialsError, PartialCredentialsError) as e:
            raise ValueError("Invalid credentials") from e


    ## BUCKET level methods
    def create_bucket(self, bucket_name):
        """
        Create a bucket.

        :param bucket_name: Name of the bucket to create.
        """
        try:
            self.s3_client.create_bucket(Bucket=bucket_name)
            cognit_logger.info(f"Bucket '{bucket_name}' created successfully.")
        except ClientError as e:
            cognit_logger.error(f"Failed to create bucket: {e}")


    def list_buckets(self):
        """
        List all buckets.

        :return: List of bucket names.
        """
        try:
            cognit_logger.debug("Listing buckets...")
            response = self.s3_client.list_buckets()
            return [b['Name'] for b in response.get('Buckets', [])]
        except (ConnectTimeoutError, ReadTimeoutError, EndpointConnectionError) as e:
            cognit_logger.error(f"MinIO unreachable or timeout occurred: {e}")
            return [f"ERROR MinIO unreachable or timeout occurred: {e}"]  # or return an error message, as you prefer
        except ClientError as e:
            cognit_logger.error(f"Failed to list buckets: {e}")
            return [f"ERROR Failed to list buckets: {e}"]
    
    
    def delete_bucket(self, bucket_name):
        """
        Delete a bucket. The bucket must be empty.

        :param bucket_name: Name of the bucket to delete.
        """
        try:
            self.s3_client.delete_bucket(Bucket=bucket_name)
            cognit_logger.info(f"Bucket '{bucket_name}' deleted successfully.")
        except ClientError as e:
            cognit_logger.error(f"Failed to delete bucket: {e}")
               
    
    def enable_versioning(self, bucket_name):
        """
        Enable versioning for a bucket.

        :param bucket_name: Name of the bucket.
        """
        try:
            self.s3_client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            cognit_logger.info(f"Versioning enabled for bucket '{bucket_name}'.")
        except ClientError as e:
            cognit_logger.error(f"Failed to enable versioning: {e}")
            
            
    def set_bucket_policy(self, bucket_name, policy):
        """
        Set a policy for a bucket.

        :param bucket_name: Name of the bucket.
        :param policy: Policy document as a JSON string.
        """
        try:
            self.s3_client.put_bucket_policy(Bucket=bucket_name, Policy=policy)
            cognit_logger.info(f"Policy set for bucket '{bucket_name}'.")
        except ClientError as e:
            cognit_logger.error(f"Failed to set bucket policy: {e}")
            
    
    ### OBJECT level methods (object == everything inside a bucket (files and folders))
    def list_objects(self, bucket_name):
        """
        List all objects in a bucket.

        :param bucket_name: Name of the bucket.
        :return: List of object names.
        """
        try:
            response = self.s3_client.list_objects_v2(Bucket=bucket_name)
            objects = [obj['Key'] for obj in response.get('Contents', [])]
            return objects
        except ClientError as e:
            cognit_logger.error(f"Failed to list objects: {e}")
            return []
    
    
    def upload_object(self, bucket, objectPath, data, extraArgs=None) -> str:
        """
        Upload an object to a bucket.

        :param bucket: Name of the bucket where the object will be uploaded.
        :param objectPath: Path (key) in the bucket where the object will be stored.
        :param data: The data to be uploaded, provided as bytes.
        :param extraArgs (Optional): Additional arguments for the upload, such as metadata or ACL settings.
        :return: A success message string if the upload is successful, or the exception message if it fails.
        """
        try:
            buffer = BytesIO(data)
            self.s3_client.upload_fileobj(
                Fileobj=buffer,
                Bucket=bucket,
                Key=objectPath,
                ExtraArgs=extraArgs
            )
            cognit_logger.info(f"Uploaded {objectPath} to {bucket} successfully.")
            return f"Uploaded {objectPath} to {bucket} successfully."
        except Exception as e:
            cognit_logger.error(e)
            return e
            
            
    def download_object(self, bucket: str, key: str, download_path: str = None):
        """
        Download any object from S3/MinIO.

        :param bucket:       Name of the bucket.
        :param key:          Object key (path) in the bucket.
        :param download_path (Optional):
            Local object saving path within the Device Runtime. 
            If specified, the object is saved to this path and the path is returned.
            If None, returns the raw bytes of the object.
        :return:
            - str:  download_path, if input path was passed and it succeeded.
            - bytes: raw object data, if input path was not passed and it succeeded.
            - str: An error message if the download fails.
        """
        try:
            if download_path:
                # Saves directly to Device Runtime disk
                self.s3_client.download_file(bucket, key, download_path)
                cognit_logger.info(f"Downloaded {bucket}/{key} to {download_path}")
                return download_path
            else:
                # Fetch into memory
                resp = self.s3_client.get_object(Bucket=bucket, Key=key)
                data = resp['Body'].read()
                cognit_logger.info(f"Downloaded {bucket}/{key} as bytes ({len(data)} bytes)")
                return data

        except ClientError as e:
            cognit_logger.error(f"Failed to download {bucket}/{key}: {e}")
            return e


    def delete_object(self, bucket_name, object_name):
        """
        Delete an object from a bucket.

        :param bucket_name: Name of the bucket.
        :param object_name: Name of the object to delete.
        """
        try:
            self.s3_client.delete_object(Bucket=bucket_name, Key=object_name)
            cognit_logger.info(f"Object '{object_name}' deleted from bucket '{bucket_name}'.")
        except ClientError as e:
            cognit_logger.error(f"Failed to delete object: {e}")


    def get_object_metadata(self, bucket_name, object_name):
        """
        Retrieve metadata for an object.

        :param bucket_name: Name of the bucket.
        :param object_name: Name of the object.
        :return: Metadata of the object.
        """
        try:
            response = self.s3_client.head_object(Bucket=bucket_name, Key=object_name)
            return response['Metadata']
        except ClientError as e:
            cognit_logger.error(f"Failed to retrieve metadata: {e}")
            return None


    def copy_object(self, source_bucket, source_key, destination_bucket, destination_key):
        """
        Copy an object from one bucket to another.

        :param source_bucket: Source bucket name.
        :param source_key: Source object key.
        :param destination_bucket: Destination bucket name.
        :param destination_key: Destination object key.
        """
        try:
            copy_source = {'Bucket': source_bucket, 'Key': source_key}
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=destination_bucket,
                Key=destination_key
            )
            cognit_logger.info(f"Object '{source_key}' copied from '{source_bucket}' to '{destination_bucket}/{destination_key}'.")
        except ClientError as e:
            cognit_logger.error(f"Failed to copy object: {e}")


    # Methods to download to the Serverless Runtime's local disk
    def download_file_to_sr_disk(self, bucket_name, object_name, download_path):
        """
        Download a file from a bucket to the SR disk.

        :param bucket_name: Name of the bucket.
        :param object_name: Name of the object in the bucket.
        :param download_path: Local path to save the downloaded file.
        """
        try:
            # Extract the directory path from the file path
            directory = os.path.dirname(download_path)

            # Create the directory structure if it doesn't exist
            os.makedirs(directory, exist_ok=True)
            
            # Download the file
            self.s3_client.download_file(bucket_name, object_name, download_path)
            cognit_logger.info(f"File '{object_name}' downloaded to '{download_path}'.")
        except ClientError as e:
            cognit_logger.error(f"Failed to download file: {e}")
    
    
    def download_objects_with_prefix_to_sr_disk(
        self,
        bucket_name,
        prefix,
        target_local_directory,
        preserve_nested_structure=False
        ):
        """
        Download all files from a bucket with a specific prefix to a target_local_directory.
        If prefix is an empty string, it downloads the whole bucket.
        The behavior depends on the `preserve_nested_structure` flag. For example having this setup:

        Bucket structure:
            - project1/test/test.py
            - project1/data/record1.txt
            - project1/data/record2.txt
        Prefix: 'project1/data'


        - CaseA: preserve_nested_structure == False (default):
        Results in a flattened structure: The files are downloaded directly into `target_local_directory`:
            `
            target_local_directory/
                ├── record1.txt
                └── record2.txt
            `

        - CaseB: preserve_nested_structure ==True:
        Results in a nested structure: The full folder structure is preserved in `target_local_directory`:
            `
            target_local_directory/
                └── project1/
                    └── data/
                        ├── record1.txt
                        └── record2.txt
            `


        :param bucket_name: Name of the bucket.
        :param prefix: Prefix to filter objects (e.g., "project1" or "project1/data").
        :param target_local_directory: Local directory to store the downloaded files.
        :param preserve_nested_structure: If True, preserves the nested folder structure; otherwise, flattens the structure.
        """
        try:
            # Create the directory if it doesn't exist
            os.makedirs(target_local_directory, exist_ok=True)

            # List all objects in the bucket with the specified prefix
            objects = self.list_objects(bucket_name)
            if not objects:
                cognit_logger.info(f"No files found in bucket '{bucket_name}' with prefix '{prefix}'.")
                return

            # Filter objects that match the prefix
            filtered_objects = [obj for obj in objects if obj.startswith(prefix)]

            if not filtered_objects:
                cognit_logger.info(f"No files found with prefix '{prefix}' in bucket '{bucket_name}'.")
                return

            # Download each object
            for object_name in filtered_objects:
                if preserve_nested_structure:
                    # Preserve the full folder structure
                    local_file_path = os.path.join(target_local_directory, object_name)
                else:
                    # Flatten the structure: Use only the file name or relative path
                    relative_path = os.path.relpath(object_name, prefix)
                    local_file_path = os.path.join(target_local_directory, relative_path)

                # Create directories if the object has a folder structure
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

                # Download the object
                self.download_file(bucket_name, object_name, local_file_path)
                cognit_logger.info(f"Downloaded '{object_name}' to '{local_file_path}'.")

            cognit_logger.info(f"All objects with prefix '{prefix}' from bucket '{bucket_name}' downloaded to '{target_local_directory}'.")
        except Exception as e:
            cognit_logger.error(f"Failed to download objects with prefix '{prefix}' from bucket '{bucket_name}': {e}")
            

    