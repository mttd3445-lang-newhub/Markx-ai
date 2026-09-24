#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "📦 สร้าง virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

if ! python -c "import discord" 2>/dev/null; then
    echo "📦 ติดตั้ง dependencies..."
    pip install -r requirements.txt
fi

if [ ! -f ".env" ]; then
    echo "📝 สร้าง .env จาก template..."
    cp .env.example .env
    echo ""
    echo "⚠️  แก้ .env ใส่ DISCORD_TOKEN และ ZAI_API_KEY ก่อนรันใหม่!"
    echo "    nano .env"
    exit 1
fi

mkdir -p logs
echo "🚀 เริ่มบอท..."
exec python -u bot.py