# FinSight AI — Member 2 Implementation Guide

This document breaks down the entire data ingestion pipeline into plain English, focusing on the "why" and "how" without a single line of code. It maps exactly to the 7-phase operational flow.

---

### Phase 1: The Front Door (Receiving & Queuing)
**The Goal:** Accept large financial PDFs without freezing the web server.
*   **What you are doing:** Building a system that takes a file, securely stores it, and puts it in a waiting line so a separate "background worker" can process it quietly.
*   **How you do it:** 
    *   **`backend/main.py`**: When a user hits the upload endpoint, this file saves the PDF to a secure folder and instantly writes a record in the PostgreSQL database with the status set to `"pending"`. It immediately replies to the user's browser.
    *   **`backend/celery_worker.py`**: This is the background worker. It constantly listens to the Redis queue. When it hears the ping from the upload, it picks up the PDF, begins the heavy lifting, and changes the database status to `"processing"`.

### Phase 2: Visual Reading (Docling Parsing)
**The Goal:** Read the PDF like a human would, understanding where titles, paragraphs, and tables are located.
*   **What you are doing:** Using Docling to prevent standard scraping from destroying the layout of financial tables.
*   **How you do it:** 
    *   **`backend/ingestion/docling_parser.py`**: Passes the PDF file into Docling. Docling scans the visual layout, builds a map of the document, identifies headings and paragraphs, and perfectly reads financial grids using TableFormer.

### Phase 3: Slicing the Document (Structural Chunking)
**The Goal:** Break the document into logical, bite-sized pieces for the AI to digest.
*   **What you are doing:** Intelligently cutting the document using the Docling map instead of blindly chopping the text every 500 words.
*   **How you do it:** 
    *   **`backend/ingestion/chunker.py`**: Reads through the Docling map. Every time it sees a new Heading (like "Q3 Revenue"), it starts a new chunk. If it encounters a table, it packages that entire table as its own isolated chunk formatted as HTML.

### Phase 4: Making the Data Smart (Enrichment & PII Redaction)
**The Goal:** Cure "AI Amnesia" so the system always knows the context of what it is reading, and ensure Enterprise Security.
*   **What you are doing:** Attaching context to every single chunk, stripping sensitive data, and pulling clean data out of tables.
*   **How you do it:** 
    *   **`backend/ingestion/enricher.py`**: 
        1. **Zero-Trust PII Redaction:** Before any AI sees the text, it runs through a Regex scanner to mask Social Security Numbers, Emails, and Phone Numbers with `[REDACTED]`. *(Configured via `ENABLE_PII_REDACTION=true` in `.env`)*.
        2. **Context Summaries:** Sends the chunk to Gemini 2.0 Flash. It asks the AI to write a short 50-word summary explaining the document title, date, and section, then glues this summary to the top of the text.
        3. **Table Extraction:** For tables, it asks Gemini to pull out raw numbers into clean Key-Value pairs for Member 4's PAL math engine.

### Phase 5: Tagging and Tracking (Metadata Extraction)
**The Goal:** Attach an identification tag to every chunk so it can be securely isolated and visually cited on the frontend.
*   **What you are doing:** Building a digital label for every piece of data you just created.
*   **How you do it:** 
    *   **`backend/ingestion/metadata_extractor.py`**: Attaches a strict `project_id` and `file_id` (a hard security rule for project isolation). It numbers the chunks sequentially (`chunk_index`) and records the exact X and Y coordinates (`bounding_box`) of where the chunk lives on the original PDF page so Member 5 can draw visual highlighter boxes later.

### Phase 6: The Dual Librarian (Indexing)
**The Goal:** Store the perfectly formatted data into databases so Member 1 (The Search Architect) can actually search it.
*   **What you are doing:** Saving data in two different formats simultaneously: one for searching by "meaning" and one for searching by "exact keywords".
*   **How you do it:** 
    *   **`backend/ingestion/dual_indexer.py`**: 
        1. **Vector Search (Qdrant):** Embeds the text (with the helpful summary glued to the top) using Gemini API to read the broad context, converting it into mathematical vectors, and saves it in Qdrant alongside all metadata tags.
        2. **Keyword Search (BM25):** Takes the raw, original text and saves it to a local BM25 file to allow the system to instantly find exact matches for serial numbers or specific dates.

### Phase 7: Closing the Loop
**The Goal:** Tell the system you are done.
*   **What you are doing:** Finalizing the background process.
*   **How you do it:** 
    *   **`backend/ingestion/celery_worker.py`**: Once both Qdrant and BM25 successfully save the data, the worker reaches back to the PostgreSQL database and changes the document's status from `"processing"` to `"ready"`. Member 5's frontend sees this change, hides the loading bar, and lets the user start chatting.
