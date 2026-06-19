from db import KnowledgeBaseDB
collection = KnowledgeBaseDB.get_collection("knowledge_base")
docs = list(collection.find(
    {"source_file": {"$regex": "soc", "$options": "i"}},
    {"content": 1, "source_file": 1, "section": 1}
))
print(f"Found {len(docs)} chunks from SOC-related files\n")
for d in docs:
    print(f"— {d.get('source_file')} | {d.get('section', d.get('chunk_index'))}")
    print(f"  {d.get('content', '')[:150]}...\n")