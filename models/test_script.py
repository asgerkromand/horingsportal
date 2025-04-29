import os
import requests
import base64

# --- CONFIG ---
VLLM_API_URL = "http://10.84.10.216:8899/v1/chat/completions"
IMAGE_DIR = "/projects/main_compute-AUDIT/people/crm406/data/hoering_photos"
MODEL_NAME = "unsloth/Qwen2.5-VL-7B-Instruct-unsloth-bnb-4bit"
INSTRUCTION_TEXT = (
    "Assess whether these images represents a view in response to a political consultation document. "
    "The output should be a list equal to the number of files, with 1 for yes and 0 for no (e.g. [1,0,1,0,0]). The images are:"
)
TEMPERATURE = 0.0
TOP_P = 1.0
MAX_TOKENS = 512

def build_payload(image_paths):
    image_messages = [{"type": "text", "text": INSTRUCTION_TEXT}]

    for path in image_paths:
        abs_path = os.path.abspath(path)
        
        image_messages.append({
            "type": "image",
            "image": f"file:///{abs_path}",
        })

    messages = [
        {
            "role": "system",
            "content": "You are a professional assistant, speaking proficient Danish, in recognizing, when an image represents a 'view' in response to a political consultation document."
        },
        {
            "role": "user",
            "content": image_messages
        }
    ]

    print(messages)

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

    try:
        response = requests.post(VLLM_API_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        print("\n--- Model Output ---\n")
        print(result["choices"][0]["message"]["content"])
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP error: {e}")
        if e.response is not None:
            print("📩 Server response:\n", e.response.text)

if __name__ == "__main__":
    main()