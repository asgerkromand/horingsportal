from openai import OpenAI
import os
import base64
from pydantic import BaseModel
from pathlib import Path
import json
import ast

class ImageClassifier:
    def __init__(self, image_dir=None, output_dir=None, model_name=None, temperature=0.0, top_p=1.0, max_tokens=512):
        self.VLLM_API_URL = "http://10.84.10.216:8899/v1/chat/completions"
        self.IMAGE_DIR = image_dir if image_dir is not None else "/projects/main_compute-AUDIT/people/crm406/data/hoering_photos"
        self.OUTPUT_DIR = output_dir if output_dir is not None else "output"
        self.MODEL_NAME = model_name if model_name is not None else "unsloth/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit"
        self.INSTRUCTION_TEXT = (
            "Assess whether these images represents a view in response to a political consultation document. Be aware of words such as 'høringssvar' og 'høringsvar'. It could also be 'bemærkning*'"
            "The output should be a list and the value being a 1 for True and 0 for False, and 2 if you unsure of to classify an image (e.g. [1,0,1,2,0]). The images are:"
        )
        self.TEMPERATURE = temperature
        self.TOP_P = top_p
        self.MAX_TOKENS = max_tokens

        self.client = OpenAI(
            base_url="http://10.84.10.216:8899/v1",
            api_key="bob",
        )

    class ImageClassificationResponse(BaseModel):
        image_path: str
        is_response: str

    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def build_payload(self, image_paths):
        image_messages = [{"type": "text", "text": self.INSTRUCTION_TEXT}]

        picture_no = 0
        for path in image_paths:
            picture_no += 1
            abs_path = os.path.abspath(path)
            base64_image = self.encode_image(abs_path)
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
            "model": self.MODEL_NAME,
            "messages": messages,
            "temperature": self.TEMPERATURE,
            "top_p": self.TOP_P,
            "max_tokens": self.MAX_TOKENS
        }

    def classify_images(self):
        image_paths = sorted([
            os.path.join(self.IMAGE_DIR, f)
            for f in os.listdir(self.IMAGE_DIR)
            if f.lower().endswith(".png")
        ])

        if not image_paths:
            print("No PNG images found in the folder.")
            return

        print(f"📤 Sending {len(image_paths)} image(s) to vLLM server...\n")

        payload = self.build_payload(image_paths)

        chat_response = self.client.chat.completions.create(
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
        output_dir = Path(self.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "image_classification_results.jsonl"
        with open(output_file, "w") as f:
            f.write(json.dumps(chat_response_dict) + "\n")