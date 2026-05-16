# app/api/evaluate.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import json
from app.core.llm_client import create_chat_completion
from app.config import settings

router = APIRouter()

class EvalRequest(BaseModel):
    query: str
    answer: str
    contexts: list[str]

class EvalResponse(BaseModel):
    faithfulness: float
    answer_relevance: float
    context_relevance: float
    reasoning: str

@router.post("/evaluate", response_model=EvalResponse)
async def evaluate_rag(req: EvalRequest):
    """
    LLM-as-a-Judge to evaluate RAG performance metrics.
    """
    prompt = f"""
    You are an impartial RAG evaluator. Evaluate the given Query, Answer, and Contexts based on three metrics (score 0.0 to 1.0):
    1. Faithfulness: Is the Answer factually derived from the Contexts? (No hallucinations)
    2. Answer Relevance: Does the Answer directly address the Query?
    3. Context Relevance: Do the Contexts contain the information needed to answer the Query?

    Query: {req.query}
    Answer: {req.answer}
    Contexts:
    {" | ".join(req.contexts)}

    Return ONLY a valid JSON object with the exact keys: 'faithfulness', 'answer_relevance', 'context_relevance', 'reasoning'. Do not include markdown code blocks.
    Example: {{"faithfulness": 0.9, "answer_relevance": 0.8, "context_relevance": 0.9, "reasoning": "Brief explanation"}}
    """
    
    messages = [{"role": "user", "content": prompt}]
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)
        
        response = await create_chat_completion(
            client=client,
            model="llama-3.3-70b-versatile",
            messages=messages,
            stream=False,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        data = json.loads(content)
        
        return EvalResponse(
            faithfulness=float(data.get("faithfulness", 0.0)),
            answer_relevance=float(data.get("answer_relevance", 0.0)),
            context_relevance=float(data.get("context_relevance", 0.0)),
            reasoning=str(data.get("reasoning", ""))
        )
    except Exception as e:
        print(f"Eval Error: {e}")
        raise HTTPException(status_code=500, detail="Evaluation failed")
