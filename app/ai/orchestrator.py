"""
This is the "AI orchestrator" - the brain of our assistant.

It pulls conversation history and the user's known profile from the
database, detects the language of the user's latest message, and
supports tool calling with live-data sources:
- get_nse_stock_price - NSE India (Indian stocks)
- get_index_level - NSE India (Nifty/Bank Nifty)
- get_stock_quote - Finnhub (US stocks)
- get_company_news - Finnhub (recent news)
plus update_user_profile for onboarding/personalization.

Every tool call is wrapped so a Python exception can never crash the
whole reply - it just becomes an error the AI can see and respond to
honestly.
"""

import re
import json
from datetime import date
from openai import OpenAI
from app.config import GROQ_API_KEY
from app.tools.finnhub_tool import get_stock_quote
from app.tools.nse_tool import get_nse_stock_price
from app.tools.index_tool import get_index_level
from app.tools.news_tool import get_company_news
from app.tools.profile_tool import update_user_profile

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    timeout=30.0,
)

HINGLISH_WORDS = {
    "hai", "hain", "tha", "thi", "the", "ho", "hoon", "kya", "kyu", "kyun",
    "kaise", "kaisi", "kaisa", "kab", "kaha", "kahan", "kaun", "kitna",
    "kitni", "mein", "mai", "main", "aap", "aapko", "aapka", "aapki",
    "tum", "tumhe", "tumhara", "tumhari", "mujhe", "mera", "meri",
    "hum", "humein", "ye", "yeh", "woh", "wo", "iska", "uska",
    "aur", "lekin", "magar", "nahi", "nahin", "haan", "abhi", "phir",
    "batao", "bata", "karo", "karna", "chahiye", "sakta", "sakti",
    "sakte", "raha", "rahi", "rahe", "batana", "acha", "accha",
}


def detect_language(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text):
        return "Hindi"
    words = re.findall(r"[a-zA-Z]+", text.lower())
    if not words:
        return "English"
    hinglish_count = sum(1 for w in words if w in HINGLISH_WORDS)
    ratio = hinglish_count / len(words)
    if ratio > 0.15:
        return "Hinglish"
    return "English"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_nse_stock_price",
            "description": "Get the current live price for an Indian (NSE-listed) stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Plain NSE symbol, e.g. RELIANCE, TCS, HDFCBANK."}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_quote",
            "description": "Get the current live price and today's change for a US stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "US stock ticker symbol, e.g. AAPL, TSLA."}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_index_level",
            "description": (
                "Get the current live level of a market index like Nifty 50 or Bank Nifty. "
                "ALWAYS use this for any general 'market update', 'market kaisa hai', or "
                "index-level question - it is the correct tool for that, not a guess."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "index_name": {"type": "string", "description": "e.g. 'nifty', 'nifty 50', 'bank nifty', 'sensex'."}
                },
                "required": ["index_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_news",
            "description": (
                "Get recent news headlines (last 7 days) for a company. "
                "Use this for any question about a company's recent news, "
                "developments, or 'what's happening with X' - not for "
                "prices. Coverage is strongest for US-listed companies."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL, TSLA, RELIANCE."}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_user_profile",
            "description": (
                "Call this whenever the user shares their role (investor, analyst, "
                "founder, student) or interests (companies/sectors). Only when they "
                "actually shared it - don't guess."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "e.g. 'investor', 'analyst', 'founder', 'student'."},
                    "interests": {"type": "string", "description": "Comma-separated companies/sectors."},
                },
            },
        },
    },
]

AVAILABLE_FUNCTIONS = {
    "get_nse_stock_price": get_nse_stock_price,
    "get_stock_quote": get_stock_quote,
    "get_index_level": get_index_level,
    "get_company_news": get_company_news,
    "update_user_profile": update_user_profile,
}

DOCUMENT_MARKER = "[User uploaded a PDF"
IMAGE_MARKER = "[User sent an image]"

IMAGE_MODE_INSTRUCTION = (
    "\n\nNote: earlier in this conversation, one or more images were "
    "analyzed and described in the conversation history. Each "
    "description is ALL you know about that specific image - you "
    "cannot look at it again. If this question is about something in "
    "an image, use ONLY that image's own description text to answer - "
    "never substitute a number for the same company/topic that you "
    "recall from elsewhere in the conversation (e.g. a live price "
    "fetched by a tool earlier, or a different image). The same "
    "company can appear multiple times in this conversation at "
    "different moments and from different sources (a live quote vs. "
    "a screenshot) - these are NOT interchangeable, even if the "
    "company name matches. If the specific detail isn't present in "
    "that image's own description, say plainly you don't have that "
    "detail from the image - do not fill the gap with a number from "
    "anywhere else."
)

STOCK_TOOL_NAMES = {"get_nse_stock_price", "get_stock_quote", "get_index_level", "get_company_news"}

# Only the turn where PDF text is FIRST introduced gets tools removed
# entirely (highest-risk moment for blending document text with a
# tool call in the same turn). Any later, unrelated question (e.g.
# "TCS ka price?") should NOT be blocked just because a PDF was
# uploaded earlier - it should use tools normally.
DOCUMENT_MODE_TOOLS = [t for t in TOOLS if t["function"]["name"] not in STOCK_TOOL_NAMES]

DOCUMENT_MODE_INSTRUCTION = (
    "\n\nSTRICT DOCUMENT MODE: The user's message includes text extracted "
    "from a document they uploaded. For this turn, answer ONLY using that "
    "document text (plus the recent conversation for context). Do not use "
    "outside knowledge, do not estimate, and do not invent any number, "
    "price, date, or fact that isn't explicitly present in the document "
    "text. If the answer isn't in the document, say plainly it isn't "
    "mentioned in the document - do not guess or fill the gap. You have "
    "no live-data tools this turn; do not claim to have checked live data."
)

# Used for any LATER turn in a conversation that once had a document
# uploaded - tools stay ON here, this just prevents the model from
# blending document content with live-tool data for unrelated questions.
DOCUMENT_CONTEXT_INSTRUCTION = (
    "\n\nNote: earlier in this conversation, a document was uploaded and "
    "its extracted text was shown then. If this question is about that "
    "document's content, use ONLY that document text - never invent or "
    "estimate. If this question is about something else entirely (e.g. "
    "a different company's live price), answer it normally using your "
    "tools as usual - do not refuse just because a document was uploaded "
    "earlier; the document only restricts answers about the document "
    "itself, not unrelated questions."
)


SYSTEM_PROMPT = """You are Atlas - an experienced financial analyst assistant
who helps finance professionals on Telegram.

Rules:
- Keep a natural, conversational tone - like a smart colleague talking to them.
- LANGUAGE: You will be told exactly which language to reply in, in a tag
  attached to the user's latest message. Always follow that tag exactly,
  regardless of what language earlier messages in the conversation were in.
- LENGTH: Telegram is a mobile chat app, long replies don't work well here.
  Keep the default reply under 3-4 lines. If a list is needed, keep it to
  max 3-4 bullet points, one line each. Only give a longer answer if the
  user explicitly asks for detail.
- If the question is ambiguous, ask for clarification in 1-2 lines.
- For Indian stocks, use get_nse_stock_price. For US stocks, use
  get_stock_quote. For ANY general "market update" or index question, you
  MUST call get_index_level - never say you don't have data without
  calling it first. For questions about a company's recent news or
  developments (not price), call get_company_news. Never mention a
  tool's name in your reply.
  If a tool returns an error, tell the user honestly you couldn't find
  live data for that - never guess or invent a price or statistic.
  For anything these tools don't cover (news, filings, general company
  info), say in one line you don't have that, and STOP - never invent
  statistics, percentages, or "recent trends" as if real.
- GROUNDING: Only state a number, price, date, or fact if it came from
  a tool result, the document text given to you, or something the user
  themselves said earlier in this conversation. If you're not sure
  where a fact would come from, don't say it - say you don't have it.
- ONBOARDING: You'll be told what you know about this user's role/interests.
  If unknown, casually ask ONCE, never like a form - weave it into your
  reply, don't make it the whole reply. "interests" should capture both
  what they follow AND what they'd like tracked/watchlisted (companies,
  sectors, topics) - if they mention either, that counts. When they
  share role or interests, call update_user_profile to save it. If they
  ignore the question and ask something else instead, just answer that -
  never repeat the onboarding question again in the same conversation.
- You're given recent conversation history - use it for context.
- Formatting: Telegram Markdown only - single asterisk *bold* (not **),
  underscore _italic_. No tables - use bullet points (- or •).
- CURRENCY: Every price tool result includes a "currency" field (USD or
  INR). Always show the matching symbol - $ for USD, ₹ for INR. Never
  default to ₹ for a US stock or $ for an Indian stock.
"""


def _run_tool_safely(function_name: str, function_args: dict) -> dict:
    function_to_call = AVAILABLE_FUNCTIONS.get(function_name)
    if not function_to_call:
        return {"error": f"Unknown tool '{function_name}'"}
    try:
        return function_to_call(**function_args)
    except Exception as e:
        return {"error": f"Tool '{function_name}' failed unexpectedly: {e}"}


def get_ai_reply(conversation_history: list, user_profile: dict) -> tuple:
    profile_context = (
        f"What you currently know about this user - "
        f"role: {user_profile.get('role') or 'unknown'}, "
        f"interests: {user_profile.get('interests') or 'unknown'}."
    )

    date_context = (
        f"Today's actual real-world date is {date.today().isoformat()} - "
        f"use this, not any assumption from your training data, for any "
        f"reasoning about what year/date it currently is."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": date_context},
        {"role": "system", "content": profile_context},
    ] + list(conversation_history)

    # Strict mode (tools OFF) only for the turn where PDF text is
    # literally being introduced right now. Later follow-ups keep
    # tools ON (see has_document_context / DOCUMENT_CONTEXT_INSTRUCTION).
    latest_is_document_turn = (
        messages[-1]["role"] == "user"
        and isinstance(messages[-1].get("content"), str)
        and DOCUMENT_MARKER in messages[-1]["content"]
    )
    has_document_context = any(
        m["role"] == "user" and isinstance(m.get("content"), str) and DOCUMENT_MARKER in m["content"]
        for m in messages
    )
    is_document_turn = latest_is_document_turn
    active_tools = DOCUMENT_MODE_TOOLS if is_document_turn else TOOLS

    has_image_context = any(
        m["role"] == "user" and isinstance(m.get("content"), str) and IMAGE_MARKER in m["content"]
        for m in messages
    )

    if messages[-1]["role"] == "user":
        original_text = messages[-1]["content"]
        language = detect_language(original_text)
        tag = f"\n\n[SYSTEM TAG: reply in {language}]"
        if is_document_turn:
            tag += DOCUMENT_MODE_INSTRUCTION
        elif has_document_context:
            tag += DOCUMENT_CONTEXT_INSTRUCTION
        if has_image_context and not is_document_turn:
            tag += IMAGE_MODE_INSTRUCTION
        messages[-1] = {
            "role": "user",
            "content": f"{original_text}{tag}",
        }

    profile_updates = {}
    max_rounds = 5
    max_tokens = 1200 if is_document_turn else 700

    for _ in range(max_rounds):
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            max_tokens=max_tokens,
            temperature=0.1,
            messages=messages,
            tools=active_tools,
        )
        ai_message = response.choices[0].message

        if not ai_message.tool_calls:
            reply = (ai_message.content or "").strip()
            if not reply:
                reply = (
                    "Ye ek saath thoda zyada ho gaya, main poora process "
                    "nahi kar paya. Ek-ek karke pooch sakte ho?"
                )
            return reply, profile_updates

        messages.append(ai_message)

        for tool_call in ai_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            result = _run_tool_safely(function_name, function_args)

            if function_name == "update_user_profile":
                profile_updates.update(
                    {k: v for k, v in result.items() if k in ("role", "interests")}
                )

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    return "Sorry, I'm having trouble right now. Please try again in a moment.", profile_updates