import json
import boto3
import numpy as np
from PIL import Image
from io import BytesIO
from tensorflow.keras.applications.resnet50 import ResNet50, preprocess_input, decode_predictions
from tensorflow.keras.preprocessing.image import img_to_array

# Initialize model and S3 client
model = ResNet50(weights='imagenet')
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    # Extract bucket name and file key from the S3 event
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    file_key = event['Records'][0]['s3']['object']['key']

    # Get the image file from S3
    try:
        file_obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        file_content = file_obj['Body'].read()
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error getting file from S3: {str(e)}")
        }

    # Load and preprocess the image
    try:
        image = Image.open(BytesIO(file_content))
        image = image.resize((224, 224))
        image_array = img_to_array(image)
        image_array = np.expand_dims(image_array, axis=0)
        image_array = preprocess_input(image_array)
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error processing image: {str(e)}")
        }

    # Model inference
    try:
        predictions = model.predict(image_array)
        decoded_predictions = decode_predictions(predictions, top=3)[0]

        # Convert predictions to a serializable format
        response_predictions = []
        for imagenet_id, label, confidence in decoded_predictions:
            response_predictions.append({
                'imagenet_id': imagenet_id,
                'label': label,
                'confidence': float(confidence)  # Convert from float32 to float
            })

        # Create response
        response = {'predictions': response_predictions}
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error in model prediction: {str(e)}")
        }

    return {
        'statusCode': 200,
        'body': json.dumps(response)
    }
