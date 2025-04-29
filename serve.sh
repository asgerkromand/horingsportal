#!/bin/bash

nohup vllm serve "hfl/Qwen2.5-VL-7B-Instruct-GPTQ-Int4" \
  --task=generate \
  --quantization=gptq \
  --host=10.84.10.216 \
  --port=8899 \
  --download-dir=/projects/main_compute-AUDIT/data/.cache/huggingface \
  --dtype=half \
  --max-model-len=16384 \
  --allowed-local-media-path="/projects/main_compute-AUDIT/people/crm406/data/hoering_photos/"   \
  --limit-mm-per-prompt=image=3 \
  > vllm.log 2>&1 &