import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class RAGMemory:
    def __init__(self, database_file='crm_data.json'):
        self.db_file = database_file
        self.vectorizer = TfidfVectorizer(stop_words='english')

    def load_history(self):
        try:
            with open(self.db_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def get_context(self, prospect_name, current_transcript):
        """
        Finds relevant past notes/pain points for this prospect.
        """
        history = self.load_history()
        
        # 1. Filter by Company/Prospect
        relevant_docs = [
            doc for doc in history 
            if doc.get('prospect_info', {}).get('name') == prospect_name
        ]
        
        if not relevant_docs:
            return "No previous interaction history found."

        # 2. Simple Semantic Search (Find most relevant past note)
        # In production, use Pinecone/ChromaDB. Here we use TF-IDF for speed/simplicity.
        past_summaries = [d['analysis']['summary'] for d in relevant_docs]
        if not past_summaries:
            return "History exists but contains no summaries."

        # Compare current call to past calls to find recurring themes
        # (Simplified for this snippet)
        context_str = "\n".join([f"- Date {d['timestamp']}: {d['analysis']['summary']}" for d in relevant_docs])
        
        return f"PREVIOUS INTERACTIONS:\n{context_str}"