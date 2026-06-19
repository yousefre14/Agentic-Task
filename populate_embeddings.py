"""
populate_embeddings.py — Pre-compute and store embeddings for all KB chunks.
Run once after uploading data: python populate_embeddings.py

FIXES:
  1. doc.get('filename') → doc.get('source_file')  (actual MongoDB field name)
  2. Used KnowledgeBaseDB.get_collection() which now exists in db.py
"""

from db import KnowledgeBaseDB
from semantic_search import calculate_embedding


def precompute_embeddings():
    print("=" * 55)
    print("  Kayfa — Pre-computing Knowledge Base Embeddings")
    print("=" * 55)

    collection = KnowledgeBaseDB.get_collection("knowledge_base")
    documents  = list(collection.find({"embedding": {"$exists": False}}))

    if not documents:
        total = collection.count_documents({})
        print(f"\n✅ All {total} documents already have embeddings. Nothing to do.")
        return

    print(f"\nFound {len(documents)} documents missing embeddings. Processing...\n")

    success = 0
    failed  = 0

    for doc in documents:
        content = doc.get("content", "")
        src     = doc.get("source_file", "unknown")   # FIX: was 'filename'

        if not content.strip():
            print(f"  ⚠️  Skipped (empty content): {src}")
            failed += 1
            continue

        try:
            vector = calculate_embedding(content)
            collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"embedding": vector}}
            )
            print(f"  ✅  {src} | chunk {doc.get('chunk_index', '?')}")
            success += 1
        except Exception as e:
            print(f"  ❌  {src}: {e}")
            failed += 1

    print(f"\n{'='*55}")
    print(f"  Done: {success} embedded | {failed} skipped/failed")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    precompute_embeddings()