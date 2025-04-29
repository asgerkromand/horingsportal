# SPDX-License-Identifier: Apache-2.0
"""
This example shows how to use vLLM for running offline inference with
multi-image input on vision language models for text generation,
using the chat template defined by the model.
"""
import os
from argparse import Namespace
from dataclasses import asdict
from typing import NamedTuple, Optional

from huggingface_hub import snapshot_download
from PIL.Image import Image
from transformers import AutoProcessor, AutoTokenizer

from vllm import LLM, EngineArgs, SamplingParams
from vllm.lora.request import LoRARequest
from vllm.multimodal.utils import fetch_image
from vllm.utils import FlexibleArgumentParser

QUESTION = "What is the content of each image?"
IMAGE_URLS = [
    "https://upload.wikimedia.org/wikipedia/commons/d/da/2015_Kaczka_krzy%C5%BCowka_w_wodzie_%28samiec%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/7/77/002_The_lion_king_Snyggve_in_the_Serengeti_National_Park_Photo_by_Giles_Laurent.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/2/26/Ultramarine_Flycatcher_%28Ficedula_superciliaris%29_Naggar%2C_Himachal_Pradesh%2C_2013_%28cropped%29.JPG",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Anim1754_-_Flickr_-_NOAA_Photo_Library_%281%29.jpg/2560px-Anim1754_-_Flickr_-_NOAA_Photo_Library_%281%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/d/d4/Starfish%2C_Caswell_Bay_-_geograph.org.uk_-_409413.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/6/69/Grapevinesnail_01.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Texas_invasive_Musk_Thistle_1.jpg/1920px-Texas_invasive_Musk_Thistle_1.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7a/Huskiesatrest.jpg/2880px-Huskiesatrest.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/68/Orange_tabby_cat_sitting_on_fallen_leaves-Hisashi-01A.jpg/1920px-Orange_tabby_cat_sitting_on_fallen_leaves-Hisashi-01A.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/3/30/George_the_amazing_guinea_pig.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Oryctolagus_cuniculus_Rcdo.jpg/1920px-Oryctolagus_cuniculus_Rcdo.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/9/98/Horse-and-pony.jpg",
]


class ModelRequestData(NamedTuple):
    engine_args: EngineArgs
    prompt: str
    image_data: list[Image]
    stop_token_ids: Optional[list[int]] = None
    chat_template: Optional[str] = None
    lora_requests: Optional[list[LoRARequest]] = None


# NOTE: The default `max_num_seqs` and `max_model_len` may result in OOM on
# lower-end GPUs.
# Unless specified, these settings have been tested to work on a single L4.

def load_qwen2_5_vl(question: str, image_urls: list[str]) -> ModelRequestData:
    try:
        from qwen_vl_utils import process_vision_info
    except ModuleNotFoundError:
        print('WARNING: `qwen-vl-utils` not installed, input images will not '
              'be automatically resized. You can enable this functionality by '
              '`pip install qwen-vl-utils`.')
        process_vision_info = None

    model_name = "Qwen/Qwen2.5-VL-3B-Instruct"

    engine_args = EngineArgs(
        model=model_name,
        max_model_len=32768 if process_vision_info is None else 4096,
        max_num_seqs=5,
        limit_mm_per_prompt={"image": len(image_urls)},
    )

    placeholders = [{"type": "image", "image": url} for url in image_urls]
    messages = [{
        "role": "system",
        "content": "You are a helpful assistant."
    }, {
        "role":
        "user",
        "content": [
            *placeholders,
            {
                "type": "text",
                "text": question
            },
        ],
    }]

    processor = AutoProcessor.from_pretrained(model_name)

    prompt = processor.apply_chat_template(messages,
                                           tokenize=False,
                                           add_generation_prompt=True)

    if process_vision_info is None:
        image_data = [fetch_image(url) for url in image_urls]
    else:
        image_data, _ = process_vision_info(messages,
                                            return_video_kwargs=False)

    return ModelRequestData(
        engine_args=engine_args,
        prompt=prompt,
        image_data=image_data,
    )


model_example_map = {
    "qwen2_5_vl": load_qwen2_5_vl,
}


def run_generate(model, question: str, image_urls: list[str],
                 seed: Optional[int]):
    req_data = model_example_map[model](question, image_urls)

    engine_args = asdict(req_data.engine_args) | {"seed": args.seed}
    llm = LLM(**engine_args)

    sampling_params = SamplingParams(temperature=0.0,
                                     max_tokens=256,
                                     stop_token_ids=req_data.stop_token_ids)

    outputs = llm.generate(
        {
            "prompt": req_data.prompt,
            "multi_modal_data": {
                "image": req_data.image_data
            },
        },
        sampling_params=sampling_params,
        lora_request=req_data.lora_requests,
    )

    print("-" * 50)
    for o in outputs:
        generated_text = o.outputs[0].text
        print(generated_text)
        print("-" * 50)


def run_chat(model: str, question: str, image_urls: list[str],
             seed: Optional[int]):
    req_data = model_example_map[model](question, image_urls)

    # Disable other modalities to save memory
    default_limits = {"image": 0, "video": 0, "audio": 0}
    req_data.engine_args.limit_mm_per_prompt = default_limits | dict(
        req_data.engine_args.limit_mm_per_prompt or {})

    engine_args = asdict(req_data.engine_args) | {"seed": seed}
    llm = LLM(**engine_args)

    sampling_params = SamplingParams(temperature=0.0,
                                     max_tokens=256,
                                     stop_token_ids=req_data.stop_token_ids)
    outputs = llm.chat(
        [{
            "role":
            "user",
            "content": [
                {
                    "type": "text",
                    "text": question,
                },
                *({
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    },
                } for image_url in image_urls),
            ],
        }],
        sampling_params=sampling_params,
        chat_template=req_data.chat_template,
        lora_request=req_data.lora_requests,
    )

    print("-" * 50)
    for o in outputs:
        generated_text = o.outputs[0].text
        print(generated_text)
        print("-" * 50)


def parse_args():
    parser = FlexibleArgumentParser(
        description='Demo on using vLLM for offline inference with '
        'vision language models that support multi-image input for text '
        'generation')
    parser.add_argument('--model-type',
                        '-m',
                        type=str,
                        default="phi3_v",
                        choices=model_example_map.keys(),
                        help='Huggingface "model_type".')
    parser.add_argument("--method",
                        type=str,
                        default="generate",
                        choices=["generate", "chat"],
                        help="The method to run in `vllm.LLM`.")
    parser.add_argument("--seed",
                        type=int,
                        default=None,
                        help="Set the seed when initializing `vllm.LLM`.")
    parser.add_argument(
        "--num-images",
        "-n",
        choices=list(range(1, 13)),  # 12 is the max number of images
        default=2,
        help="Number of images to use for the demo.")
    return parser.parse_args()


def main(args: Namespace):
    model = args.model_type
    method = args.method
    seed = args.seed

    image_urls = IMAGE_URLS[:args.num_images]

    if method == "generate":
        run_generate(model, QUESTION, image_urls, seed)
    elif method == "chat":
        run_chat(model, QUESTION, image_urls, seed)
    else:
        raise ValueError(f"Invalid method: {method}")


if __name__ == "__main__":
    args = parse_args()
    main(args)