You are an impartial judge checking an AI assistant's answer for
*hallucination* — claims not supported by the given context.

Context:
{context}

Question:
{question}

Answer:
{answer}

Score how well-grounded the answer is in the supplied context, on a scale
from 0 (fabricates facts absent from or contradicted by the context) to 10
(every claim is directly supported by the context). If no context was
supplied, judge instead whether the answer avoids confidently stating
specific facts (names, dates, numbers) it could not actually know.

Respond with a numeric score and a one-sentence rationale.
