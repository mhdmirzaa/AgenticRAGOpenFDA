"""
MaiStorage Agentic RAG - Streamlit Demo App

A working prototype demonstrating the agentic RAG system with:
- Document ingestion and chunking
- Agentic retrieval with self-grading
- Citations and trace visibility
- Comparison: Traditional RAG vs Agentic RAG

Usage:
    cd maistorage-kit/maistorage
    streamlit run demo_app.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import traceback

import streamlit as st

# ---------------------------------------------------------------------------
# Ensure the backend package is importable
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ---------------------------------------------------------------------------
# Async helpers (Streamlit runs its own event loop, so we need care)
# ---------------------------------------------------------------------------
def _run_async(coro):
    """Run an async coroutine from synchronous Streamlit code."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Helpers to safely serialise Pydantic models for session-state storage
# ---------------------------------------------------------------------------
def _to_dict(obj):
    """Convert a Pydantic model (or plain dict) to a plain dict."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return obj


def _to_dict_list(items: list) -> list[dict]:
    return [_to_dict(i) for i in items]


# =========================================================================
# Page configuration
# =========================================================================
st.set_page_config(
    page_title="MaiStorage Agentic RAG",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================================
# Sidebar -- system configuration & document ingestion
# =========================================================================
with st.sidebar:
    st.title("MaiStorage Agentic RAG")
    st.markdown("---")

    st.header("System Configuration")

    provider = st.selectbox(
        "LLM Provider",
        ["gemini", "ollama", "openai", "groq"],
        index=0,
        help="Select the LLM provider.  Gemini free tier is the default.",
    )

    if provider == "gemini":
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            value=os.environ.get("GEMINI_API_KEY", ""),
        )
        if api_key:
            os.environ["GEMINI_API_KEY"] = api_key
    elif provider == "openai":
        api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=os.environ.get("OPENAI_API_KEY", ""),
        )
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
    elif provider == "groq":
        api_key = st.text_input(
            "Groq API Key",
            type="password",
            value=os.environ.get("GROQ_API_KEY", ""),
        )
        if api_key:
            os.environ["GROQ_API_KEY"] = api_key

    os.environ["LLM_PROVIDER"] = provider

    st.markdown("---")

    st.header("Document Ingestion")

    if st.button("Ingest Corpus", use_container_width=True):
        with st.spinner("Loading, chunking, and indexing documents..."):
            try:
                from app.ingestion.loader import load_corpus
                from app.ingestion.chunker import chunk_documents
                from app.ingestion.indexer import index_chunks
                from app.retrieval.vectorstore import get_vectorstore

                vs = get_vectorstore()
                vs.reset()

                docs = load_corpus()
                st.success(f"Loaded {len(docs)} document(s)")

                chunks = chunk_documents(docs)
                st.success(f"Created {len(chunks)} chunks")

                count = _run_async(index_chunks(chunks))
                st.success(f"Indexed {count} chunks into Chroma")

                st.session_state["ingested"] = True
                st.session_state["chunks"] = chunks
            except Exception as exc:
                st.error(f"Ingestion failed: {exc}")
                st.code(traceback.format_exc())

    try:
        from app.retrieval.vectorstore import get_vectorstore

        vs = get_vectorstore()
        doc_count = vs.count()
        st.info(f"Chroma index: {doc_count} chunks")
        if doc_count > 0:
            st.session_state["ingested"] = True
    except Exception:
        st.warning("Chroma not initialised")

    st.markdown("---")

    st.header("About")
    st.markdown(
        """
**Agentic RAG** goes beyond traditional retrieve-and-generate by adding an
intelligent agent loop that:
- Routes queries (retrieval vs. refusal)
- Rewrites queries for better retrieval
- Grades retrieved chunks for relevance
- Re-retrieves if chunks are insufficient
- Generates answers with verified citations
- Refuses gracefully when information is unavailable
"""
    )


# =========================================================================
# Main content area -- four tabs
# =========================================================================
tab_chat, tab_compare, tab_arch, tab_tests = st.tabs(
    ["Chat", "Traditional vs Agentic RAG", "System Architecture", "Test Cases"]
)


# =========================================================================
# Tab 1 -- Chat interface
# =========================================================================
with tab_chat:
    st.header("Agentic RAG Chat")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # Replay history
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            if msg.get("citations"):
                with st.expander("Citations"):
                    for cit in msg["citations"]:
                        marker = cit["marker"]
                        source = cit["source"]
                        section = cit["section"]
                        st.markdown(f"**{marker}** -- `{source}` > `{section}`")
                        st.caption(cit["text"][:300])

            if msg.get("trace"):
                with st.expander("Agent Trace"):
                    for step in msg["trace"]:
                        node_name = step["node"]
                        inp = str(step["input"])[:300]
                        out = str(step["output"])[:300]
                        st.markdown(f"**{node_name}**")
                        st.text(f"  Input:  {inp}")
                        st.text(f"  Output: {out}")

    # New user message
    if prompt := st.chat_input("Ask a question about MaiStorage..."):
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if not st.session_state.get("ingested"):
                notice = (
                    "Please ingest the corpus first using the **Ingest Corpus** "
                    "button in the sidebar."
                )
                st.warning(notice)
                st.session_state["messages"].append(
                    {"role": "assistant", "content": notice}
                )
            else:
                with st.spinner("Agent thinking..."):
                    try:
                        from app.agent.graph import run_agent

                        t0 = time.time()
                        result = _run_async(run_agent(prompt))
                        elapsed = time.time() - t0

                        answer = result.get("answer", "No answer generated.")
                        citations = result.get("citations", [])
                        trace = result.get("trace", [])
                        iterations = result.get("iterations", 0)

                        st.markdown(answer)

                        col1, col2, col3 = st.columns(3)
                        col1.metric("Iterations", iterations)
                        col2.metric("Citations", len(citations))
                        col3.metric("Time", f"{elapsed:.1f}s")

                        if citations:
                            with st.expander("Citations", expanded=True):
                                for cit in citations:
                                    d = _to_dict(cit)
                                    marker = d["marker"]
                                    source = d["source"]
                                    section = d["section"]
                                    st.markdown(
                                        f"**{marker}** -- `{source}` > `{section}`"
                                    )
                                    st.caption(d["text"][:300])

                        if trace:
                            with st.expander("Agent Decision Trace"):
                                for step in trace:
                                    d = _to_dict(step)
                                    node_name = d["node"]
                                    inp = str(d["input"])[:300]
                                    out = str(d["output"])[:300]
                                    st.markdown(f"**Node: {node_name}**")
                                    st.text(f"  Input:  {inp}")
                                    st.text(f"  Output: {out}")
                                    st.markdown("---")

                        st.session_state["messages"].append(
                            {
                                "role": "assistant",
                                "content": answer,
                                "citations": _to_dict_list(citations),
                                "trace": _to_dict_list(trace),
                            }
                        )

                    except Exception as exc:
                        st.error(f"Error: {exc}")
                        st.code(traceback.format_exc())


# =========================================================================
# Tab 2 -- Traditional RAG vs Agentic RAG comparison
# =========================================================================
with tab_compare:
    st.header("Traditional RAG vs Agentic RAG")

    st.markdown(
        """
### What is RAG (Retrieval-Augmented Generation)?

RAG enables LLMs to answer questions based on facts from a specific knowledge
base rather than relying solely on training data.  It combines **retrieval**
(finding relevant documents) with **generation** (producing a natural language
answer).
"""
    )

    col_trad, col_agent = st.columns(2)

    with col_trad:
        st.subheader("Traditional RAG")
        st.markdown(
            """
**Flow:** Query -> Embed -> Retrieve -> Generate

**Characteristics:**
- **Single-pass retrieval**: one query, one set of results
- **No quality check**: uses whatever chunks are retrieved
- **No query refinement**: original question used as-is
- **No self-awareness**: cannot detect when it lacks information
- **Citation gaps**: may hallucinate or fail to cite properly

**Limitations:**
- Vague queries lead to poor retrieval and wrong answers
- No mechanism to detect retrieval failure
- Cannot decompose multi-hop questions
- "Garbage in, garbage out" problem

**Example failure:**
> Q: "If a public holiday falls on my annual leave day, is that leave day
> deducted?"
>
> Traditional RAG might only retrieve the leave policy section and miss the
> public holidays section, giving an incomplete answer.
"""
        )

    with col_agent:
        st.subheader("Agentic RAG")
        st.markdown(
            """
**Flow:** Query -> Route -> Rewrite -> Retrieve -> Rerank -> Grade -> Decide
-> Generate / Retry / Refuse

**Characteristics:**
- **Multi-pass retrieval**: re-retrieves with refined queries
- **Self-grading**: evaluates chunk relevance before answering
- **Query rewriting**: optimises search queries iteratively
- **Graceful refusal**: knows when it cannot answer
- **Verified citations**: post-validates all citation references

**Advantages:**
- Handles vague / ambiguous queries via rewriting
- Detects and recovers from poor retrieval
- Supports multi-hop reasoning across sections
- "Quality control loop" ensures answer reliability

**Example success:**
> Q: "If a public holiday falls on my annual leave day, is that leave day
> deducted?"
>
> Agentic RAG retrieves both leave policy AND public holidays sections, grades
> both as relevant, and generates a complete answer with citations to both
> sources.
"""
        )

    st.markdown("---")
    st.subheader("Side-by-Side Comparison Table")

    comparison_data = {
        "Aspect": [
            "Retrieval passes",
            "Query handling",
            "Chunk quality control",
            "Out-of-scope questions",
            "Multi-hop questions",
            "Citations",
            "Transparency",
            "Cost",
            "Latency",
            "Complexity",
        ],
        "Traditional RAG": [
            "Single pass",
            "Direct embedding",
            "None (trust retrieval)",
            "Hallucinate an answer",
            "Often incomplete",
            "Basic or none",
            "Black box",
            "Lower (1 LLM call)",
            "Lower (~1-3 s)",
            "Simple pipeline",
        ],
        "Agentic RAG": [
            "Multi-pass (up to 3)",
            "Rewrite + optimise",
            "Grade each chunk",
            "Graceful refusal",
            "Iterative retrieval",
            "Validated citations",
            "Full decision trace",
            "Higher (3-7 LLM calls)",
            "Higher (~3-10 s)",
            "Graph-based agent",
        ],
    }
    st.table(comparison_data)

    st.markdown(
        """
### When to Use Which?

| Scenario | Recommendation |
|----------|----------------|
| Simple FAQ lookup | Traditional RAG (faster, cheaper) |
| Complex policy questions | Agentic RAG (more accurate) |
| Multi-document reasoning | Agentic RAG (iterative retrieval) |
| High-stakes decisions | Agentic RAG (verified citations) |
| Cost-constrained | Traditional RAG (fewer API calls) |
| Real-time chat | Traditional RAG (lower latency) |
"""
    )


# =========================================================================
# Tab 3 -- System architecture
# =========================================================================
with tab_arch:
    st.header("System Architecture & Implementation Flow")

    st.subheader("Thought Process & Design Decisions")
    st.markdown(
        """
#### 1. Why Agentic RAG?

Traditional RAG has a fundamental flaw: it treats retrieval as a black box.  If
the retrieved chunks are irrelevant, the LLM either hallucinates or gives a
vague answer.  **Agentic RAG adds a feedback loop** -- the agent grades its own
retrieval results and can retry with a better query.

#### 2. Architecture Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **LLM** | Gemini 2.0 Flash (free tier) | Zero cost, good quality, streaming support |
| **Vector DB** | ChromaDB (PersistentClient) | Local, no server needed, pip-installable |
| **Agent Framework** | LangGraph | State machine for retrieval loops, conditional edges |
| **Chunking** | Structure-aware | Split on headings, preserve tables, ~512 tokens |
| **Retrieval** | Hybrid (Dense + BM25) | Dense catches semantic similarity, BM25 catches keywords |
| **Reranking** | Cross-encoder | Precise relevance scoring after initial retrieval |

#### 3. Pipeline Diagrams
"""
    )

    st.markdown(
        """
```
 INGESTION PIPELINE
 =========================================================================
  Corpus Files --> Loader --> Structure-Aware Chunker --> Embedder (Gemini)
     (.md/.txt)                   (~512 tokens)                |
                                                               v
                                                   ChromaDB Vector Store

 AGENTIC RAG PIPELINE
 =========================================================================
  User Question
       |
  [1. ROUTE] ----------> Does this need retrieval?
       | yes                        | no
  [2. REWRITE] <------+       [REFUSE]
       |              |
  [3. RETRIEVE]       |          (max 3 iterations)
       |              |
  [4. RERANK]         |
       |              |
  [5. GRADE] -------> Sufficient?
       | yes               | no
  [6. GENERATE]            +---> retry with rewritten query
       |
  Answer + Citations + Trace
```
"""
    )

    st.subheader("Key Components")

    with st.expander("Document Ingestion"):
        st.markdown(
            """
- **Loader** (app.ingestion.loader): Reads .md, .txt, .pdf files from
  the corpus/ directory.
- **Chunker** (app.ingestion.chunker): Structure-aware splitting:
  - Split by ## headings first (section boundaries)
  - Then by ### sub-headings if sections are large
  - Then by paragraphs with 64-token overlap
  - Never splits mid-table or mid-list
  - Target: ~512 tokens (~2048 chars) per chunk
- **Indexer** (app.ingestion.indexer): Batch-embeds chunks via the configured
  LLM provider and upserts to ChromaDB.
- **Metadata**: Each chunk carries source, section, chunk_id for citation
  tracking.
"""
        )

    with st.expander("Retrieval Layer"):
        st.markdown(
            """
- **Dense Retrieval**: Cosine similarity over Gemini embeddings in ChromaDB.
- **BM25 Keyword Search**: Traditional keyword matching via rank-bm25.
- **Hybrid Merge**: Reciprocal Rank Fusion (RRF) combines both result sets.
- **Cross-Encoder Reranker**: BAAI/bge-reranker-base re-orders merged
  candidates for precise relevance scoring.
- **Top-K -> Top-N**: Start with K=8 candidates, rerank down to N=4 best.
"""
        )

    with st.expander("Agent Loop (LangGraph)"):
        st.markdown(
            """
The agent is a **state machine** built with LangGraph (app.agent.graph):

1. **Route** -- Classify whether the question needs retrieval or should be
   refused outright.
2. **Rewrite** -- Transform the user question into an optimised search query.
3. **Retrieve** -- Get top-K candidates from hybrid retrieval.
4. **Rerank** -- Re-order candidates with the cross-encoder.
5. **Grade** -- Binary relevance check on each chunk (YES / NO).
6. **Decide** -- Sufficient chunks -> generate; else retry (max 3) or refuse.
7. **Generate** -- Answer with inline [n] citation markers.
8. **Refuse** -- Explicit "I cannot answer" when information is insufficient.

**Hard cap:** Maximum 3 retrieval iterations prevents infinite loops.
**Post-validation:** Citations are verified against graded chunk IDs.
"""
        )

    with st.expander("Citation System"):
        st.markdown(
            """
Citations are a first-class feature, not an afterthought:

1. **During generation**: LLM inserts [n] markers referencing numbered chunks.
2. **Post-validation**: _extract_citations() maps markers to actual graded
   chunks.
3. **Invalid citations removed**: Any [n] referencing a non-graded chunk is
   dropped.
4. **Citation objects**: Each carries marker, source, section, chunk_id, text.
5. **UI display**: Expandable citation panel with source links and chunk
   previews.
"""
        )

    with st.expander("State Schema (RagState)"):
        st.code(
            """class RagState(TypedDict, total=False):
    question: str           # original user question
    query: str              # rewritten search query
    candidates: list[dict]  # retrieved chunks (as dicts)
    graded: list[dict]      # chunks that passed grading
    iterations: int         # current loop count
    answer: str             # generated answer text
    citations: list[Citation]
    trace: list[TraceStep]
    trace_id: str
    needs_retrieval: bool
    is_sufficient: bool
    refused: bool""",
            language="python",
        )


# =========================================================================
# Tab 4 -- Test cases & quality assurance
# =========================================================================
with tab_tests:
    st.header("Test Cases & Quality Assurance")

    st.markdown(
        """
### Test Strategy

The test suite covers multiple levels to ensure quality.
"""
    )

    st.subheader("1. Unit Tests -- Chunking")
    st.markdown(
        """
| Test | Description | Expected |
|------|-------------|----------|
| test_chunk_size | All chunks <= target size | Each chunk <= 2048 chars |
| test_chunk_overlap | Consecutive chunks share overlap | ~256 char overlap |
| test_no_mid_table_split | Tables stay in one chunk | Table text intact |
| test_metadata_present | Every chunk has source, section, chunk_id | All fields non-empty |
| test_section_preservation | Headings create section boundaries | Sections match ## headings |
| test_empty_input | Empty document handling | Returns empty list |
| test_stable_chunk_ids | Same input -> same chunk_ids | Deterministic IDs |
"""
    )

    st.subheader("2. Integration Tests -- Retrieval")
    st.markdown(
        """
| Test | Description | Expected |
|------|-------------|----------|
| test_index_and_query | Index chunks, then query | Returns relevant chunks |
| test_hybrid_retrieval | Dense + BM25 combined | Better recall than either alone |
| test_reranker | Cross-encoder reranking | Top results more relevant |
| test_embed_round_trip | Embed -> store -> query | Cosine similarity > 0.7 |
"""
    )

    st.subheader("3. Agent Tests")
    st.markdown(
        """
| Test | Description | Expected |
|------|-------------|----------|
| test_single_hop_question | Simple factual query | Correct answer with citation |
| test_multi_hop_question | Cross-section reasoning | Retrieves multiple sections |
| test_unanswerable_question | Out-of-scope query | Graceful refusal |
| test_max_iterations | Force re-retrieval loop | Terminates at MAX_ITERS=3 |
| test_citation_validation | Check citation markers | All citations map to graded chunks |
| test_route_decision | Route node classification | Correctly classifies queries |
"""
    )

    st.subheader("4. Golden Set Evaluation")
    st.markdown(
        """
| ID | Question | Type | Expected |
|----|----------|------|----------|
| q1 | "How many annual leave days do full-time staff get?" | Single-hop | Answer contains "18"; source: handbook.md |
| q2 | "If a public holiday falls on my annual leave day, is that leave day deducted?" | Multi-hop | Answer contains "not deducted"; sources: leave-policy + public-holidays |
| q3 | "What is the capital of France?" | Out-of-scope | Refusal (no sources, no answer) |
"""
    )

    st.subheader("5. Evaluation Metrics")
    st.markdown(
        """
| Metric | Description | Target |
|--------|-------------|--------|
| **Hit@1** | Correct source in top-1 result | >= 80% |
| **Hit@3** | Correct source in top-3 results | >= 90% |
| **MRR** | Mean Reciprocal Rank | >= 0.7 |
| **Faithfulness** | Answer supported by retrieved chunks | >= 90% |
| **Citation Accuracy** | Citations reference correct sources | >= 85% |
| **Refusal Correctness** | Refuses when appropriate | 100% |
"""
    )

    st.markdown("---")

    # ---- Interactive test runner --------------------------------------------
    st.subheader("Run Tests")

    # -- Chunker unit tests ---------------------------------------------------
    if st.button("Run Unit Tests (Chunker)", use_container_width=True):
        with st.spinner("Running chunker tests..."):
            try:
                from app.ingestion.loader import Document
                from app.ingestion.chunker import chunk_documents, TARGET_CHARS

                corpus_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "corpus",
                    "handbook.md",
                )
                with open(corpus_path, encoding="utf-8") as fh:
                    handbook_text = fh.read()

                test_doc = Document(content=handbook_text, source="handbook.md")
                chunks = chunk_documents([test_doc])

                results: list[tuple[str, bool, str]] = []

                # 1. Chunks created
                results.append(
                    ("Chunks created", len(chunks) > 0, f"{len(chunks)} chunks")
                )

                # 2. Size constraint (allow 1.5x headroom)
                oversized = [
                    c for c in chunks if len(c.text) > TARGET_CHARS * 1.5
                ]
                detail = (
                    f"{len(oversized)} oversized chunks"
                    if oversized
                    else "All within limits"
                )
                results.append(("Size constraint", len(oversized) == 0, detail))

                # 3. Metadata present
                missing = [
                    c
                    for c in chunks
                    if not c.source or not c.section or not c.chunk_id
                ]
                detail = (
                    f"{len(missing)} missing metadata"
                    if missing
                    else "All complete"
                )
                results.append(("Metadata present", len(missing) == 0, detail))

                # 4. Unique chunk IDs
                ids = [c.chunk_id for c in chunks]
                results.append(
                    (
                        "Unique chunk IDs",
                        len(ids) == len(set(ids)),
                        f"{len(ids)} total, {len(set(ids))} unique",
                    )
                )

                # 5. Section coverage
                sections = sorted(set(c.section for c in chunks))
                sec_str = ", ".join(sections[:6])
                if len(sections) > 6:
                    sec_str += "..."
                results.append(
                    (
                        "Section coverage",
                        len(sections) >= 3,
                        f"{len(sections)} sections: {sec_str}",
                    )
                )

                # 6. Deterministic (stable) chunk IDs
                chunks2 = chunk_documents([test_doc])
                ids2 = [c.chunk_id for c in chunks2]
                results.append(
                    (
                        "Stable chunk IDs",
                        ids == ids2,
                        "Deterministic" if ids == ids2 else "Non-deterministic",
                    )
                )

                # 7. Empty input
                empty_result = chunk_documents([])
                results.append(
                    (
                        "Empty input handling",
                        len(empty_result) == 0,
                        f"Returned {len(empty_result)} chunks",
                    )
                )

                # Display
                for name, passed, detail in results:
                    if passed:
                        st.success(f"PASS -- {name}: {detail}")
                    else:
                        st.error(f"FAIL -- {name}: {detail}")

                passed_count = sum(1 for _, p, _ in results if p)
                st.info(f"Results: {passed_count}/{len(results)} tests passed")

            except Exception as exc:
                st.error(f"Test error: {exc}")
                st.code(traceback.format_exc())

    # -- Agent integration test (requires ingested corpus) --------------------
    if st.button("Run Agent Smoke Test", use_container_width=True):
        if not st.session_state.get("ingested"):
            st.warning("Ingest the corpus first before running agent tests.")
        else:
            with st.spinner("Running agent smoke tests..."):
                try:
                    from app.agent.graph import run_agent

                    agent_results: list[tuple[str, bool, str]] = []

                    # Test 1: single-hop question
                    t0 = time.time()
                    state = _run_async(
                        run_agent(
                            "How many annual leave days do full-time staff get?"
                        )
                    )
                    elapsed = time.time() - t0
                    answer = state.get("answer", "")
                    has_answer = len(answer) > 20 and not state.get(
                        "refused", False
                    )
                    status = "Answered" if has_answer else "No answer"
                    agent_results.append(
                        (
                            "Single-hop question",
                            has_answer,
                            f"{status} in {elapsed:.1f}s",
                        )
                    )

                    # Test 2: out-of-scope question
                    t0 = time.time()
                    state2 = _run_async(
                        run_agent("What is the capital of France?")
                    )
                    elapsed2 = time.time() - t0
                    refused = state2.get("refused", False)
                    answer2 = state2.get("answer", "")
                    is_refused = refused or "cannot" in answer2.lower()
                    status2 = "Refused" if is_refused else "Answered (check manually)"
                    agent_results.append(
                        (
                            "Out-of-scope question",
                            is_refused,
                            f"{status2} in {elapsed2:.1f}s",
                        )
                    )

                    # Test 3: citations present on answerable question
                    citations = state.get("citations", [])
                    agent_results.append(
                        (
                            "Citations present",
                            len(citations) > 0,
                            f"{len(citations)} citation(s)",
                        )
                    )

                    # Test 4: trace recorded
                    trace = state.get("trace", [])
                    agent_results.append(
                        (
                            "Trace recorded",
                            len(trace) > 0,
                            f"{len(trace)} trace step(s)",
                        )
                    )

                    # Test 5: iterations within cap
                    iters = state.get("iterations", 0)
                    agent_results.append(
                        (
                            "Iterations within cap",
                            0 < iters <= 3,
                            f"{iters} iteration(s)",
                        )
                    )

                    for name, passed, detail in agent_results:
                        if passed:
                            st.success(f"PASS -- {name}: {detail}")
                        else:
                            st.error(f"FAIL -- {name}: {detail}")

                    passed_count = sum(1 for _, p, _ in agent_results if p)
                    st.info(
                        f"Results: {passed_count}/{len(agent_results)} "
                        f"tests passed"
                    )

                except Exception as exc:
                    st.error(f"Agent test error: {exc}")
                    st.code(traceback.format_exc())

    # -- Chunk browser (useful for debugging) ---------------------------------
    st.markdown("---")
    st.subheader("Chunk Browser")

    if st.session_state.get("chunks"):
        chunks_list = st.session_state["chunks"]
        st.write(f"Total chunks: {len(chunks_list)}")

        sections_available = sorted(set(c.section for c in chunks_list))
        selected_section = st.selectbox(
            "Filter by section", ["(all)"] + sections_available
        )

        filtered = (
            chunks_list
            if selected_section == "(all)"
            else [c for c in chunks_list if c.section == selected_section]
        )

        for i, chunk in enumerate(filtered):
            label = (
                f"[{i}] {chunk.source} / {chunk.section} "
                f"({len(chunk.text)} chars) -- {chunk.chunk_id[:12]}..."
            )
            with st.expander(label):
                st.text(chunk.text[:1000])
                st.caption(
                    f"chunk_id: {chunk.chunk_id}  |  "
                    f"source: {chunk.source}  |  "
                    f"section: {chunk.section}"
                )
    else:
        st.info("Ingest the corpus to browse chunks.")


# =========================================================================
# Footer
# =========================================================================
st.markdown("---")
st.caption(
    "MaiStorage Agentic RAG System  |  "
    "Built with FastAPI + LangGraph + ChromaDB + Streamlit"
)
