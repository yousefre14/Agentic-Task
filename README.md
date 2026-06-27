# 🤖 Kayfa AI Sales Agent

An intelligent, Arabic-first sales agent built with **Pydantic AI**, **MongoDB Atlas**, and **Groq LLM** — deployed as a full-stack Streamlit application. The agent answers product questions, handles pricing and policy queries, and silently captures qualified leads into a CRM dashboard, all in real time.

Built as Week 3 of the **Kayfa Agentic AI Internship Program**.

---

## ✨ Features

- **Conversational AI Sales Agent** — warm, consultative tone in Arabic and English, dialect-aware
- **RAG Pipeline** — semantic search over a structured knowledge base (courses, roadmaps, policies, pricing)
- **CRM Lead Capture** — silently saves qualified leads (name + contact) to MongoDB with full ticket schema
- **Behaviour Tracing** — every turn logged to MongoDB with token counts, latency, tool calls, and retrieval sources
- **Usage Tracker** — per-turn and per-session cost tracking with model-specific pricing
- **Auth System** — login-gated access with role-based routing (admin vs user)
- **CRM Dashboard** — admin page showing all captured leads with filters and analytics
- **Dark Glassmorphism UI** — Kayfa gold accent, full RTL Arabic support, custom Streamlit theme

---

## 🗂️ Project Structure

```
kayfa-sales-agent/
│
├── app.py                    # Streamlit entry point — routing, auth, chat UI
├── agent.py                  # Pydantic AI agent orchestration — retrieval, LLM call, tracing
├── tools.py                  # 4 agent tools: course search, roadmap, policies, CRM capture
├── db.py                     # MongoDB Atlas — KnowledgeBaseDB, LeadDB, vector search
├── semantic_search.py        # Sentence-transformer singleton + cosine similarity
├── prompts.py                # System prompt, language rules, sales strategy, CRM schema
├── models.py                 # Pydantic schemas — CRMLeadTicket, ConversationTurn
├── Auth.py                   # Login page, session management, role resolution
├── styles.py                 # Glassmorphism theme, RTL support, top bar, logos
├── usage_tracker.py          # Per-turn cost tracking, session accumulation
├── populate_embeddings.py    # One-time script — pre-compute embeddings for all KB docs
├── data_uploader.py          # Script — upload and chunk KB markdown/JSON files to MongoDB
├── balancer_embed_test.py    # Ad-hoc script — check and backfill missing embeddings
├── pages/
│   └── crm_dashbored.py      # CRM dashboard page (admin only)
└── logos/                    # Kayfa brand assets
```

---

## 🧠 Architecture

```
User Message
     │
     ▼
QueryRouter ──── trivial? ──── skip retrieval ───────────────────┐
     │                                                            │
     ▼ (non-trivial)                                             │
Parallel Retrieval (asyncio.gather)                              │
  ├── search_courses()        → MongoDB vector search            │
  ├── search_roadmaps()       → MongoDB vector search            │
  ├── query_unstructured_kb() → MongoDB vector search (policies) │
  └── pricing hardcoded query → MongoDB vector search            │
     │                                                            │
     ▼                                                            │
Pre-fetched context injected into prompt                         │
     │                                                            │
     ▼                                                    ◄───────┘
Pydantic AI Agent (Groq LLM)
  ├── Tool: search_available_courses
  ├── Tool: get_roadmap_or_diploma_details
  ├── Tool: lookup_policies_and_sales_pitches
  └── Tool: capture_and_save_crm_lead (silent, on name+contact)
     │
     ▼
Lean History Builder (strips tool payloads, caps at 5 turns)
     │
     ▼
Response → Streamlit Chat UI
     │
     ▼
Behaviour Trace → MongoDB (tokens, latency, sources, tool calls)
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq — `llama-3.3-70b` (via Pydantic AI) |
| Agent Framework | Pydantic AI |
| Vector Search | MongoDB Atlas + `paraphrase-multilingual-MiniLM-L12-v2` |
| Database | MongoDB Atlas |
| Frontend | Streamlit |
| Embeddings | sentence-transformers (local, singleton) |
| Deployment | Streamlit Cloud |

---

## ⚙️ Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/kayfa-sales-agent.git
cd kayfa-sales-agent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
MONGODB_URI=your_mongodb_atlas_connection_string
```

### 4. Upload the knowledge base

```bash
python data_uploader.py
```

### 5. Pre-compute embeddings

```bash
python populate_embeddings.py
```

### 6. Run the app

```bash
streamlit run app.py
```

---

## 🗃️ Knowledge Base Structure

The agent's knowledge base is stored in MongoDB Atlas and sourced from these documents:

| File | Content |
|---|---|
| `kayfa_data_science_diploma.md` | Data Science Track — curriculum, pricing, outcomes |
| `kayfa_paid_educational_tracks.md` | All track prices in USD |
| `kayfa_policies_and_faqs.md` | Refund policy, subscription policy, FAQs |
| `kayfa_roadmaps.json` | Structured track/diploma roadmaps |
| `kayfa_courses.json` | Full course catalog with metadata |
| `kayfa_paid_individual_courses.md` | Individual course pricing |

---

## 🔧 Key Design Decisions

**Why pre-fetched context + tool calls?**
The agent uses a two-layer retrieval strategy: pre-fetched context is injected before the LLM call (guaranteeing pricing data is always present), and tool calls handle follow-up queries. This prevents hallucination when the model doesn't call the right tool.

**Why a lean history builder?**
Pydantic AI's default history includes full tool payloads (KB chunks) in every turn. After turn 2, this compounds rapidly. `_build_lean_history()` strips tool returns and pre-fetched context from history, keeping only user messages and assistant text — saving 60–80% of history tokens.

**Why a singleton sentence-transformer?**
`semantic_search.py` holds one model instance via `get_embedding_model()`. Both `db.py` and `tools.py` delegate to it, avoiding the 5× model reload that occurs when each module loads its own instance.

**Why are `db` imports inside tool functions?**
`tools.py` and `db.py` previously had a circular import (`tools → db → tools`). Moving `from db import ...` inside each function body resolves this — Python only resolves the import when the function is called, by which point both modules are fully initialized.

---

## 📊 CRM Dashboard

Admin users see a live CRM dashboard at `/crm_dashbored` (the typo in the filename is intentional — it must be preserved for Streamlit routing). The dashboard shows:

- All captured leads with temperature classification (hot / warm / cold)
- Conversation summaries and recommended sales actions
- Filter by product interest, lead temperature, and date
- Session cost and token usage analytics

---

## 💰 Cost Tracking

Every turn tracks:

- Input tokens, output tokens
- Per-turn cost in USD (model-specific pricing table in `usage_tracker.py`)
- Session cumulative cost
- Latency in milliseconds

All data is written to the `behaviour_traces` collection in MongoDB for analysis.

---

## 🚀 Deployment

The app is deployed on **Streamlit Cloud**. Key deployment notes:

- All secrets (`GROQ_API_KEY`, `MONGODB_URI`) go in Streamlit Cloud's Secrets manager, not `.env`
- The sentence-transformer model downloads on first cold start (~30s)
- `pages/crm_dashbored.py` — the filename typo must be preserved exactly

---

## 👤 Author

**Yousef** — Mechatronics & Robotics Engineer, E-JUST  
Agentic AI Intern @ Kayfa  
[LinkedIn](https://linkedin.com/in/YOUR_HANDLE) · [GitHub](https://github.com/YOUR_USERNAME)

---

## 📄 License

This project was built as part of the Kayfa Agentic AI Internship Program.  
© 2025 Kayfa. All rights reserved.
