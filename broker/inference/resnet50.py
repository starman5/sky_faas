import tensorflow as tf
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.resnet50 import preprocess_input, decode_predictions
import numpy as np

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# Load the pre-trained ResNet-50 model
model = tf.keras.applications.ResNet50(weights='imagenet')

# Load and preprocess an example image
img_path = 'dog.jpeg'
img = image.load_img(img_path, target_size=(224, 224))
img_array = image.img_to_array(img)
img_array = np.expand_dims(img_array, axis=0)
img_array = preprocess_input(img_array)

# Perform inference
predictions = model.predict(img_array)

# Decode and print the top-3 predicted classes
decoded_predictions = decode_predictions(predictions, top=3)[0]
print("Predictions:")
for i, (imagenet_id, label, score) in enumerate(decoded_predictions):
    print(f"{i + 1}: {label} ({score:.2f})")

# Alternatively, you can get the class index with the highest probability
predicted_class_index = np.argmax(predictions)
predicted_class = decode_predictions(np.eye(1, 1000, predicted_class_index))[0][0][1]
print(f"\nPredicted class index: {predicted_class_index}")
print(f"Predicted class: {predicted_class}")
