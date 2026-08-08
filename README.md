# Atlas - AI Financial Assistant (Phase 1)

Ye Phase 1 hai: basic conversational Telegram bot jo Claude AI se
baat karwata hai. Abhi memory, financial data, documents kuch bhi
nahi hai - bas ek working bot jisse tum baat kar sako.

## Setup Steps (line by line follow karo)

### 1. Telegram Bot Banao

1. Telegram khol ke `@BotFather` ko search karo aur message karo.
2. `/newbot` type karo.
3. Bot ka naam aur username set karo (username `_bot` se end hona chahiye).
4. BotFather tumhe ek **token** dega jaisa: `123456789:ABCdefGhIJKlmNoPQRstuVWXyz`
   Ise safe rakho.

### 2. Anthropic API Key Lo

1. https://console.anthropic.com pe jao aur account banao.
2. API Keys section mein jaake ek naya key generate karo.

### 3. Python Environment Setup

Terminal mein project folder ke andar jaake ye commands chalao:

```bash
# Virtual environment banao (isse dependencies alag rehte hain)
python -m venv venv

# Activate karo
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows

# Dependencies install karo
pip install -r requirements.txt
```

### 4. Environment Variables Set Karo

```bash
cp .env.example .env
```

Ab `.env` file kholo aur apni actual keys daalo:

```
TELEGRAM_BOT_TOKEN=tumhara_telegram_token_yahan
ANTHROPIC_API_KEY=tumhari_anthropic_key_yahan
```

### 5. Bot Chalao

```bash
python -m app.main
```

Terminal mein "Atlas bot chal raha hai..." dikhega. Ab Telegram khol ke
apne bot ko dhundo aur `/start` bhejo!

## Project Structure

```
atlas-assistant/
├── app/
│   ├── main.py              # Bot yahan se start hota hai
│   ├── config.py            # API keys yahan load hoti hain
│   ├── bot/
│   │   └── handlers.py      # Telegram messages yahan handle hote hain
│   └── ai/
│       └── orchestrator.py  # Claude AI ko yahan call karte hain
├── requirements.txt
└── .env.example
```

## Agla Kya Aayega (Phase 2+)

- **Database + Memory**: User profile, watchlist, conversation history save karna
- **Financial Data**: Live stock prices, company research
- **Documents**: PDF upload karke usse questions poochna
- **Scheduler**: Daily market briefing automatically bhejna
- **Google Integrations**: Gmail, Calendar connect karna
- **Voice & Image**: Voice messages aur images samajhna
