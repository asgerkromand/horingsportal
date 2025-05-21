import base64
import json
import os
from pathlib import Path
from typing import Literal, List, Dict
from openai import OpenAI
from PIL import Image
from pydantic import BaseModel
from qwen_vl_utils import smart_resize

# To-do
# Seed: check where to set a seed

class ImageClassificationResponse(BaseModel):
    is_response: Literal[0, 1, 2]

class ImageClassifier:
    def __init__(
        self,
        image_dir=None,
        output_dir=None,
        model_name=None,
        temperature=0.0,
        top_p=1.0,
        max_tokens=100,
        instruction_path=None,
    ):
        self.VLLM_API_URL = "http://10.84.10.216:8899/v1/chat/completions"
        self.IMAGE_DIR = (
            image_dir
            or "/projects/main_compute-AUDIT/people/crm406/data/hoering_photos"
        )
        self.OUTPUT_DIR = output_dir or "output"
        self.MODEL_NAME = (
            model_name or "unsloth/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit"
        )
        self.TEMPERATURE = temperature
        self.TOP_P = top_p
        self.MAX_TOKENS = max_tokens
        self.INSTRUCTION_PATH = (
            instruction_path
            or "/projects/main_compute-AUDIT/people/crm406/src/hoering/models/instruction_prompt.txt"
        )
        self.INSTRUCTION_TEXT = self.load_instruction()

        self.client = OpenAI(
            base_url="http://10.84.10.216:8899/v1",
            api_key="bob",
        )

    def load_instruction(self):
        try:
            with open(self.INSTRUCTION_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Instruction prompt file not found: {self.INSTRUCTION_PATH}"
            )

    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def resize_image_if_needed(self, image_path, num_images=1, patch_size=28):
        max_model_tokens = 16384
        reserved_text_tokens = 400
        max_image_tokens = (max_model_tokens - reserved_text_tokens) // num_images
        max_pixels = max_image_tokens * patch_size * patch_size
        min_pixels = 128 * patch_size * patch_size

        image = Image.open(image_path)
        width, height = image.size

        new_height, new_width = smart_resize(
            height, width, min_pixels=min_pixels, max_pixels=max_pixels
        )

        if (new_width, new_height) != (width, height):
            print(
                f"🔄 Resizing {image_path} from {(width, height)} to {(new_width, new_height)}"
            )
            image = image.resize((new_width, new_height))
            image.save(image_path)

    def build_multi_image_payload(self, image_paths: List[str]):
        image_payloads = []
        for img_path in image_paths:
            self.resize_image_if_needed(img_path, num_images=len(image_paths))
            base64_img = self.encode_image(img_path)
            image_payloads.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"},
                }
            )

        return {
            "model": self.MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a professional assistant fluent in Danish, trained to recognize whether an image contains a formal response "
                        "to a political consultation (a høringssvar)."
                    ),
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": self.INSTRUCTION_TEXT}]
                    + image_payloads,
                },
            ],
            "temperature": self.TEMPERATURE,
            "top_p": self.TOP_P,
            "max_tokens": self.MAX_TOKENS,
        }

    def save_result_jsonl(self, result: Dict):
        output_dir = Path(self.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "image_classification_results.jsonl"

        with open(output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    def group_images_by_pdf(self) -> Dict[str, List[str]]:
        grouped = {}
        for file in os.listdir(self.IMAGE_DIR):
            if file.endswith(".png") and "_pdf_" in file and "combined" not in file:
                base_pdf = file.split("_pdf_")[0] + ".pdf"
                path = os.path.join(self.IMAGE_DIR, file)
                grouped.setdefault(base_pdf, []).append(path)

        # Sort and limit to first 4 pages
        for key in grouped:
            grouped[key] = sorted(grouped[key])[:4]

        return grouped

    def classify_images(self):
        image_groups = self.group_images_by_pdf()
        json_schema = ImageClassificationResponse.model_json_schema()

        if not image_groups:
            print("❗ No multi-page image sets found.")
            return

        print(f"📤 Sending {len(image_groups)} document(s) to vLLM server...\n")

        for idx, (pdf_name, image_paths) in enumerate(image_groups.items(), 1):
            print(
                f"[{idx}/{len(image_groups)}] Processing: {pdf_name} with {len(image_paths)} pages"
            )
            payload = self.build_multi_image_payload(image_paths)

            try:
                completion = self.client.chat.completions.create(
                    **payload, extra_body={"guided_json": json_schema}
                )
                content = completion.choices[0].message.content.strip()
                parsed = ImageClassificationResponse.model_validate_json(content)

                confidence = (
                    1.0 if self.TEMPERATURE == 0 else round(1 - self.TEMPERATURE, 2)
                )

                result = {
                    "pdf_path": os.path.abspath(os.path.join(self.IMAGE_DIR, pdf_name)),
                    "is_response": parsed.is_response,
                    "confidence": confidence,
                }
                print(f"✅ Result: {result}")

            except Exception as e:
                print(f"❌ Error processing {pdf_name}: {e}")
                result = {
                    "pdf_path": os.path.abspath(os.path.join(self.IMAGE_DIR, pdf_name)),
                    "is_response": -1,
                    "confidence": 0.0,
                }

            self.save_result_jsonl(result)

        print(
            f"\n📁 All results saved to: {Path(self.OUTPUT_DIR) / 'image_classification_results.jsonl'}"
        )
