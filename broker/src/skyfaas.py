import os
import sys
import tempfile
import shutil
import subprocess
import boto3
import base64
import time
from botocore.exceptions import ClientError
import socket
import json
import logging
from google.cloud import storage, functions_v1, logging
from google.cloud.functions_v1 import types
from google.oauth2 import service_account
import re

# AWS Lambda and ECR configurations
aws_access_key = "AKIAZKDKGJWWOUZBFIKZ"
aws_secret_key = "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"
aws_region = 'us-east-1'
aws_account_id = 640172838316

# Google Cloud configurations
SERVICE_ACCOUNT_KEY_PATH = "../data/bubbly-polygon-407112-bbd354782a2b.json"
PROJECT_ID = "bubbly-polygon-407112"
credentials = service_account.Credentials.from_service_account_file("../data/bubbly-polygon-407112-bbd354782a2b.json")

aws_dir='aws_received'
gcloud_dir='gcloud_received'

# The function being invoked
current_function = None

# The file used as input for an invocation
invocation_file = None

# The cloud decision for a function (if there is one)
function_to_cloud = {}

# The remaining invocations before making a decision
function_to_remaining_invocations = {}

# Avg duration
google_avg_duration = {}
aws_avg_duration = {}

# The last average duration, for detecting changes
google_last_avg = {}
aws_last_avg = {}

# Number of invocations
google_num_invocations = {}
aws_num_invocations = {}

def make_decision():
    num_requests = 10000000
    if current_function in aws_avg_duration:
        aws_cost = aws_avg_duration[current_function] * 0.000016667 + (num_requests / 1000000) * 0.20
    else:
        aws_cost = 100000000
    print(f"Projected AWS Cost: {aws_cost}")
    
    if current_function in google_avg_duration:
        google_cost = google_avg_duration[current_function] * 0.0000025 + (num_requests / 1000000) * 0.40
    else:
        google_cost = 10000000
    print(f"Projected Google Cost: {google_cost}")
    if aws_cost > google_cost:
        print("Chose AWS")
        function_to_cloud[current_function] = "AWS"
    else:
        print("Chose Google")
        function_to_cloud[current_function] = "Google"
    
    function_to_cloud[current_function] = "AWS"

def detect_change(percentage):
    if current_function in aws_avg_duration and current_function in aws_last_agv:
        if abs(aws_avg_duration[current_function] - aws_last_avg[current_function]) > aws_avg_duration[current_function] * (percentage/100):
            make_decision()
            return

    if current_function in google_avg_duration and current_function in google_last_agv:
        if abs(google_avg_duration[current_function] - google_last_avg[current_function]) > google_avg_duration[current_function] * (percentage/100):
            make_decision()
            return


# Server Setup and File Reception
def receive_files(server_socket, num_files=7):
    client_socket, addr = server_socket.accept()
    with client_socket:
        print(f"Connection from {addr}")

        # First, receive the command or identifier
        command = client_socket.recv(1024).decode().strip()
        print(command)

        if command == "CREATE_FUNCTION":
            if not os.path.exists(aws_dir):
                os.makedirs(aws_dir)
            if not os.path.exists(gcloud_dir):
                os.makedirs(gcloud_dir)

            for _ in range(num_files):
                file_info = client_socket.recv(1024).decode()
                print(file_info)
                file_name, file_size, file_directory = file_info.split('|')[:3]
                #print(file_directory)
                file_size = int(file_size)

                # Determine the target directory
                target_directory = aws_dir if file_directory == 'aws_send\n' else gcloud_dir
                #print(target_directory)
                file_path = os.path.join(target_directory, file_name)

                with open(file_path, 'wb') as file:
                    while file_size > 0:
                        data = client_socket.recv(min(1024, file_size))
                        if not data:
                            break
                        file.write(data)
                        file_size -= len(data)
            
        elif command == "INVOKE_FUNCTION":
            # Receive a single JPEG file
            global current_function
            current_function = client_socket.recv(1024).decode()
            file_info = client_socket.recv(1024).decode()
            print(file_info)
            file_name, file_size = file_info.split('|')[:2]
            file_size = int(file_size)
            file_path = os.path.join("./", file_name)  # Saving the file in the current directory
            global invocation_file
            invocation_file = file_name

            with open(file_path, 'wb') as file:
                while file_size > 0:
                    data = client_socket.recv(min(1024, file_size))
                    if not data:
                        break
                    file.write(data)
                    file_size -= len(data)

    return command


def create_aws():
    # Read serverless function name from info.json
    with open(os.path.join(aws_dir, 'info.json'), 'r') as json_file:
        info = json.load(json_file)
    function_name = info['name']

    # Update function metadata
    function_to_cloud[function_name] = "None"
    function_to_remaining_invocations[function_name] = 2
    google_num_invocations[function_name] = 0
    aws_num_invocations[function_name] = 0

    # Dynamic configurations based on info.json
    ecr_repository_name = "resnet50-lambda"
    image_tag = "latest"
    image_name = function_name
    BUCKET_NAME = function_name

    # AWS ECR login command
    aws_ecr_login_command = [
        "aws",
        "ecr",
        "get-login-password",
        "--region",
        aws_region,
    ]

    # Run the AWS ECR login command and capture its output
    try:
        aws_login_password = subprocess.check_output(aws_ecr_login_command, text=True).strip()
    except subprocess.CalledProcessError as e:
        print("Error running AWS ECR login command:", e)
        aws_login_password = ""

    # Check if the AWS ECR login password was retrieved successfully
    if aws_login_password:
        # Define the Docker build command
        docker_build_command = ["docker", "build", "-t", image_name, "./aws_received"]

        # Run the Docker build command
        try:
            subprocess.run(docker_build_command, check=True)
        except subprocess.CalledProcessError as e:
            print("Error running Docker build command:", e)

        # Define the Docker tag command
        docker_tag_command = [
            "docker",
            "tag",
            f"{image_name}:{image_tag}",
            f"640172838316.dkr.ecr.us-east-1.amazonaws.com/{ecr_repository_name}:{image_tag}",
        ]

        # Run the Docker tag command
        try:
            subprocess.run(docker_tag_command, check=True)
        except subprocess.CalledProcessError as e:
            print("Error running Docker tag command:", e)

        # Define the Docker push command
        docker_push_command = [
            "docker",
            "push",
            f"640172838316.dkr.ecr.us-east-1.amazonaws.com/{ecr_repository_name}:{image_tag}",
        ]

        # Run the Docker push command
        try:
            subprocess.run(docker_push_command, check=True)
        except subprocess.CalledProcessError as e:
            print("Error running Docker push command:", e)
    else:
        print("AWS ECR login password not retrieved.")

    #delete received directory
    if os.path.exists('./aws_received'):
        shutil.rmtree('./aws_received')

    time.sleep(3)

    s3_client = boto3.client(
        "s3",
        aws_access_key_id = aws_access_key,
        aws_secret_access_key = aws_secret_key,
        region_name = aws_region
    )
    lambda_client = boto3.client(
        "lambda",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )

    s3_client.create_bucket(
        ACL='private',
        Bucket=BUCKET_NAME
    )
    s3_arn = f"arn:aws:s3:::{BUCKET_NAME}"

    # Create the lambda function from the container image on ECR
    image_uri = f"640172838316.dkr.ecr.us-east-1.amazonaws.com/{ecr_repository_name}:{image_tag}"
    role_arn = "arn:aws:iam::640172838316:role/lambda-inference-role"
    response = lambda_client.create_function(
        FunctionName=function_name,
        Role=role_arn, # Ensure this is the correct role ARN
        Code={
            'ImageUri': image_uri
        },
        PackageType='Image',
        Timeout=123, # Set appropriate timeout
        MemorySize=128, # Set appropriate memory size
        Publish=True # Set to True if you want to publish this version
    )


    time.sleep(60)

    # Add an S3 trigger to the lambda function
    response = lambda_client.add_permission(
        FunctionName=function_name,
        StatementId='1',
        Action='lambda:InvokeFunction',
        Principal='s3.amazonaws.com',
        SourceArn=s3_arn,
        SourceAccount='640172838316'
    )

    time.sleep(3)

    response = s3_client.put_bucket_notification_configuration(
        Bucket=BUCKET_NAME,
        NotificationConfiguration={
            "LambdaFunctionConfigurations": [
                {
                    "LambdaFunctionArn": f"arn:aws:lambda:us-east-1:640172838316:function:{function_name}",
                    "Events": ["s3:ObjectCreated:*"]
                }
            ]
        }
    )


# Create GCS Bucket
def create_gcs_bucket(bucket_name):
    storage_client = storage.Client(
        project = PROJECT_ID,
        credentials=credentials
    )
    bucket = storage_client.bucket(bucket_name)
    if not bucket.exists():
        bucket = storage_client.create_bucket(bucket_name)
        print(f"Bucket {bucket_name} created.")
    else:
        print(f"Bucket {bucket_name} already exists.")

# Deploy Cloud Function
def deploy_cloud_function(function_name, file_directory):
    subprocess.run([
        "gcloud", "functions", "deploy", function_name,
        "--trigger-bucket", function_name,  # The bucket name is the same as the function name
        "--runtime", "python39",  # Specify the Python runtime version
        "--source", file_directory,
        "--entry-point", "my_cloud_function"  # Replace with your entry point function in main.py
    ], check=True)

def create_gcloud():
    file_directory = gcloud_dir

    with open(os.path.join(file_directory, 'info.json'), 'r') as json_file:
        info = json.load(json_file)
    function_name = info['name']

     # Create GCS Bucket
    create_gcs_bucket(function_name)

    # Deploy Cloud Function
    deploy_cloud_function(function_name, file_directory)

    #delete received directory
    if os.path.exists('./gcloud_received'):
        shutil.rmtree('./gcloud_received')

def create_function():
    create_aws()
    create_gcloud()


def upload_file_to_s3(file_path, bucket_name, object_name=None):
    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = os.path.basename(file_path)

    # Upload the file
    s3_client = boto3.client(
        's3',
        aws_access_key_id = aws_access_key,
        aws_secret_access_key = aws_secret_key,
        region_name = aws_region
    )
    try:
        response = s3_client.upload_file(file_path, bucket_name, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def upload_file_to_google(file_path, bucket_name, object_name=None):
    if object_name is None:
        object_name = os.path.basename(file_path)

    storage_client = storage.Client(
        project = PROJECT_ID,
        credentials=credentials
    )
    # Get the bucket
    bucket = storage_client.bucket(bucket_name)
    # Create a blob and upload the file
    blob = bucket.blob(object_name)

    try:
        blob.upload_from_filename(file_path)
        return True
    except Exception as e:
        print(f"Failed to upload file to GCS: {e}")
        return False

import re
import boto3
from botocore.exceptions import ClientError
import time

def get_aws_lambda_duration(function_name):
    client = boto3.client('logs', aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_key, region_name=aws_region)

    query = f"fields @timestamp, @message | filter @message like /REPORT RequestId/ | sort @timestamp desc | limit 1"
    log_group_name = f"/aws/lambda/{function_name}"

    try:
        response = client.start_query(logGroupName=log_group_name, startTime=int((time.time() - 60) * 1000), endTime=int(time.time() * 1000), queryString=query)
        query_id = response['queryId']

        # Wait for the query to complete
        for _ in range(10):  # Retry up to 10 times
            result = client.get_query_results(queryId=query_id)
            if result['status'] == 'Complete':
                print("Complete")
                print(result)
                for event in result['results']:
                    for field in event:
                        print(field)
                        if field['field'] == '@message':
                            match = re.search(r'Duration: (\d+\.\d+) ms', field['value'])
                            if match:
                                return float(match.group(1))
                break
            time.sleep(2)
    except ClientError as e:
        print(f"Error fetching Lambda duration: {e}")
        return None

    return None


def get_google_cloud_function_duration(function_name):
    logging_client = logging.Client(credentials=credentials)
    filter_str = f'resource.type="cloud_function" resource.labels.function_name="{function_name}"'

    # Look for the latest log entry
    iterator = logging_client.list_entries(filter_=filter_str, order_by=logging.DESCENDING, page_size=1)

    for entry in iterator:
        # Ensure payload is in string format
        if isinstance(entry.payload, str):
            text_payload = entry.payload
        elif isinstance(entry.payload, dict):
            # Convert the dict payload to string if needed
            text_payload = json.dumps(entry.payload)
        else:
            # For other types, convert to string
            text_payload = str(entry.payload)

        # Search for duration in the log entry
        match = re.search(r"Function execution took (\d+) ms", text_payload)
        if match:
            return int(match.group(1))
    
    return None
    
def aws_invoke_function(image_path):
    bucket_name = current_function
    upload_successful = upload_file_to_s3(image_path, bucket_name)
    if upload_successful:
        print("File uploaded successfully.")
        time.sleep(5)
        duration = get_aws_lambda_duration(current_function)
        if duration != None:
            if current_function in aws_avg_duration:
                aws_avg_duration[current_function] = ((aws_avg_duration[current_function] * aws_num_invocations[current_function]) + duration) / (aws_num_invocations[current_function] + 1)
            else:
                aws_avg_duration[current_function] = duration
            aws_num_invocations[current_function] += 1
        print(duration)
    else:
        print("File upload failed.")

def google_invoke_function(image_path):
    bucket_name = current_function
    upload_successful = upload_file_to_google(image_path, bucket_name)
    if upload_successful:
        print("File uploaded successfully.")
        duration = get_google_cloud_function_duration(current_function)
        if duration != None:
            if current_function in google_avg_duration:
                google_avg_duration[current_function] = ((google_avg_duration[current_function] * google_num_invocations[current_function]) + duration) / (google_num_invocations[current_function] + 1)
            else:
                google_avg_duration[current_function] = duration
            google_num_invocations[current_function] += 1
        print(duration)
    else:
        print("File upload failed.")


def invoke_function(image_path):
    if function_to_cloud[current_function] == "AWS":
        aws_invoke_function(image_path)

    elif function_to_cloud[current_function] == "Google":
        google_invoke_function(image_path)

    elif function_to_cloud[current_function] == "None":
        aws_invoke_function(image_path)
        google_invoke_function(image_path)

        function_to_remaining_invocations[current_function] -= 1
        
        if function_to_remaining_invocations[current_function] == 0:
            make_decision()
        

if __name__ == '__main__':
    host='0.0.0.0'
    port=12345
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((host, port))
        server_socket.listen()
        print(f"Listening on {host}:{port}")
        while True:
            command = receive_files(server_socket)

            if command == "CREATE_FUNCTION":
                create_function()
            
            elif command == "INVOKE_FUNCTION":
                invoke_function('dog2.jpeg')


