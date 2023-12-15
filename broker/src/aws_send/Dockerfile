# Use an official Python runtime as a parent image
FROM public.ecr.aws/lambda/python:3.8

# Copy the earlier requirements file
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
#RUN pip install --no-cache-dir -r requirements.txt

# Copy the lambda function
COPY lambda_function.py ./

# Set the default command for the container
CMD ["lambda_function.lambda_handler"]
