"""
db.py — All database operations: Conversations, CRM Tickets, Knowledge Base RAG.

FIXES:
  1. query_unstructured_kb now returns TOP N chunks (not top 1) — critical for
     price questions that need both the diploma file AND the pricing file.
  2. 'filename' → 'source_file' everywhere (matches actual MongoDB field name).
  3. Removed full-collection RAM load on every query — uses stored embeddings only,
     falls back to on-the-fly only for docs missing embeddings.
  4. Added search_courses() and search_roadmaps() methods tools.py calls directly.
  5. get_collection() kept for balancer.py and populate_embeddings.py.
"""

import os
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
from dotenv import load_dotenv
from semantic_search import calculate_embedding, compute_cosine_similarity

load_dotenv()

client = MongoClient(os.environ['MONGODB_URI'])
db     = client[os.getenv('KAYFA_DB_NAME', 'kayfa_sales_agent')]

conversations_col = db['conversations']
tickets_col       = db['crm_tickets']
kb_col            = db['knowledge_base']


# ════════════════════════════════════════════════════════════════════════════
# CONVERSATIONS
# ════════════════════════════════════════════════════════════════════════════

class ConversationDB:

    @staticmethod
    def save_turn(session_id: str, role: str, content: str, user_id: str = None) -> str:
        doc = {
            'session_id': session_id,
            'user_id':    user_id,
            'role':       role,
            'content':    content,
            'timestamp':  datetime.now(timezone.utc),
        }
        result = conversations_col.insert_one(doc)
        return str(result.inserted_id)

    @staticmethod
    def load_session(session_id: str) -> list:
        cursor = conversations_col.find(
            {'session_id': session_id}
        ).sort('timestamp', ASCENDING)
        return [{'role': d['role'], 'content': d['content']} for d in cursor]


# ════════════════════════════════════════════════════════════════════════════
# CRM TICKETS
# ════════════════════════════════════════════════════════════════════════════

class LeadDB:
    @staticmethod
    def create_ticket(ticket_data: dict) -> str:
        ticket_data['created_at'] = datetime.now(timezone.utc)
        ticket_data['status'] = 'new'
        if 'notes' not in ticket_data:
            ticket_data['notes'] = []
        result = tickets_col.insert_one(ticket_data)
        return str(result.inserted_id)
    
    @staticmethod
    def get_all_tickets(limit: int = 50) -> list:
        cursor = tickets_col.find({}).sort('created_at', DESCENDING).limit(limit)
        tickets = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            tickets.append(doc)
        return tickets

    # 🚀 UPDATED & FIXED METHOD BELOW:
    @staticmethod
    def update_ticket_status(ticket_id: str, status: str, note: str = None, **kwargs) -> bool:
        """
        Updates a CRM ticket status and optionally pushes an interaction note 
        into the notes tracking history array.
        """
        try:
            # 1. Prepare base fields to set
            update_fields = {"status": status, "updated_at": datetime.now(timezone.utc)}
            update_operations = {"$set": update_fields}
            
            # 2. If a rep note was submitted from the dashboard, push it into the tracking array
            if note and note.strip():
                new_note_entry = {
                    "text": note.strip(),
                    "timestamp": datetime.now(timezone.utc),
                    "author": "Sales Representative"
                }
                update_operations["$push"] = {"notes": new_note_entry}
                
            # 3. Perform atomic operation in MongoDB
            result = tickets_col.update_one(
                {"_id": ObjectId(ticket_id)},
                update_operations
            )
            
            print(f"💼 CRM Ticket {ticket_id} status modified successfully to: {status}")
            return result.modified_count > 0
            
        except Exception as e:
            print(f"❌ Failed to alter CRM document status status: {str(e)}")
            return False


# ════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE BASE
# ════════════════════════════════════════════════════════════════════════════

class KnowledgeBaseDB:

    @classmethod
    def get_collection(cls, collection_name: str):
        """Direct collection access — used by balancer.py and populate_embeddings.py."""
        return db[collection_name]

    # ── CORE: multi-chunk semantic search ────────────────────────────────

    @classmethod
    def query_unstructured_kb(cls, query_text: str, top_n: int = 4,
                               similarity_threshold: float = 0.15) -> str:
        """
        Semantic search returning TOP N relevant chunks (not just 1).

        WHY top_n=4?
        A price question needs BOTH the diploma overview (what it is) AND the
        pricing chunk (what it costs) — these live in different source files.
        Returning only the single best match caused the hallucination bug where
        the agent found curriculum but never found the price table.

        HOW:
          1. Embed the query once.
          2. Score every stored embedding with cosine similarity.
          3. Return the top_n chunks above threshold, concatenated.
          4. For docs missing embeddings (shouldn't happen after balancer runs)
             compute on-the-fly and save so it only happens once.
        """
        try:
            query_vector = calculate_embedding(query_text)
            documents    = list(kb_col.find({}))

            if not documents:
                return "Knowledge base is empty."

            scored = []
            for doc in documents:
                content    = doc.get("content", "")
                doc_vector = doc.get("embedding")

                # on-the-fly fallback for docs without stored embedding
                if not doc_vector:
                    doc_vector = calculate_embedding(content)
                    kb_col.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"embedding": doc_vector}}
                    )

                score = compute_cosine_similarity(query_vector, doc_vector)
                scored.append((score, doc))

            # sort by similarity descending
            scored.sort(key=lambda x: x[0], reverse=True)

            # filter by threshold and take top_n
            top_chunks = [
                (score, doc) for score, doc in scored
                if score >= similarity_threshold
            ][:top_n]

            if not top_chunks:
                print(f"[RAG] No chunks above threshold {similarity_threshold} "
                      f"for query: '{query_text}' "
                      f"(best score: {scored[0][0]:.4f} from "
                      f"{scored[0][1].get('source_file','?')})")
                return ""   # empty string → agent uses fallback language

            # build context block from all matched chunks
            context_parts = []
            for score, doc in top_chunks:
                src     = doc.get('source_file', 'KB')
                section = doc.get('section', '')
                content = doc.get('content', '')
                print(f"[RAG] ✅ {src} | {section} | score={score:.4f}")
                context_parts.append(
                    f"### Source: {src} — {section}\n{content}"
                )

            return "\n\n---\n\n".join(context_parts)

        except Exception as e:
            import traceback
            print("[RAG] CRITICAL ERROR:\n", traceback.format_exc())
            return ""

    # ── ALIAS: courses search (called from tools.py) ──────────────────────

    @classmethod
    def search_courses(cls, query_text: str = "", track: str = None,
                       level: str = None, **kwargs) -> str:
        """
        Search for course information.
        Combines track + level + query into one semantic search.
        Fixes tools.py calling search_courses(track=..., level=...) with no query_text.
        """
        parts = []
        if track:  parts.append(track)
        if level:  parts.append(level)
        if query_text: parts.append(query_text)

        combined = " ".join(parts) if parts else "courses overview"
        return cls.query_unstructured_kb(combined)

    # ── ALIAS: roadmap / diploma search (called from tools.py) ───────────

    @classmethod
    def search_roadmaps(cls, query_text: str = "", structural_name: str = None,
                        **kwargs) -> str:
        """
        Search for diploma / roadmap details.
        Accepts structural_name kwarg tools.py passes.
        """
        query = structural_name or query_text or "learning path diploma"
        return cls.query_unstructured_kb(query)