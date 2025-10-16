# ReviewProject
AI Translation Assistance for Sermon Translation (EN → PT)

## Overview

This project provides an AI-powered translation pipeline for converting English sermons to Portuguese, using machine translation, retrieval-augmented generation, and fine-tuned post-editing models.

## Prerequisites

### Environment Setup
1. Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   ```
2. Add your OpenAI API key to `.env`:
   ```
   OPENAI_API_KEY=sk-your-openai-api-key-here
   ```
3. Add your GPT prompt instructions in config/prompts/translate_system.txt

### Dependencies
Install required packages:
```bash
pip install -r requirements.txt
```

## Commands and Workflow

### 1. Fetch Source Material
```bash
python -m scripts.fetch_sermon <sermon_reference>
```

**What it does:**
- Scrapes sermon content from messagehub.info using the provided sermon reference (e.g., "61-0125")
- Extracts the sermon title, location, and formatted text content
- Parses HTML and preserves paragraph structure with proper numbering
- Saves the English source text to `input/en/<sermon_reference>.txt`

**Behind the scenes:**
- Sends HTTP request to `https://messagehub.info/en/readMessage.msg?ref_num={sermon_id}`
- Uses BeautifulSoup to parse HTML and extract structured content from specific CSS classes
- Fixes formatting issues like separated paragraph numbers
- Creates the input directory structure if it doesn't exist

**Example:**
```bash
python -m scripts.fetch_sermon 61-0125
# Creates: input/en/61-0125.txt
```

### 2. Process Individual Sermon
```bash
python -m scripts.process_sermon --sermon-id <id> --input-file input/en/<id>.txt [--verbose]
```

**What it does:**
- **Phase 1: Translation** - Translates English source to raw Portuguese using GPT-4o
- **Phase 2: Retrieval** - Finds similar translation examples from the Chroma vector database
- **Phase 3: Post-editing** - Uses a fine-tuned model to improve the raw translation based on retrieved examples
- **Phase 4: Output** - Saves the final Portuguese translation with metadata

**Behind the scenes:**
- Loads translation and post-editing prompts from config files
- Uses OpenAI embeddings to find semantically similar translation examples
- Applies retrieval-augmented generation (RAG) to improve translation quality
- Saves intermediate and final outputs with processing metadata

**Example:**
```bash
python -m scripts.process_sermon --sermon-id 61-0125 --input-file input/en/61-0125.txt --verbose
```

### 3. Create docx file for review
```bash
python -m scripts.review.build_docx --sermon-id <id>
```


## Directory Structure

```
reviewProject/
├── input/en/              # Source English sermons
├── output/               # Processing outputs (ignored by git)
├── final/               # Final reviewed translations
├── config/              # Configuration files and prompts
└── scripts/             # Processing scripts
```

## Typical Workflow

1. **Fetch new sermon**: `python -m scripts.fetch_sermon 61-0125`
2. **Process translation**: `python -m scripts.process_sermon --sermon-id 61-0125 --input-file input/en/61-0125.txt`
3. **Create docx file for review**:  `python -m scripts.review.build_docx --sermon-id 61-0205E`

## Notes

- The system uses GPT-4o for initial translation and fine-tuned models for post-editing
- Translation memory improves quality through retrieval of similar translation examples
- All API keys and sensitive configuration should be stored in environment variables
- The workflow supports both individual sermon processing and batch operations