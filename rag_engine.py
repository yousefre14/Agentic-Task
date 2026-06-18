"""
rag_engine.py — Retrieval-Augmented Generation

WHY: 
- Agent must answer ONLY from Kayfa's knowledge base
- No hallucinations about prices, courses, or policies
- Must be fast and context-aware

HOW:
1. Load JSON courses & roadmaps into a searchable index
2. Load markdown FAQs & policies as plain text
3. Provide a retrieval function the agent can call
4. Agent passes queries, retrieves relevant context, generates grounded response
"""

import json
import os
from pathlib import Path
from typing import List, Dict
from difflib import SequenceMatcher

class KayfahKnowledgeBase:
    """Kayfa's structured knowledge base."""
    
    def __init__(self, data_dir: str = 'data'):
        """Load all knowledge base files."""
        self.data_dir = Path(data_dir)
        self.courses = self._load_json('kayfa_courses.json')
        self.roadmaps = self._load_json('kayfa_roadmaps.json')
        self.faq = self._load_markdown('kayfa_faq.md')
        self.policies = self._load_markdown('kayfa_policies.md')
        self.pricing = self._load_markdown('kayfa_pricing.md')
        
    def _load_json(self, filename: str) -> dict:
        """Load JSON knowledge base."""
        filepath = self.data_dir / filename
        if not filepath.exists():
            return {}
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_markdown(self, filename: str) -> str:
        """Load markdown knowledge base."""
        filepath = self.data_dir / filename
        if not filepath.exists():
            return ""
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    
    def search_courses(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search courses by name, skills, or track.
        
        WHY: Let agent find relevant courses for user's goal.
        HOW: Fuzzy string matching on course names + exact match on skills/track.
        """
        results = []
        query_lower = query.lower()
        
        for course in self.courses.get('courses', []):
            # Match by name
            if query_lower in course.get('name', '').lower():
                results.append(course)
                continue
            
            # Match by skills
            skills = [s.lower() for s in course.get('skills', [])]
            if any(query_lower in s for s in skills):
                results.append(course)
                continue
            
            # Match by track
            if query_lower in course.get('track', '').lower():
                results.append(course)
        
        return results[:limit]
    
    def search_roadmaps(self, query: str, limit: int = 3) -> List[Dict]:
        """Search learning paths/diplomas."""
        results = []
        query_lower = query.lower()
        
        for roadmap in self.roadmaps.get('roadmaps', []):
            if query_lower in roadmap.get('name', '').lower():
                results.append(roadmap)
            elif query_lower in roadmap.get('track', '').lower():
                results.append(roadmap)
        
        return results[:limit]
    
    def get_course_by_id(self, course_id: str) -> Dict:
        """Get full course details."""
        for course in self.courses.get('courses', []):
            if course['id'] == course_id:
                return course
        return {}
    
    def get_roadmap_by_id(self, roadmap_id: str) -> Dict:
        """Get full roadmap details."""
        for roadmap in self.roadmaps.get('roadmaps', []):
            if roadmap['id'] == roadmap_id:
                return roadmap
        return {}
    
    def search_faq(self, query: str) -> str:
        """Search FAQ for relevant answer."""
        if not self.faq:
            return ""
        
        # Simple keyword matching in FAQ
        query_words = query.lower().split()
        faq_lines = self.faq.split('\n')
        
        relevant_lines = []
        for line in faq_lines:
            if any(word in line.lower() for word in query_words):
                relevant_lines.append(line)
        
        return '\n'.join(relevant_lines[:5])  # Return top 5 matching lines
    
    def format_context_for_agent(self, courses: List[Dict], roadmaps: List[Dict]) -> str:
        """
        Format knowledge base results as context for the agent.
        
        WHY: Agent needs structured, readable context to generate good answers.
        HOW: Format as markdown with course/roadmap summaries.
        """
        context = "## Relevant Kayfa Products\n\n"
        
        if courses:
            context += "### Courses\n"
            for course in courses:
                context += f"- **{course['name']}** (${course.get('price', 'Free')})\n"
                context += f"  Level: {course.get('level', 'N/A')}\n"
                context += f"  Duration: {course.get('duration', 'N/A')}\n"
                context += f"  Skills: {', '.join(course.get('skills', []))}\n"
                context += f"  Link: {course.get('link', 'N/A')}\n\n"
        
        if roadmaps:
            context += "### Learning Paths & Diplomas\n"
            for roadmap in roadmaps:
                context += f"- **{roadmap['name']}** (${roadmap.get('price', 'N/A')})\n"
                context += f"  Track: {roadmap.get('track', 'N/A')}\n"
                context += f"  Duration: {roadmap.get('duration', 'N/A')}\n"
                context += f"  Courses: {len(roadmap.get('courses', []))}\n"
                context += f"  Diploma: {roadmap.get('is_diploma', False)}\n\n"
        
        return context

# Singleton instance
kb = KayfahKnowledgeBase()