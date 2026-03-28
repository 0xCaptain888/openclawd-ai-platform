# Prompt Engineering Guide for Social Media Bot

This guide explains how to write, customize, and maintain prompt templates for the social media content generation bot.

## Supported Platforms

| Platform     | File              | Language | Style Summary                              |
|-------------|-------------------|----------|--------------------------------------------|
| xiaohongshu | `xiaohongshu.txt` | Chinese  | Lifestyle sharing, product reviews         |
| douyin      | `douyin.txt`      | Chinese  | Short video scripts, trending hooks        |
| weibo       | `weibo.txt`       | Chinese  | Hot topics, short-form posts               |
| twitter     | `twitter.txt`     | English  | Tweets, threads                            |
| instagram   | `instagram.txt`   | English  | Photo captions, Reel scripts               |
| zhihu       | `zhihu.txt`       | Chinese  | In-depth articles, data-driven analysis    |
| bilibili    | `bilibili.txt`    | Chinese  | Youth-oriented video scripts, danmaku      |
| tiktok      | `tiktok.txt`      | English  | Trending short video, duet/stitch friendly |
| linkedin    | `linkedin.txt`    | English  | Professional thought leadership            |
| youtube     | `youtube.txt`     | English  | SEO titles, descriptions, full scripts     |

## How to Write Effective Prompts

### 1. Define the Role Clearly

Start every prompt with a clear persona definition. The LLM performs best when it has a concrete identity.

```
You are a [platform] content creator with [specific expertise].
```

### 2. Provide Structured Output Requirements

Break down the expected output into labeled sections. Use headers like:

- `【CONTENT STRUCTURE】` or `【内容结构】`
- `【STYLE GUIDELINES】` or `【写作风格】`
- `【PLATFORM-SPECIFIC TIPS】` or `【平台特色】`

### 3. Include Concrete Examples and Anti-patterns

Tell the model what TO DO and what NOT TO DO:

```
- Use: Short punchy sentences, rhetorical questions
- Avoid: Corporate jargon, walls of text, generic advice
```

### 4. Optimize for Platform Algorithms

Each platform rewards different engagement signals. Mention these explicitly:

- **TikTok/Douyin**: Watch time, completion rate, shares
- **YouTube**: Click-through rate, watch time, engagement
- **LinkedIn**: Comments, shares, dwell time
- **Zhihu**: Upvotes, bookmarks, follows

## Available Variables

All prompt templates can reference these variables, which are injected by the application at runtime:

| Variable               | Description                                      |
|------------------------|--------------------------------------------------|
| `{topic}`              | The main topic or keyword provided by the user   |
| `{language}`           | Target output language (zh/en/auto)              |
| `{extra_instructions}` | Any additional custom instructions from the user |

These variables are documented in the `【变量说明】` or `【VARIABLES】` section at the end of each prompt file.

## Tips for Improving Content Quality

1. **Be specific about structure**: Instead of "write a good post", specify exact sections, word counts, and formatting rules.

2. **Include platform-native language**: Each platform has its own jargon and culture. Use terms like "三连" (Bilibili), "fyp" (TikTok), "Thread" (Twitter).

3. **Set guardrails**: Explicitly state what to avoid -- clickbait, misinformation, offensive language.

4. **Specify formatting**: Mention emoji usage, line breaks, hashtag placement, and paragraph length expectations.

5. **Add engagement hooks**: Every platform values different engagement actions. Include specific CTAs (call-to-action) relevant to the platform.

6. **Test iteratively**: After creating a prompt, test it with 5-10 different topics and refine based on output quality.

## How to Add a New Platform

### Step 1: Create the Prompt File

Create a new `.txt` file in the `prompts/` directory:

```
prompts/
  newplatform.txt
```

Follow this template structure:

```
You are a [platform] content creator...

【CONTENT STRUCTURE】
1. [Section]: Description
2. [Section]: Description
...

【STYLE GUIDELINES】
- Tone: ...
- Use: ...
- Avoid: ...

【PLATFORM-SPECIFIC TIPS】
- Algorithm considerations
- Cultural norms
- Formatting rules

【VARIABLES】
- {topic}: Content topic
- {language}: Output language
- {extra_instructions}: Additional user requirements
```

### Step 2: Register the Platform in `app.py`

Add the platform name to the `SUPPORTED_PLATFORMS` list:

```python
SUPPORTED_PLATFORMS: list[str] = [
    ...,
    "newplatform",
]
```

And add a description entry in the `/platforms` endpoint:

```python
"newplatform": "Platform Name - Brief description of content style",
```

### Step 3: Test the New Platform

```bash
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "newplatform",
    "topic": "test topic",
    "language": "en"
  }'
```

## Example: Customizing Tone and Style

### Scenario: Making LinkedIn posts more casual

You can adjust the tone by modifying the style guidelines section in `linkedin.txt`:

**Before (formal):**
```
- Tone: Professional, authoritative, data-driven
- Avoid: Slang, informal expressions, humor
```

**After (casual professional):**
```
- Tone: Friendly professional, conversational, relatable
- Use: Light humor, personal anecdotes, everyday language
- Avoid: Stiff corporate speak, excessive formality
```

### Scenario: Adding industry-specific jargon

For a tech-focused Zhihu prompt, add a domain section:

```
【领域术语】
- 在讨论AI话题时，可使用：大模型、prompt engineering、RAG、fine-tuning 等术语
- 保持术语准确，必要时附上中文解释
```

### Scenario: Using extra_instructions at runtime

Users can customize output without modifying prompts by passing `extra_instructions`:

```json
{
  "platform": "twitter",
  "topic": "AI trends in 2025",
  "extra_instructions": "Write in a sarcastic, humorous tone. Include 2 relevant memes references."
}
```

This allows per-request customization while keeping the base prompt stable.
