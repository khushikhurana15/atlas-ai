"""
Analyzes images sent by the user using Groq's vision model - useful
for screenshots of stock charts, portfolios, financial documents, or
any image the user wants to ask about.
"""

import base64
from datetime import date
from openai import OpenAI
from app.config import GROQ_API_KEY

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    timeout=30.0,
)


def analyze_image(image_bytes: bytes, caption: str = "") -> str:
    """
    Sends an image to Groq's vision model and returns a text
    description/answer. If the user included a caption (like a
    question), that's used as the prompt; otherwise a general
    financial-context description is requested.
    """
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    prompt = caption.strip() if caption.strip() else (
        "Describe what's in this image, focusing on anything financially "
        "relevant (stock charts, numbers, company names, tables, etc.) "
        "if present."
    )

    prompt += (
        "\n\nIMPORTANT: This is the ONLY time this image will be analyzed - "
        "any follow-up questions later in the conversation will rely "
        "entirely on what you write now, without seeing the image again. "
        "So: answer the question above, but ALSO list out every other "
        "clearly-legible data point in the image (e.g. if it's a table of "
        "stocks, list each symbol with its price/change; if it's a chart, "
        "note the key visible values) in a few compact bullet points. "
        "Do not skip visible data just because it wasn't directly asked "
        "about - a later question may need it."
    )

    prompt += (
        f"\n\nToday's actual real-world date is {date.today().isoformat()} - "
        f"use this, not any assumption from your training data, if the "
        f"image or your answer involves reasoning about what year/date it "
        f"currently is. Do not claim a date in the image is 'in the "
        f"future' or otherwise wrong based on your own guess of the "
        f"current year."
    )

    prompt += (
        "\n\nBe careful with charts/graphs: only state an exact number, "
        "date, or value if you can clearly read it in the image. If two "
        "lines' relative position or an exact figure isn't clearly "
        "legible, say so explicitly instead of guessing - a cautious "
        "'I can't read that precisely' is better than a confident wrong "
        "answer. For line charts specifically, do NOT claim a precise "
        "final gap, exact peak time, or which line ends closer/further "
        "apart unless the endpoints are unambiguous in the image - give "
        "only the broad, clearly-visible trend (e.g. 'both rose, one "
        "stayed slightly higher') and tell the user to check a live "
        "tool for exact closing figures."
    )

    response = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ],
        temperature=0.1,
        max_tokens=600,
    )

    return response.choices[0].message.content