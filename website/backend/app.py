"""
app.py - FastAPI Backend for AI-Powered Website Platform

A modular, production-ready backend providing AI content generation
endpoints powered by a local LLM API. Designed to be customized
for e-commerce, corporate, or content blog use cases.

Environment variables:
    LLM_API_URL  - Base URL of the local LLM API (default: http://localhost:11434/v1)
    MODEL_NAME   - Model identifier (default: qwen2.5:7b)
"""

import os
import logging
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from knowledge_base import KnowledgeBase

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:7b")
KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", "knowledge")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App & middleware
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Website Platform API",
    description="Modular AI content generation backend for websites",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize knowledge base for RAG
kb = KnowledgeBase(KNOWLEDGE_DIR)

# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

# -- Chat --

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message")
    history: list[dict] = Field(
        default_factory=list,
        description="Conversation history as list of {role, content} dicts",
    )
    context_query: Optional[str] = Field(
        None, description="Optional query to retrieve knowledge base context"
    )

class ChatResponse(BaseModel):
    reply: str
    context_used: bool = False


# -- SEO --

class SEOArticleRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="Article topic")
    keywords: list[str] = Field(
        default_factory=list, description="Target SEO keywords"
    )
    tone: str = Field("professional", description="Writing tone")
    length: str = Field("medium", description="short / medium / long")

class SEOArticleResponse(BaseModel):
    article: str


class SEOMetaRequest(BaseModel):
    page_content: str = Field(..., min_length=1, description="Page content or summary")
    keywords: list[str] = Field(default_factory=list)

class SEOMetaResponse(BaseModel):
    title: str
    description: str


# -- Content --

class ProductDescRequest(BaseModel):
    product_name: str = Field(..., min_length=1)
    features: list[str] = Field(default_factory=list)
    tone: str = Field("professional", description="Writing tone")
    target_audience: str = Field("general", description="Target audience")

class ProductDescResponse(BaseModel):
    description: str


class FAQRequest(BaseModel):
    product_or_service: str = Field(..., min_length=1)
    details: str = Field("", description="Additional details or context")
    count: int = Field(5, ge=1, le=20, description="Number of Q&A pairs")

class FAQResponse(BaseModel):
    faq: str


# -- Translation --

class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    source_language: str = Field("auto", description="Source language or 'auto'")
    target_language: str = Field(..., min_length=1, description="Target language")

class TranslateResponse(BaseModel):
    translated_text: str


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------

async def call_llm(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """
    Call the local LLM API (OpenAI-compatible /chat/completions endpoint).
    Raises HTTPException on failure.
    """
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{LLM_API_URL}/chat/completions", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        logger.error("LLM API HTTP error: %s", exc.response.text)
        raise HTTPException(status_code=502, detail="LLM service returned an error")
    except httpx.RequestError as exc:
        logger.error("LLM API connection error: %s", exc)
        raise HTTPException(status_code=503, detail="LLM service unavailable")
    except (KeyError, IndexError):
        raise HTTPException(status_code=502, detail="Unexpected LLM response format")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "llm_api": LLM_API_URL,
        "knowledge_docs": kb.document_count,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    AI chatbot endpoint with optional RAG context injection.
    Suitable for customer service, product Q&A, general assistance.
    """
    system_prompt = (
        "You are a helpful, professional AI assistant for this website. "
        "Answer questions clearly and concisely. "
        "If you are given reference context, use it to inform your answer. "
        "Reply in the same language the user writes in."
    )

    # RAG: retrieve relevant knowledge if requested
    context_used = False
    query = req.context_query or req.message
    docs = kb.retrieve(query, top_k=3)
    context_block = kb.format_context(docs)

    if context_block:
        system_prompt += (
            f"\n\nReference context (use if relevant):\n{context_block}"
        )
        context_used = True

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(req.history[-10:])  # Keep last 10 turns to control token usage
    messages.append({"role": "user", "content": req.message})

    reply = await call_llm(messages, temperature=0.7, max_tokens=1024)
    return ChatResponse(reply=reply, context_used=context_used)


@app.post("/api/seo/generate", response_model=SEOArticleResponse)
async def seo_generate(req: SEOArticleRequest):
    """Generate an SEO-optimized article from topic and keywords."""
    length_guide = {"short": "about 300 words", "medium": "about 600 words", "long": "about 1200 words"}
    word_target = length_guide.get(req.length, "about 600 words")
    kw_str = ", ".join(req.keywords) if req.keywords else "none specified"

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert SEO content writer. Write well-structured, "
                "engaging articles optimized for search engines. Use headings, "
                "subheadings, and natural keyword placement."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Write an SEO-optimized article.\n"
                f"Topic: {req.topic}\n"
                f"Target keywords: {kw_str}\n"
                f"Tone: {req.tone}\n"
                f"Target length: {word_target}\n"
                f"Include a compelling title, introduction, body with subheadings, "
                f"and conclusion."
            ),
        },
    ]

    article = await call_llm(messages, temperature=0.7, max_tokens=3000)
    return SEOArticleResponse(article=article)


@app.post("/api/seo/meta", response_model=SEOMetaResponse)
async def seo_meta(req: SEOMetaRequest):
    """Generate SEO meta title and description for a page."""
    kw_str = ", ".join(req.keywords) if req.keywords else "none specified"

    messages = [
        {
            "role": "system",
            "content": (
                "You are an SEO specialist. Generate a meta title (under 60 chars) "
                "and meta description (under 160 chars) that are compelling and "
                "keyword-rich. Reply in exactly this format:\n"
                "Title: <title>\nDescription: <description>"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Page content summary:\n{req.page_content[:1000]}\n\n"
                f"Target keywords: {kw_str}"
            ),
        },
    ]

    result = await call_llm(messages, temperature=0.5, max_tokens=256)

    # Parse structured response
    title, description = "", ""
    for line in result.strip().splitlines():
        lower = line.lower().strip()
        if lower.startswith("title:"):
            title = line.split(":", 1)[1].strip()
        elif lower.startswith("description:"):
            description = line.split(":", 1)[1].strip()

    return SEOMetaResponse(
        title=title or result[:60],
        description=description or result[:160],
    )


@app.post("/api/content/product-description", response_model=ProductDescResponse)
async def product_description(req: ProductDescRequest):
    """Generate a compelling product description."""
    features_str = "\n".join(f"- {f}" for f in req.features) if req.features else "Not specified"

    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional copywriter specializing in product descriptions. "
                "Write engaging, benefit-focused descriptions that convert."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Write a product description.\n"
                f"Product: {req.product_name}\n"
                f"Key features:\n{features_str}\n"
                f"Tone: {req.tone}\n"
                f"Target audience: {req.target_audience}"
            ),
        },
    ]

    desc = await call_llm(messages, temperature=0.7, max_tokens=1024)
    return ProductDescResponse(description=desc)


@app.post("/api/content/faq", response_model=FAQResponse)
async def generate_faq(req: FAQRequest):
    """Generate FAQ pairs from product/service information."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful content writer. Generate clear, useful FAQ "
                "entries in Q&A format. Each entry should start with 'Q:' and "
                "the answer with 'A:'."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Generate {req.count} frequently asked questions and answers.\n"
                f"Product/Service: {req.product_or_service}\n"
                f"Additional details: {req.details or 'None'}"
            ),
        },
    ]

    faq = await call_llm(messages, temperature=0.7, max_tokens=2048)
    return FAQResponse(faq=faq)


@app.post("/api/translate", response_model=TranslateResponse)
async def translate(req: TranslateRequest):
    """Translate content between languages using the LLM."""
    source = req.source_language
    if source == "auto":
        source_instruction = "Detect the source language automatically."
    else:
        source_instruction = f"Source language: {source}."

    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional translator. Translate the given text "
                "accurately while preserving tone, formatting, and meaning. "
                "Output ONLY the translated text, nothing else."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{source_instruction}\n"
                f"Target language: {req.target_language}\n\n"
                f"Text to translate:\n{req.text}"
            ),
        },
    ]

    translated = await call_llm(messages, temperature=0.3, max_tokens=2048)
    return TranslateResponse(translated_text=translated)
