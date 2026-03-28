"""
社交媒体内容生成机器人 - 主应用
Social Media Content Generation Bot - Main Application

基于 FastAPI 构建，调用本地 LLM API 为多个社交媒体平台生成定制化内容。
"""

import os
import logging
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("social-bot")

# ---------------------------------------------------------------------------
# 环境变量 & 常量
# ---------------------------------------------------------------------------
LLM_API_URL: str = os.getenv("LLM_API_URL", "http://localhost:8000/v1")
MODEL_NAME: str = os.getenv("MODEL_NAME", "auto")
LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120"))

# 支持的平台列表
SUPPORTED_PLATFORMS: list[str] = [
    "xiaohongshu",
    "douyin",
    "weibo",
    "twitter",
    "instagram",
    "zhihu",
    "bilibili",
    "tiktok",
    "linkedin",
    "youtube",
]

# 提示词目录
PROMPTS_DIR = Path(__file__).parent / "prompts"

# ---------------------------------------------------------------------------
# 提示词加载
# ---------------------------------------------------------------------------

_prompt_cache: dict[str, str] = {}


def load_prompt(name: str) -> str:
    """从 prompts/ 目录加载系统提示词，带内存缓存。"""
    if name in _prompt_cache:
        return _prompt_cache[name]

    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"提示词文件不存在: {path}")

    text = path.read_text(encoding="utf-8").strip()
    _prompt_cache[name] = text
    logger.info("已加载提示词: %s (%d 字符)", name, len(text))
    return text


# ---------------------------------------------------------------------------
# Pydantic 数据模型
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    """单平台内容生成请求"""
    platform: str = Field(..., description="目标平台: xiaohongshu/douyin/weibo/twitter/instagram")
    topic: str = Field(..., description="内容主题或关键词")
    language: str = Field(default="auto", description="输出语言: zh/en/auto")
    extra_instructions: str = Field(default="", description="额外的自定义指令")
    max_tokens: int = Field(default=1024, ge=64, le=4096, description="最大生成 token 数")
    temperature: float = Field(default=0.8, ge=0.0, le=2.0, description="生成温度")


class GenerateResponse(BaseModel):
    """内容生成响应"""
    platform: str
    content: str
    model: str
    usage: Optional[dict] = None


class RewriteRequest(BaseModel):
    """内容改写请求"""
    original_content: str = Field(..., description="原始内容/热门帖子")
    target_platform: str = Field(default="", description="目标平台（可选）")
    style: str = Field(default="", description="目标风格描述（可选）")
    language: str = Field(default="auto", description="输出语言: zh/en/auto")
    max_tokens: int = Field(default=1024, ge=64, le=4096)
    temperature: float = Field(default=0.8, ge=0.0, le=2.0)


class RewriteResponse(BaseModel):
    """改写响应"""
    rewritten_content: str
    model: str
    usage: Optional[dict] = None


class VideoScriptRequest(BaseModel):
    """视频脚本生成请求"""
    topic: str = Field(..., description="视频主题")
    duration: str = Field(default="60s", description="目标时长: 15s/30s/60s/3min/5min")
    target_platform: str = Field(default="douyin", description="目标平台")
    style: str = Field(default="", description="风格要求")
    language: str = Field(default="zh", description="输出语言")
    max_tokens: int = Field(default=2048, ge=64, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class VideoScriptResponse(BaseModel):
    """视频脚本响应"""
    script: str
    model: str
    usage: Optional[dict] = None


class BatchRequest(BaseModel):
    """批量生成请求 - 一个话题生成所有平台内容"""
    topic: str = Field(..., description="内容主题")
    platforms: list[str] = Field(default=SUPPORTED_PLATFORMS, description="目标平台列表")
    language: str = Field(default="auto", description="输出语言")
    extra_instructions: str = Field(default="")
    max_tokens: int = Field(default=1024, ge=64, le=4096)
    temperature: float = Field(default=0.8, ge=0.0, le=2.0)


class BatchResponse(BaseModel):
    """批量生成响应"""
    results: dict[str, GenerateResponse]
    failed: dict[str, str] = Field(default_factory=dict, description="失败的平台及原因")


# ---------------------------------------------------------------------------
# LLM 调用工具函数
# ---------------------------------------------------------------------------

async def call_llm(
    system_prompt: str,
    user_message: str,
    *,
    max_tokens: int = 1024,
    temperature: float = 0.8,
) -> dict:
    """
    调用 OpenAI 兼容的 LLM API（chat/completions）。

    返回值示例:
    {
        "content": "生成的文本",
        "model": "model-name",
        "usage": {...}
    }
    """
    url = f"{LLM_API_URL}/chat/completions"
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    logger.info("调用 LLM: %s (max_tokens=%d, temp=%.2f)", url, max_tokens, temperature)

    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        except httpx.TimeoutException:
            logger.error("LLM 请求超时 (%ss)", LLM_TIMEOUT)
            raise HTTPException(status_code=504, detail="LLM 服务请求超时")
        except httpx.HTTPStatusError as exc:
            logger.error("LLM 返回错误: %s %s", exc.response.status_code, exc.response.text[:500])
            raise HTTPException(
                status_code=502,
                detail=f"LLM 服务返回错误: {exc.response.status_code}",
            )
        except httpx.ConnectError:
            logger.error("无法连接 LLM 服务: %s", url)
            raise HTTPException(status_code=503, detail="无法连接 LLM 服务，请检查 LLM_API_URL 配置")

    data = resp.json()
    choice = data["choices"][0]
    return {
        "content": choice["message"]["content"],
        "model": data.get("model", MODEL_NAME),
        "usage": data.get("usage"),
    }


def build_user_message(topic: str, language: str, extra: str = "") -> str:
    """构建用户消息，包含语言指令和额外要求。"""
    parts = [f"主题/Topic: {topic}"]
    if language and language != "auto":
        lang_map = {"zh": "请用中文输出", "en": "Please respond in English"}
        parts.append(lang_map.get(language, f"Language: {language}"))
    if extra:
        parts.append(f"额外要求/Extra: {extra}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------

app = FastAPI(
    title="社交媒体内容生成机器人",
    description="基于 LLM 的多平台社交媒体内容自动生成服务",
    version="1.0.0",
)


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "ok",
        "llm_api_url": LLM_API_URL,
        "model": MODEL_NAME,
    }


@app.get("/platforms")
async def list_platforms():
    """返回支持的社交媒体平台列表"""
    return {
        "platforms": SUPPORTED_PLATFORMS,
        "descriptions": {
            "xiaohongshu": "小红书 - 种草文案、生活分享",
            "douyin": "抖音/TikTok - 短视频脚本文案",
            "weibo": "微博 - 话题热点、短文案",
            "twitter": "Twitter/X - 推文、Thread",
            "instagram": "Instagram - 图文配文、Reel 文案",
            "zhihu": "知乎 - 专业深度长文、问答",
            "bilibili": "B站 - 年轻化视频文案、弹幕互动",
            "tiktok": "TikTok - International short video, trending content",
            "linkedin": "LinkedIn - Professional thought leadership, industry insights",
            "youtube": "YouTube - SEO optimized video scripts, descriptions & tags",
        },
    }


@app.post("/generate", response_model=GenerateResponse)
async def generate_content(req: GenerateRequest):
    """为指定平台生成社交媒体内容"""
    if req.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的平台: {req.platform}。支持的平台: {SUPPORTED_PLATFORMS}",
        )

    system_prompt = load_prompt(req.platform)
    user_message = build_user_message(req.topic, req.language, req.extra_instructions)

    result = await call_llm(
        system_prompt,
        user_message,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
    )

    return GenerateResponse(
        platform=req.platform,
        content=result["content"],
        model=result["model"],
        usage=result["usage"],
    )


@app.post("/rewrite", response_model=RewriteResponse)
async def rewrite_content(req: RewriteRequest):
    """改写热门帖子/已有内容"""
    system_prompt = load_prompt("rewrite")

    # 如果指定了目标平台，追加平台风格要求
    if req.target_platform and req.target_platform in SUPPORTED_PLATFORMS:
        platform_prompt = load_prompt(req.target_platform)
        system_prompt += f"\n\n---\n同时请参考以下平台风格要求:\n{platform_prompt}"

    user_parts = [f"原始内容:\n{req.original_content}"]
    if req.style:
        user_parts.append(f"目标风格: {req.style}")
    if req.language and req.language != "auto":
        lang_map = {"zh": "请用中文输出", "en": "Please respond in English"}
        user_parts.append(lang_map.get(req.language, f"Language: {req.language}"))
    user_message = "\n\n".join(user_parts)

    result = await call_llm(
        system_prompt,
        user_message,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
    )

    return RewriteResponse(
        rewritten_content=result["content"],
        model=result["model"],
        usage=result["usage"],
    )


@app.post("/video-script", response_model=VideoScriptResponse)
async def generate_video_script(req: VideoScriptRequest):
    """生成视频分镜脚本"""
    system_prompt = load_prompt("video_script")

    user_parts = [
        f"视频主题: {req.topic}",
        f"目标时长: {req.duration}",
        f"目标平台: {req.target_platform}",
    ]
    if req.style:
        user_parts.append(f"风格要求: {req.style}")
    if req.language and req.language != "auto":
        lang_map = {"zh": "请用中文输出", "en": "Please respond in English"}
        user_parts.append(lang_map.get(req.language, f"Language: {req.language}"))
    user_message = "\n".join(user_parts)

    result = await call_llm(
        system_prompt,
        user_message,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
    )

    return VideoScriptResponse(
        script=result["content"],
        model=result["model"],
        usage=result["usage"],
    )


@app.post("/batch", response_model=BatchResponse)
async def batch_generate(req: BatchRequest):
    """批量生成 - 一个话题同时为多个平台生成内容"""
    # 验证平台列表
    invalid = [p for p in req.platforms if p not in SUPPORTED_PLATFORMS]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的平台: {invalid}。支持的平台: {SUPPORTED_PLATFORMS}",
        )

    results: dict[str, GenerateResponse] = {}
    failed: dict[str, str] = {}

    # 逐平台调用（可改为 asyncio.gather 并发，但需考虑 LLM 并发限制）
    import asyncio

    async def _gen(platform: str) -> tuple[str, Optional[GenerateResponse], Optional[str]]:
        try:
            system_prompt = load_prompt(platform)
            user_message = build_user_message(req.topic, req.language, req.extra_instructions)
            result = await call_llm(
                system_prompt,
                user_message,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
            )
            resp = GenerateResponse(
                platform=platform,
                content=result["content"],
                model=result["model"],
                usage=result["usage"],
            )
            return platform, resp, None
        except Exception as exc:
            logger.error("批量生成失败 [%s]: %s", platform, exc)
            return platform, None, str(exc)

    tasks = [_gen(p) for p in req.platforms]
    outcomes = await asyncio.gather(*tasks)

    for platform, resp, error in outcomes:
        if resp is not None:
            results[platform] = resp
        else:
            failed[platform] = error or "未知错误"

    return BatchResponse(results=results, failed=failed)


# ---------------------------------------------------------------------------
# 入口（开发用，生产环境使用 uvicorn 命令启动）
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info",
    )
