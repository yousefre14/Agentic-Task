"""
All database operations in one place. Easier to maintain, test, and scale.
     Follows the Single Responsibility Principle.
"""

import os
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING
from bson import ObjectId
from dotenv import load_dotenv
import json

# Initialize connection
load_dotenv()
client = MongoClient(os.environ['MONGODB_URI'])
db = client[os.environ.get('KAYFA_DB_NAME', 'kayfa_sales_agent')]

# Collections
conversations_col = db['conversations']
leads_col = db['leads']
tickets_col = db['crm_tickets']

# Create indexes for fast queries
conversations_col.create_index([('session_id', ASCENDING), ('timestamp', ASCENDING)])
leads_col.create_index([('email', ASCENDING)])
tickets_col.create_index([('created_at', ASCENDING)])

class ConversationDB:
    """Store and retrieve conversations."""
    
    @staticmethod
    def save_turn(session_id: str, role: str, content: str, user_id: str = None):
        """
        Save a single chat turn (user or assistant message).
        
        WHY: Each message is a separate document for flexibility.
             As volume grows, this scales better than arrays in one doc.
        
        HOW: Insert one document with session_id, role, content, timestamp.
        """
        doc = {
            'session_id': session_id,
            'user_id': user_id,
            'role': role,  # "user" or "assistant"
            'content': content,
            'timestamp': datetime.now(timezone.utc)
        }
        result = conversations_col.insert_one(doc)
        return str(result.inserted_id)
    
    @staticmethod
    def load_session(session_id: str) -> list:
        """
        Load all turns for a session in order.
        
        WHY: Replay the conversation in the UI. Exact {role, content} format
             matches what Pydantic AI expects + what Streamlit renders.
        
        HOW: Find all docs with this session_id, sort by timestamp (oldest first).
        """
        cursor = conversations_col.find(
            {'session_id': session_id}
        ).sort('timestamp', ASCENDING)
        
        return [
            {'role': doc['role'], 'content': doc['content']}
            for doc in cursor
        ]
    
    @staticmethod
    def get_conversation_full(session_id: str) -> dict:
        """Get full conversation with metadata."""
        turns = conversations_col.find(
            {'session_id': session_id}
        ).sort('timestamp', ASCENDING)
        
        return {
            'session_id': session_id,
            'turns': [
                {
                    'role': doc['role'],
                    'content': doc['content'],
                    'timestamp': doc['timestamp']
                }
                for doc in turns
            ]
        }

class LeadDB:
    """Store qualified leads and CRM tickets."""
    
    @staticmethod
    def create_ticket(ticket_data: dict) -> str:
        """
        Create a CRM ticket from a conversation.
        
        FIELDS (Arabic-ready):
        - name, phone, email, city, country
        - language, dialect, contact_channel
        - products_interested (course/track/diploma names)
        - goal, current_level, prerequisites_discussed
        - lead_temperature (hot/warm/cold)
        - buying_signals (list of observed signals)
        - objections (list of concerns raised)
        - conversation_summary (Arabic summary)
        - recommended_action (Arabic next steps)
        - timestamp
        
        WHY: Rich tickets let sales reps follow up immediately without re-asking.
        """
        ticket_data['created_at'] = datetime.now(timezone.utc)
        ticket_data['status'] = 'new'  # new, contacted, converted, lost
        
        result = tickets_col.insert_one(ticket_data)
        return str(result.inserted_id)
    
    @staticmethod
    def get_all_tickets(limit=50) -> list:
        """Get all CRM tickets (most recent first)."""
        return list(
            tickets_col.find({}).sort('created_at', ASCENDING).limit(limit)
        )
    
    @staticmethod
    def update_ticket_status(ticket_id: str, status: str, notes: str = ""):
        """Update lead status (new → contacted → converted/lost)."""
        tickets_col.update_one(
            {'_id': ObjectId(ticket_id)},
            {
                '$set': {
                    'status': status,
                    'last_updated': datetime.now(timezone.utc)
                },
                '$push': {'notes': notes} if notes else {}
            }
        )
    
    @staticmethod
    def ticket_exists(email: str) -> bool:
        """Check if a ticket for this email already exists."""
        return tickets_col.find_one({'email': email}) is not None