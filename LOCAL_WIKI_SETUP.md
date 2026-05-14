# Local Document Wiki — Setup Guide

Turn your local documentation folder (PPTX training slides, PDFs, source code) into a searchable, AI-powered Wiki — **100% offline**, no internet required.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Your machine (RTX 3060)                                    │
│                                                             │
│  ┌─────────────────┐    ┌──────────────────────────────┐   │
│  │  DeepWiki-Local │    │  Ollama (localhost:11434)     │   │
│  │  Frontend+API   │───▶│  - nomic-embed-text (embed)  │   │
│  │  port 3000/8001 │    │  - qwen2.5vl:7b (vision)     │   │
│  └────────┬────────┘    └──────────────────────────────┘   │
│           │                                                  │
└───────────┼──────────────────────────────────────────────────┘
            │ text generation (LLM)
            ▼
┌─────────────────────────────────────────────────────────────┐
│  AGX Orin (AGX_ORIN_IP:11434)                               │
│  Ollama: qwen2.5:27b                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 1: Pull Required Ollama Models

### On the RTX 3060 machine (localhost)

```bash
# Embedding model for RAG indexing
ollama pull nomic-embed-text

# Vision LLM for PPTX slide and PDF page extraction
ollama pull qwen2.5vl:7b
```

### On the AGX Orin machine

```bash
# Text generation LLM for wiki generation and Q&A
ollama pull qwen2.5:27b
```

> **Verify models are running:**
> ```bash
> # On RTX 3060
> curl http://localhost:11434/api/tags | python3 -m json.tool
>
> # On AGX Orin (replace with actual IP)
> curl http://AGX_ORIN_IP:11434/api/tags | python3 -m json.tool
> ```

---

## Step 2: Configure Environment Variables

```bash
cd /path/to/deepwiki-open
cp .env.local.example .env
```

Edit `.env` and fill in:

```bash
# Your local documentation folder path
LOCAL_DOCS_PATH=/home/yourname/training-materials

# AGX Orin address on your network
OLLAMA_GENERATOR_HOST=http://192.168.1.100:11434  # replace with actual IP

# These defaults are usually correct for local setup
OLLAMA_HOST=http://localhost:11434
DEEPWIKI_EMBEDDER_TYPE=ollama
VISION_LLM_MODEL=qwen2.5vl:7b
```

---

## Step 3: Install Python Dependencies

```bash
cd /path/to/deepwiki-open/api
pip install python-pptx PyMuPDF Pillow
# or with poetry:
poetry install
```

---

## Step 4: Start the Application

### Option A: Docker Compose (recommended)

```bash
cd /path/to/deepwiki-open

# Build and start (first time takes a few minutes)
docker-compose -f docker-compose.local.yml up --build

# Subsequent starts (faster)
docker-compose -f docker-compose.local.yml up
```

### Option B: Development mode (no Docker)

```bash
# Terminal 1: Start the Python API backend
cd /path/to/deepwiki-open/api
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2: Start the Next.js frontend
cd /path/to/deepwiki-open
npm install
npm run dev
```

---

## Step 5: Generate Your First Wiki

1. Open your browser at **http://localhost:3000**

2. In the input field, type the **absolute path** to your documentation folder:
   ```
   /home/yourname/training-materials
   ```
   Or the path mounted inside Docker:
   ```
   /docs
   ```

3. Click **Generate Wiki** and configure:
   - **Provider**: Ollama
   - **Model**: qwen2.5:27b (or whichever model you pulled on the AGX Orin)
   - **Language**: Your preferred language

4. Click **Start** — the system will:
   - Scan the folder for `.pptx`, `.pdf`, `.md`, source code files
   - Extract text from PPTX slides (with Vision LLM for image-heavy slides)
   - Extract text from PDF pages (with Vision LLM for scanned documents)
   - Build an embedding index using `nomic-embed-text`
   - Generate wiki pages using `qwen2.5:27b` on the AGX Orin

5. Once the wiki is generated, you can ask questions about your documentation using the chat widget.

---

## Supported File Types

| Extension | Extraction Method |
|-----------|------------------|
| `.pptx`, `.ppt` | python-pptx text + Vision LLM (`qwen2.5vl:7b`) for image slides |
| `.pdf` | PyMuPDF text + Vision LLM for scanned/image pages |
| `.md`, `.txt`, `.rst` | Direct text read |
| `.py`, `.js`, `.ts`, `.go`, etc. | Direct source code read |
| `.json`, `.yaml`, `.yml` | Direct text read |

---

## Troubleshooting

### Wiki generation is slow

- PPTX/PDF extraction calls the Vision LLM for each image-heavy slide — this is ~2–5 seconds per slide
- Large decks (50+ slides) may take several minutes on first run
- After first run, results are cached in `~/.adalflow/databases/`

### Cannot connect to AGX Orin

```bash
# Test connectivity
ping AGX_ORIN_IP
curl http://AGX_ORIN_IP:11434/api/tags

# Ensure Ollama on AGX Orin listens on all interfaces (not just localhost)
# On AGX Orin, set: OLLAMA_HOST=0.0.0.0 before starting Ollama
OLLAMA_HOST=0.0.0.0 ollama serve
```

### Ollama model not found

```bash
# Check available models
ollama list

# Pull missing models
ollama pull nomic-embed-text  # for embedding
ollama pull qwen2.5vl:7b      # for vision extraction
ollama pull qwen2.5:27b       # for text generation (on AGX Orin)
```

### Vision LLM not extracting slide content

If vision extraction returns empty results:
1. Test the vision model directly:
   ```bash
   curl http://localhost:11434/api/chat -d '{
     "model": "qwen2.5vl:7b",
     "messages": [{"role": "user", "content": "Describe this image", "images": ["<base64_png>"]}],
     "stream": false
   }'
   ```
2. Check the API logs: `docker-compose -f docker-compose.local.yml logs -f deepwiki-local`

### Embeddings not consistent

If you see "Embedding size validation failed":
1. Delete the cached database: `rm -rf ~/.adalflow/databases/<folder_name>.pkl`
2. Re-run wiki generation

---

## Cache Locations

| Cache type | Location |
|------------|----------|
| Embedding database | `~/.adalflow/databases/<folder_name>.pkl` |
| Downloaded Git repos | `~/.adalflow/repos/` |
| Generated wiki cache | `~/.adalflow/wikicache/` |
| Application logs | `./api/logs/` |
