# FinSight AI: Project Overview

## 1. Problem Statement
Financial analysts and decision-makers are overwhelmed by massive, unstructured documents (annual reports, filings, research papers). Current RAG solutions often fail to handle complex document layouts (tables, charts) and provide static text responses that lack interactivity, making it difficult to extract actionable insights quickly.

## 2. Idea / Solution
**FinSight AI** is an advanced, document-grounded RAG platform designed for financial intelligence. It combines high-fidelity document parsing with an interactive Generative UI. Instead of just answering with text, it provides native data visualizations (charts, tables) and voice-enabled interactions, all while maintaining strict grounding through page-level citations.

## 3. Innovation Factor
- **High-Fidelity Parsing**: Uses **Docling** for industry-leading parsing of complex PDF and DOCX financial tables.
- **Generative UI (GenUI)**: Dynamically renders interactive Recharts widgets from LLM responses, moving beyond simple markdown.
- **End-to-End Voice Support**: Hands-free interaction via Web Speech API with automatic "Speak-Back" capabilities.
- **Source Grounding**: Interactive citation markers that scroll to the exact document chunk in the explorer.
- **Dual-State Retrieval**: Combines Qdrant vector search with neural reranking for high-precision retrieval.

## 4. Technology Stack
- **Frontend**: Next.js 16 (App Router), TypeScript, Tailwind CSS, Recharts, Lucide.
- **Backend**: FastAPI, SQLAlchemy (Async), Pydantic.
- **Infrastructure**: Docker, PostgreSQL (Metadata/History), Redis (Caching/Tasks), Qdrant (Vector DB).
- **Processing**: Docling, Celery (Background Workers).
- **AI Models**: Groq (LLaMA 3 70B), Sentence Transformers.

## 5. Business Model / Monetization
- **SaaS Model**: Tiered subscription for institutional financial analysts.
- **Enterprise Integration**: On-premise deployment for hedge funds and banks with strict data privacy requirements.
- **API Access**: Usage-based billing for integrating the high-fidelity parsing engine into existing fintech workflows.

## 6. Impact
- **Financial Analysts**: Reduces document review time by 70%.
- **Investment Teams**: Faster synthesis of quarterly performance across competitors.
- **Compliance Officers**: Immediate verification of data points through interactive citations.

## 7. Prototype / Demo
- **Working Interface**: Full-featured chat with document explorer.
- **Live Widgets**: Real-time generation of Bar and Comparison charts.
- **Voice Loop**: Fully functional voice-to-chat and text-to-speech pipeline.

## 8. Future Scope
- **Multi-Document Reasoning**: Compare data across hundreds of documents simultaneously.
- **Automated Reporting**: One-click generation of polished financial reports from conversational insights.
- **Real-Time Data Feeds**: Integrating live market data (Stock APIs) into the RAG context.
