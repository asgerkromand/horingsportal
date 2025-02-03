

# 3/2/2025

0. Re-scrape

```python
python scripts/scrape.py --data-dir data --all
```

1. Make a table of Horingssvar per year and department
2. Counting the distribution of file-formats to the "høringssvar"-files.

```bash
grep -roh "svar" --include="*" . | awk -F. '{ext=$NF} ext!=""{count[ext]++} END {for (e in count) print e, count[e]}'
```

## Test set (pdf-segmentation)

1. Does a model know how (i.e. where) to segment a pdf?
2. Andet approach er, at model skal predicte for hver side, hvilken organisation der er afsender.
3. Lav et test-set med variation, dvs. forskellige længder og formater.

## Test set (content)

1. Sample on year and departments to manually check file content and structure
2. Construct a test set with the relevant information you want to extract so that you capture enough variation in the different formats and structures

## Model specification

- OCR:
  - Rule-based extraction
  - VISION-AI
    - Open-source?
    - Domæne?
  - OpenAI?

- Multi-step pipeline:
  - "En pdf fil med 30 høringssvar"
    - Prompt 1: "Del denne pdf med 30 høringssvar op i 30 filer - én pr. organisation"
      - Er med til at increase performance?
- Læs om potentielle modeller bruger OCR
  - Det kan være, at jeg får svært ved at parse footters og header, hvis de ligger som billeder
  - Løsning kan så måske være, at splitte pdf'erne op og så konverte til png, og så bruge en multi-modal, som ikke fucker med OCR.
- Hvordan skal jeg repræsentere data?
  - Som pdf?
    - Binary-format.
  - Som png?
    - Multi-modal
    - En side af gangen. Hvem er afsenderen?
    - Måske man kan lave det til en binary classification task, hvor man tager to sider af gangen, og så skal modellen finde ud af, om den skal splitte eller ej.

## Model-Garage

### MMM

- https://github.com/QwenLM/Qwen2.5-VL
  - https://github.com/QwenLM/Qwen2.5-VL?tab=readme-ov-file
  - Har potentiale
- https://allenai.org/multimodal-models

### File-parser

- https://github.com/Filimoa/open-parse

### Library for fine-tuning

- https://docs.unsloth.ai/
  - Has llama-vision 11B