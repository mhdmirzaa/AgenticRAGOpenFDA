"""Prompt templates for route / rewrite / grade / generate.  [M6]. Keep each small for cheap models."""

ROUTE_PROMPT = """You are a query router. Determine if the question requires searching a knowledge base or can be answered directly.

Question: {question}

If the question is about company policies, products, HR, leave, employees, internal processes, or any specific factual claim that would be in a company handbook, respond with: RETRIEVE
If the question is casual chitchat, a greeting, or clearly outside any company knowledge base, respond with: REFUSE

Respond with exactly one word: RETRIEVE or REFUSE"""

REWRITE_PROMPT = """You are a search query optimizer. Rewrite the user question into a precise search query that will retrieve the most relevant chunks from a company handbook / knowledge base.

Original question: {question}
Previous query (if any): {previous_query}
Iteration: {iteration}

Rules:
- Extract key terms and concepts
- Remove filler words
- If this is a retry (iteration > 1), try different angle / broader/narrower terms
- Output ONLY the rewritten query, nothing else

Rewritten query:"""

GRADE_PROMPT = """You are a relevance grader. Given a question and a text chunk, determine if the chunk contains information relevant to answering the question.

Question: {question}

Chunk:
{chunk_text}

Is this chunk relevant to answering the question? Respond with exactly one word: YES or NO"""

GENERATE_PROMPT = """You are a careful assistant that answers ONLY from the provided context chunks, and cites every claim.

Question: {question}

Context chunks:
{context}

Rules:
1. Use ONLY facts that are explicitly stated in the context chunks above. Do NOT infer, interpret, elaborate, rephrase into stronger claims, or add any explanation that is not written verbatim in the context. (For example, do not say a benefit is "restored" or "takes precedence" unless those words/facts appear in a chunk.)
2. Put a citation marker after EVERY sentence, matching the number of the chunk that supports it (e.g. [1], [2]). If a sentence draws on two chunks, cite both (e.g. [1][2]). Never cite a chunk that does not support the sentence.
3. If the context does not fully contain the answer, do NOT guess — answer only the part that is supported, or say "I cannot answer this question based on the available information." if nothing is supported.
4. Be concise: state the supported facts and stop. No preamble, no added commentary.

Answer:"""

REFUSE_PROMPT = """I cannot answer this question based on the available information in our knowledge base. The question appears to be outside the scope of the documents I have access to."""
