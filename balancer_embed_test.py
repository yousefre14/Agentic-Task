"""
balancer.py — Check and backfill missing embeddings on demand.
Run anytime to ensure all KB documents have stored vectors.

"""

from db import KnowledgeBaseDB
from semantic_search import calculate_embedding

print("=" * 55)
print("  Kayfa — Embedding Balance Check")
print("=" * 55)

collection   = KnowledgeBaseDB.get_collection("knowledge_base")
total        = collection.count_documents({})
missing_docs = list(collection.find({"embedding": {"$exists": False}}))

print(f"\n  Total documents : {total}")
print(f"  Missing vectors : {len(missing_docs)}")

if not missing_docs:
    print("\n Every document already has a stored vector. DB is fully optimised.")
else:
    print(f"\nBackfilling {len(missing_docs)} missing embeddings...\n")
    success = 0
    for doc in missing_docs:
        content = doc.get("content", "")
        src     = doc.get("source_file", "unknown")  
        if content.strip():
            try:
                vector = calculate_embedding(content)
                collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"embedding": vector}}
                )
                print(f"   {src} | chunk {doc.get('chunk_index','?')}")
                success += 1
            except Exception as e:
                print(f"  {src}: {e}")

    print(f"\n✅ Done. {success}/{len(missing_docs)} embeddings saved.")

print()