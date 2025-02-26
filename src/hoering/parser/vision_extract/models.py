# Import huggingface models
# Example: reuse your existing OpenAI setup
import base64
import os
from openai import OpenAI
from pathlib import Path

# Point to the local server
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")


# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


# Path to test images
image_path = Path(
    "/Users/asgerkromand/Library/CloudStorage/OneDrive-UniversityofCopenhagen/2. SODAS/5 horingsportal/test"
)

# Path to your image. The folder is ../../data and the five test images have the file-domains jpg.
image_paths = [image for image in image_path.iterdir() if image.suffix == ".jpg"]

# Encode all images as Base64 strings
base64_images = [encode_image(str(image)) for image in image_paths]

# Create the content dynamically
content = []
instruction = {
    "type": "text",
    "text": (
        f"I have attached {len(base64_images)} jpegs, and they represent pages continuously extracted from a pdf with responses made to a (political) hearing. The task is a binary classification task with labels 0 and 1: "
        "For each page, respond 0 if the sender is the same as for the previous page. Respond with 1 if the sender is a new one compared to the previous page. "
        "You should base your response on consistency in header and footer information, but also based on consistency in content and style."
        f"I would like you to output a list with a classification for each continous page-pair, i.e. a list of length {len(base64_images)-1}. Do not include any other information."
    ),
}
content.append(instruction)

# Iterate through Base64 images and add them to the content
for base64_image in base64_images:
    content.append(
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
        }
    )

# Contruct the prompt
messages = [
    {
        "role": "user",
        "content": content,
    }
]


# Call the OpenAI API
response = client.chat.completions.create(
    model="lmstudio-community/Qwen2-VL-7B-Instruct-GGUF",
    messages=messages,
)

# Output the response
print(response.choices[0].message)
