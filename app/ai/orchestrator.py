"""
This is the "AI orchestrator" - the brain of our assistant.

It pulls conversation history and the user's known profile from the
database, detects the language of the user's latest message, and
supports tool calling with exactly three live-data sources:
- get_nse_stock_price - NSE India (Indian stocks)
- get_index_level - NSE India (Nifty/Bank Nifty)
- get_stock_quote - Finnhub (US stocks)
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
    timeout=20.0,
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

# handlers.py tags every PDF-derived message with this marker (see
# handle_document_message). We check for it here to detect "document
# mode" - a turn where the user is asking about an uploaded document.
DOCUMENT_MARKER = "[User uploaded a PDF"

# Same idea for images (see handle_photo_message). Images only get
# analyzed once, at upload time - the description/answer generated
# then is all the model will ever "see" of that image again. Without
# a reminder, the model sometimes invents a plausible-sounding value
# for something not captured in that description, instead of saying
# it doesn't have it.
IMAGE_MARKER = "[User sent an image]"

IMAGE_MODE_INSTRUCTION = (
    "\n\nNote: earlier in this conversation, an image was analyzed and "
    "its content was described in the conversation history. That "
    "description is ALL you have of that image - you cannot look at it "
    "again. If this question asks about something from that image and "
    "the answer isn't in the description already given, say plainly you "
    "don't have that detail from the image - do not guess or invent a "
    "number."
)

# Live-data tools available in every normal turn - all excluded in
# document mode (see below).
STOCK_TOOL_NAMES = {"get_nse_stock_price", "get_stock_quote", "get_index_level", "get_company_news"}

# In document mode we deliberately drop the live-data tools. This is
# the fix for the "Apple closed at $313" hallucination: the model had
# access to get_stock_quote in the same turn as the PDF text, got
# confused about which one to trust, and ended up inventing a number
# instead of using either. Removing the tools removes that ambiguity -
# the only thing left to answer from is the document text itself.
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

    # Document mode: was a document uploaded anywhere in this
    # conversation (not just the latest message)? Checking only the
    # latest message meant a follow-up like "isme AAPL ka price kya
    # hai" (asked one turn AFTER the PDF upload) lost the strict
    # grounding entirely - the model regained access to live-price
    # tools and answered with a real (but contextually misleading)
    # live quote instead of correctly saying AAPL isn't in the
    # document. Checking the full history keeps grounding active for
    # every follow-up about that document, for as long as it's still
    # in the last 10 messages of context.
    is_document_turn = any(
        m["role"] == "user" and DOCUMENT_MARKER in m["content"]
        for m in messages
        if isinstance(m.get("content"), str)
    )
    active_tools = DOCUMENT_MODE_TOOLS if is_document_turn else TOOLS

    # Image mode: was an image analyzed anywhere in this conversation?
    # Doesn't restrict tools (a live price lookup after discussing an
    # image is still valid) - just reminds the model not to invent
    # details about the image beyond what was actually captured.
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
        if has_image_context and not is_document_turn:
            tag += IMAGE_MODE_INSTRUCTION
        messages[-1] = {
            "role": "user",
            "content": f"{original_text}{tag}",
        }

    profile_updates = {}
    max_rounds = 5
    # Document turns tend to involve longer, multi-part answers (several
    # questions about one report in one message) - give them more room
    # than a typical short chat reply needs.
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
                # The model returned nothing usable (can happen when a
                # single message packs in many questions at once, or a
                # response gets cut off). Never forward an empty string
                # to Telegram - it hard-crashes the send call.
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