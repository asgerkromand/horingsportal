from openai import OpenAI
import os
import base64
from pydantic import BaseModel
from pathlib import Path
import json
import ast
VLLM_API_URL = "http://10.84.10.216:8899/v1/chat/completions"
IMAGE_DIR = "/projects/main_compute-AUDIT/people/crm406/data/hoering_photos"
MODEL_NAME = "unsloth/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit"
INSTRUCTION_TEXT = (
    "Assess whether these images represents a view in response to a political consultation document. Be aware of words such as 'høringssvar' og 'høringsvar'. It could also be 'bemærkning*'"
    "The output should be a list and the value being a 1 for True and 0 for False, and 2 if you unsure of to classify an image (e.g. [1,0,1,2,0]). The images are:"
)
TEMPERATURE = 0.0
TOP_P = 1.0
MAX_TOKENS = 512

class ImageClassificationResponse(BaseModel):
    image_path: str
    is_response: str

client = OpenAI(
    base_url="http://10.84.10.216:8899/v1",
    api_key="bob",
)
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def build_payload(image_paths):
    image_messages = [{"type": "text", "text": INSTRUCTION_TEXT}]

    picture_no = 0
    for path in image_paths:
        picture_no += 1
        abs_path = os.path.abspath(path)
        base64_image = encode_image(abs_path)
        print(f"Encoding image {picture_no} of {len(image_paths)}: {abs_path}")

        image_messages.append({
            "type": "image_url",
            "image_url": {
                'url':f"data:image/jpeg;base64,{base64_image}",
            }
        })

    messages = [
        {
            "role": "system",
            "content": "You are a professional assistant, speaking proficient Danish, in recognizing, when an image represents an formal answer to a political consultation document."
        },
        {
            "role": "user",
            "content": image_messages
        }
    ]

    return {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS
    }

def main():
    image_paths = sorted([
        os.path.join(IMAGE_DIR, f)
        for f in os.listdir(IMAGE_DIR)
        if f.lower().endswith(".png")
    ])

    if not image_paths:
        print("No PNG images found in the folder.")
        return

    print(f"📤 Sending {len(image_paths)} image(s) to vLLM server...\n")

    payload = build_payload(image_paths)

    chat_response = client.chat.completions.create(
        **payload,
        ).choices[0].message.content
    
    response_list = ast.literal_eval(chat_response)
    
    print(f"Chat response: {chat_response}")
    
    chat_response_dict = {}
    for i, image_path in enumerate(image_paths):
        image_path = os.path.abspath(image_path)
        is_response = response_list[i]
        chat_response_dict[image_path] = is_response
    
    # Save as jsonl in output folder
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "image_classification_results.jsonl"
    with open(output_file, "w") as f:
        f.write(json.dumps(chat_response_dict) + "\n")
        
if __name__ == "__main__":
    main()