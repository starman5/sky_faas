import os
from google.cloud import storage
from tensorflow.keras.applications.resnet50 import ResNet50, preprocess_input, decode_predictions
from tensorflow.keras.preprocessing import image
import numpy as np

# Initialize the ResNet50 model
model = ResNet50(weights='imagenet')

def predict_from_storage(data, context):
    """Background Cloud Function to be triggered by Cloud Storage.
       This function is triggered when a file is uploaded to the specified bucket.

    Args:
        data (dict): The Cloud Functions event payload.
        context (google.cloud.functions.Context): Metadata of triggering event.
    """
    storage_client = storage.Client()
    bucket_name = data['bucket']
    file_name = data['name']

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob.download_to_filename('/tmp/' + file_name)

    # Load and preprocess the image
    img = image.load_img('/tmp/' + file_name, target_size=(224, 224))
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = preprocess_input(img_array)

    # Perform inference
    predictions = model.predict(img_array)
    decoded_predictions = decode_predictions(predictions, top=3)[0]

    # Process and print the predictions
    for _, label, confidence in decoded_predictions:
        print(f"Label: {label}, Confidence: {confidence}")
