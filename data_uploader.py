"""
upload_knowledge_base.py
========================
Uploads Kayfa knowledge base to MongoDB with RAG-optimised storage.

Storage strategy:
  • .md files  → chunked by ## headings, one chunk = one document
  • .json files → one array element = one document (unchanged)

Each chunk document shape:
  {
    "content":       "the actual text of this section",
    "section":       "Pricing & Enrollment",        ← heading text
    "chunk_index":   2,                              ← position in file
    "source_file":   "kayfa_soc_diploma.md",
    "file_type":     "markdown",
    "collection_key":"kayfa_soc_diploma",
    "imported_at":   "2026-06-18T..."
  }

WHY chunking helps RAG:
  A similarity search on "SOC diploma price" should return the 150-word
  Pricing section — not the entire 3000-word diploma file. Smaller chunks =
  higher precision retrieval = less noise fed to the LLM.
"""

import os
import re
import json
from datetime import datetime, timezone
from pymongo import MongoClient
from semantic_search import calculate_embedding

# ── MongoDB ───────────────────────────────────────────────────────────────────
MONGODB_URI = "mongodb+srv://yousefmegawer_db_user:AO3VqLNqJCNzaWOs@cluster0.nfjjcbd.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGODB_URI)
db     = client["kayfa_sales_agent"]
col    = db["knowledge_base"]

# ── Data path (confirmed from your filesystem) ────────────────────────────────
DATA_DIR = "/media/yousef/DATA/Agentic Task/Ai-Analytics Intern at Kayfa Task3 Data and its Summary/data"


# ════════════════════════════════════════════════════════════════════════════
# CHUNKING — the core RAG improvement
# ════════════════════════════════════════════════════════════════════════════

def chunk_markdown(text: str, source_file: str) -> list[dict]:
    """
    Split a markdown file into chunks at every ## (h2) heading.

    Strategy:
      1. Everything before the first ## becomes chunk 0 (the intro/overview).
      2. Each ## section (heading + its body) becomes its own chunk.
      3. Chunks under MIN_CHARS are merged into the previous chunk so we
         don't create tiny useless documents (e.g. a heading with one line).

    Returns a list of dicts ready for MongoDB insert.
    """
    MIN_CHARS  = 100   # merge chunks shorter than this into the previous one
    slug       = source_file.lower().rsplit(".", 1)[0]
    now        = datetime.now(timezone.utc).isoformat()

    # Split on lines that start with ## (but NOT ###)
    # Pattern: capture the delimiter so we keep the heading in the chunk
    parts = re.split(r'(?=^##(?!#))', text, flags=re.MULTILINE)

    raw_chunks = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Extract heading title (first line if it starts with ##)
        lines = part.split('\n', 1)
        first_line = lines[0].strip()

        if first_line.startswith('##'):
            section = first_line.lstrip('#').strip()
            body    = lines[1].strip() if len(lines) > 1 else ""
        else:
            # intro block before any ## heading
            section = "Overview"
            body    = part

        content = f"{first_line}\n\n{body}".strip() if first_line.startswith('##') else part
        raw_chunks.append({"section": section, "content": content})

    # ── merge tiny chunks into previous ──────────────────────────────────
    merged = []
    for chunk in raw_chunks:
        if merged and len(chunk["content"]) < MIN_CHARS:
            # append to previous chunk's content
            merged[-1]["content"] += "\n\n" + chunk["content"]
            merged[-1]["section"] += " + " + chunk["section"]
        else:
            merged.append(chunk)

    # ── build final documents ─────────────────────────────────────────────
    docs = []
    for i, chunk in enumerate(merged):
        docs.append({
            "content":        chunk["content"],
            "section":        chunk["section"],
            "chunk_index":    i,
            "total_chunks":   len(merged),      # useful for debugging
            "source_file":    source_file,
            "file_type":      "markdown",
            "collection_key": slug,
            "imported_at":    now,
        })

    return docs


# ════════════════════════════════════════════════════════════════════════════
# UPLOAD FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def upload_md(filepath: str) -> tuple[int, int, str | None]:
    filename = os.path.basename(filepath)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        if not text.strip():
            return 0, 0, "File is empty"

        docs = chunk_markdown(text, filename)

        if not docs:
            return 0, 0, "No chunks produced"

        # 🚀 ADD THIS: Pre-calculate vector embeddings for every chunk!
        print(f"  🧠 Generating semantic vectors for {filename}...")
        for doc in docs:
            doc["embedding"] = calculate_embedding(doc["content"])

        # Delete previous version then insert fresh
        col.delete_many({"source_file": filename})
        result = col.insert_many(docs, ordered=False)
        return len(result.inserted_ids), len(text), None

    except Exception as e:
        return 0, 0, str(e)


def upload_json(filepath: str) -> tuple[int, str | None]:
    """
    Read and insert one .json file — one array element per document.
    Returns (docs_inserted, error)
    """
    filename = os.path.basename(filepath)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data if isinstance(data, list) else [data]

        if not items:
            return 0, "JSON file is empty"

        slug = filename.lower().rsplit(".", 1)[0]
        now  = datetime.now(timezone.utc).isoformat()

        docs = []
        for item in items:
            if not isinstance(item, dict):
                item = {"value": item}
            d = dict(item)
            d["source_file"]    = filename
            d["file_type"]      = "json"
            d["collection_key"] = slug
            d["imported_at"]    = now
            
            # Construct meaningful string representation to embed
            content_representation = str(item)
            if "content" in item:
                content_representation = item["content"]
            elif "text" in item:
                content_representation = item["text"]
                
            d["content"] = content_representation
            d["embedding"] = calculate_embedding(content_representation)
            
            docs.append(d)

        col.delete_many({"source_file": filename})
        result = col.insert_many(docs, ordered=False)
        
        return len(result.inserted_ids), None

    except json.JSONDecodeError as e:
        return 0, f"JSON parse error: {e}"
    except Exception as e:
        return 0, str(e)


# ════════════════════════════════════════════════════════════════════════════
# FILE DISCOVERY
# ════════════════════════════════════════════════════════════════════════════

def discover_files(base: str) -> tuple[list[str], list[str]]:
    md_files, json_files = [], []
    for root, _, files in os.walk(base):
        for fname in sorted(files):
            full = os.path.join(root, fname)
            if fname.lower().endswith((".md", ".markdown")):
                md_files.append(full)
            elif fname.lower().endswith(".json"):
                json_files.append(full)
    return md_files, json_files


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 65)
    print("  Kayfa Knowledge Base → MongoDB  (RAG-optimised)")
    print(f"  Data dir : {DATA_DIR}")
    print(f"  DB       : kayfa_sales_agent → knowledge_base")
    print(f"  MD mode  : chunked by ## heading")
    print(f"  JSON mode: one object per document")
    print("=" * 65)

    md_files, json_files = discover_files(DATA_DIR)

    if not md_files and not json_files:
        print(f"\n❌  No files found in: {DATA_DIR}")
        client.close()
        return

    print(f"\n  Found {len(md_files)} .md  and  {len(json_files)} .json files\n")

    total_docs = 0
    failures   = 0

    # ── Markdown (chunked) ────────────────────────────────────────────────
    print("📄  Markdown files  (chunked by ## heading):")
    print("-" * 65)
    for fp in md_files:
        name = os.path.basename(fp)
        n, chars, err = upload_md(fp)
        if err:
            print(f"  ❌  {name:<48} {err}")
            failures += 1
        else:
            print(f"  ✅  {name:<48} {n:>3} chunks  ({chars:,} chars)")
            total_docs += n

    # ── JSON (one object per doc) ─────────────────────────────────────────
    print("\n📋  JSON files  (one object = one document):")
    print("-" * 65)
    for fp in json_files:
        name = os.path.basename(fp)
        n, err = upload_json(fp)
        if err:
            print(f"  ❌  {name:<48} {err}")
            failures += 1
        else:
            print(f"  ✅  {name:<48} {n:>3} documents")
            total_docs += n

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    final = col.count_documents({})
    print(f"  This run : {total_docs} documents inserted  |  {failures} failed")
    print(f"  MongoDB  : {final} total documents in knowledge_base")
    print("=" * 65)

    # ── Chunk breakdown per file ──────────────────────────────────────────
    print("\n  Chunk breakdown (useful for RAG debugging):")
    print("  " + "-" * 55)
    pipeline = [
        {"$group": {"_id": "$source_file",
                    "chunks": {"$sum": 1},
                    "type":   {"$first": "$file_type"}}},
        {"$sort":  {"_id": 1}},
    ]
    for row in col.aggregate(pipeline):
        icon = "📄" if row["type"] == "markdown" else "📋"
        source = row.get("_id") or "UNKNOWN_SOURCE"
        chunks = row.get("chunks", 0)

        print(f"  {icon}  {source:<45} {chunks:>4} docs")

    client.close()
    print()


if __name__ == "__main__":
    main()