"""
bot.py — บอท Discord + Z.ai GLM เวอร์ชัน production-ready

ฟีเจอร์:
  • AI chat พร้อม memory ต่อ channel/user
  • @mention, DM, และห้อง auto-respond
  • Slash commands + prefix commands
  • อ่านไฟล์แนบ (.py, .js, .txt, .md, .json, ฯลฯ) วิเคราะห์/อธิบาย/แก้ไข
  • หลายบุคลิก (persona) สลับได้ด้วย /setpersona
  • Image generation ผ่าน /image <prompt>
  • HTTP health check endpoint + stats
  • Logging ลงไฟล์แบบ rotation
  • รองรับ Docker + systemd deployment
"""
import asyncio
import sys
import time

import discord
from discord import app_commands
from discord.ext import commands

from ai_client import AIClient, AIClientError
from attachments import read_attachments, format_files_for_prompt
from config import (
    AUTO_RESPOND_CHANNEL_IDS, COMMAND_PREFIX, DISCORD_TOKEN,
    HEALTH_CHECK_ENABLED, MSG_CLEARED, MSG_ERROR, MSG_NO_TOKEN,
    MSG_PONG, OWNER_IDS, STATS_ENABLED, USE_SLASH_COMMANDS,
)
from health import start_health_server, update_status, HealthHandler
from logger import setup_logger
from memory import ConversationMemory
from personas import list_personas, get_persona

log = setup_logger("z-bot")

# ---------- สร้าง instances ----------
try:
    ai = AIClient()
    log.info("✅ AI client สร้างแล้ว (model=%s, base=%s)", ai.model, ai.base_url)
except AIClientError as e:
    log.error("❌ สร้าง AI client ไม่ได้: %s", e)
    print(f"❌ {e}")
    sys.exit(1)

memory = ConversationMemory()

# ---------- Discord intents ----------
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.dm_messages = True

bot = commands.Bot(
    command_prefix=COMMAND_PREFIX,
    intents=intents,
    help_command=None,
)


# ---------- ตัวช่วย ----------
def _memory_key(message: discord.Message) -> str:
    if isinstance(message.channel, (discord.DMChannel, discord.GroupChannel)):
        return f"dm:{message.author.id}"
    return f"ch:{message.channel.id}"


async def _call_ai(messages):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: ai.chat(messages))


async def _safe_send(channel, text: str):
    """ส่งข้อความ แบ่ง chunk ถ้าเกิน 2000 ตัวอักษร"""
    if not text:
        return
    chunk_size = 1900
    if len(text) <= chunk_size:
        await channel.send(text)
        return

    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > chunk_size:
            if current:
                chunks.append(current)
            current = line
        else:
            current = (current + "\n" + line) if current else line
    if current:
        chunks.append(current)

    final = []
    for c in chunks:
        while len(c) > chunk_size:
            final.append(c[:chunk_size])
            c = c[chunk_size:]
        final.append(c)

    for c in final:
        await channel.send(c)
        await asyncio.sleep(0.2)


def _bump_stat(key: str, n: int = 1):
    if STATS_ENABLED and hasattr(HealthHandler, "bot_status"):
        HealthHandler.bot_status[key] = HealthHandler.bot_status.get(key, 0) + n


# ---------- event handlers ----------
@bot.event
async def on_ready():
    log.info("✅ ล็อกอินแล้วในชื่อ %s (id=%s)", bot.user, bot.user.id)

    if USE_SLASH_COMMANDS:
        try:
            synced = await bot.tree.sync()
            log.info("Slash commands ลงทะเบียน %d คำสั่ง", len(synced))
        except Exception as e:
            log.warning("sync slash commands ไม่ได้: %s", e)

    log.info("📢 Auto-respond channels: %s",
             AUTO_RESPOND_CHANNEL_IDS or "(ไม่ได้ตั้ง)")
    log.info("🎭 Default persona: %s",
             get_persona(memory.get_persona_name("__default__"))["name"])

    if HEALTH_CHECK_ENABLED:
        start_health_server()

    update_status(
        guilds=len(bot.guilds),
        users=sum(g.member_count or 0 for g in bot.guilds),
    )

    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="แชทเป็นเพื่อน | /help"),
        )
    except Exception:
        pass


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.process_commands(message)
        return

    is_dm = isinstance(message.channel, (discord.DMChannel, discord.GroupChannel))
    is_mentioned = (
        bot.user in message.mentions
        or (message.reference and message.reference.resolved and
            getattr(message.reference.resolved, "id", None) == bot.user.id)
    )
    is_auto = not is_dm and message.channel.id in AUTO_RESPOND_CHANNEL_IDS

    has_attachments = bool(message.attachments)

    if not (is_dm or is_mentioned or is_auto):
        if not (is_mentioned and has_attachments):
            return

    file_contents, skipped = await read_attachments(message)

    content = message.clean_content.strip()
    bot_name = bot.user.display_name
    if content.startswith(f"@{bot_name}"):
        content = content[len(f"@{bot_name}"):].strip()

    if content and file_contents:
        full_prompt = content + "\n\n" + format_files_for_prompt(file_contents)
    elif file_contents:
        full_prompt = (
            "วิเคราะห์/อธิบาย/แก้ไขไฟล์ต่อไปนี้ตามที่เหมาะสม:\n\n"
            + format_files_for_prompt(file_contents)
        )
    else:
        full_prompt = content

    if skipped:
        full_prompt += "\n\n⚠️ ไฟล์ที่ข้าม: " + ", ".join(skipped)

    if not full_prompt:
        return

    if STATS_ENABLED:
        update_status(last_message_at=time.time())
        _bump_stat("messages_processed")

    async with message.channel.typing():
        key = _memory_key(message)
        memory.add_user_message(key, full_prompt)

        try:
            reply = await _call_ai(memory.get_history(key))
        except AIClientError as e:
            log.error("AI error: %s", e)
            _bump_stat("ai_errors")
            await _safe_send(message.channel, f"{MSG_ERROR}\n\n`{e}`")
            return
        except Exception as e:
            log.exception("unexpected error")
            _bump_stat("ai_errors")
            await _safe_send(message.channel, MSG_ERROR)
            return

        memory.add_assistant_message(key, reply)
        _bump_stat("ai_calls")

    try:
        await _safe_send(message.channel, reply)
    except discord.HTTPException as e:
        log.error("discord send error: %s", e)


# ---------- prefix commands ----------
@bot.command(name="ping")
async def ping_prefix(ctx: commands.Context):
    await ctx.send(MSG_PONG)


@bot.command(name="clear")
async def clear_prefix(ctx: commands.Context):
    key = f"dm:{ctx.author.id}" if isinstance(ctx.channel, (
        discord.DMChannel, discord.GroupChannel)) else f"ch:{ctx.channel.id}"
    memory.clear(key)
    await ctx.send(MSG_CLEARED)


@bot.command(name="help")
async def help_prefix(ctx: commands.Context):
    await ctx.send(_help_text())


@bot.command(name="persona")
async def persona_prefix(ctx: commands.Context, name: str = ""):
    if not name:
        await ctx.send(_persona_list())
        return
    key = f"dm:{ctx.author.id}" if isinstance(ctx.channel, (
        discord.DMChannel, discord.GroupChannel)) else f"ch:{ctx.channel.id}"
    if memory.set_persona(key, name.lower()):
        p = get_persona(name.lower())
        await ctx.send(f"🎭 บุคลิกถูกเปลี่ยนเป็น **{p['name']}**\n> {p['description']}")
    else:
        await ctx.send(f"❌ ไม่มี persona ชื่อ '{name}' — ลองดูรายการ: `{COMMAND_PREFIX}persona`")


# ---------- slash commands ----------
@bot.tree.command(name="ping", description="ตรวจสอบว่าบอทยังทำงานอยู่")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.send_message(MSG_PONG)


@bot.tree.command(name="clear", description="ล้างประวัติการสนทนาในห้องนี้")
async def clear_slash(interaction: discord.Interaction):
    if isinstance(interaction.channel, (discord.DMChannel, discord.GroupChannel)):
        key = f"dm:{interaction.user.id}"
    else:
        key = f"ch:{interaction.channel.id}"
    memory.clear(key)
    await interaction.response.send_message(MSG_CLEARED)


@bot.tree.command(name="help", description="แสดงวิธีใช้บอท")
async def help_slash(interaction: discord.Interaction):
    await interaction.response.send_message(_help_text())


@bot.tree.command(name="persona", description="ดูหรือตั้งบุคลิกของบอท")
@app_commands.describe(name="ชื่อ persona (เว้นว่างเพื่อดูรายการทั้งหมด)")
async def persona_slash(interaction: discord.Interaction, name: str = ""):
    if not name:
        await interaction.response.send_message(_persona_list())
        return
    if isinstance(interaction.channel, (discord.DMChannel, discord.GroupChannel)):
        key = f"dm:{interaction.user.id}"
    else:
        key = f"ch:{interaction.channel.id}"
    if memory.set_persona(key, name.lower()):
        p = get_persona(name.lower())
        await interaction.response.send_message(
            f"🎭 บุคลิกถูกเปลี่ยนเป็น **{p['name']}**\n> {p['description']}"
        )
    else:
        await interaction.response.send_message(f"❌ ไม่มี persona ชื่อ '{name}'")


@bot.tree.command(name="image", description="สร้างรูปจากข้อความ")
@app_commands.describe(prompt="คำอธิบายรูปที่ต้องการสร้าง")
async def image_slash(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    try:
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(None, lambda: ai.generate_image(prompt))
        if url:
            await interaction.followup.send(f"🎨 รูปสำหรับ: `{prompt}`\n{url}")
        else:
            await interaction.followup.send("❌ ไม่สามารถสร้างรูปได้")
    except AIClientError as e:
        await interaction.followup.send(f"❌ สร้างรูปไม่สำเร็จ: {e}")


@bot.tree.command(name="stats", description="ดูสถิติการใช้งานบอท")
async def stats_slash(interaction: discord.Interaction):
    s = HealthHandler.bot_status
    uptime = int(time.time() - s.get("started_at", time.time()))
    text = (
        "**📊 สถิติบอท**\n"
        f"⏱ ออนไลน์: {uptime//86400}d {(uptime%86400)//3600}h {(uptime%3600)//60}m\n"
        f"📨 ข้อความประมวลผล: {s.get('messages_processed', 0)}\n"
        f"🤖 การเรียก AI: {s.get('ai_calls', 0)}\n"
        f"⚠️ ข้อผิดพลาด: {s.get('ai_errors', 0)}\n"
        f"🏠 เซิร์ฟเวอร์: {s.get('guilds', 0)}\n"
        f"👥 ผู้ใช้รวม: {s.get('users', 0)}\n"
    )
    await interaction.response.send_message(text)


# ---------- helper text ----------
def _help_text() -> str:
    return (
        "**🤖 Z Bot — คำสั่งที่ใช้ได้**\n"
        f"`{COMMAND_PREFIX}ping` หรือ `/ping` — ตรวจสถานะบอท\n"
        f"`{COMMAND_PREFIX}clear` หรือ `/clear` — ล้างประวัติการสนทนา\n"
        f"`{COMMAND_PREFIX}persona` หรือ `/persona` — ดู/เปลี่ยนบุคลิก\n"
        f"`{COMMAND_PREFIX}help` หรือ `/help` — แสดงคำสั่งนี้\n"
        "`/image <prompt>` — สร้างรูปจากคำอธิบาย\n"
        "`/stats` — ดูสถิติการใช้งาน\n"
        "\n"
        "**วิธีคุยกับบอท**\n"
        "• ในเซิร์ฟเวอร์: @mention บอทแล้วพิมพ์ข้อความ\n"
        "• ใน DM: พิมพ์อะไรก็ได้ บอทจะตอบทันที\n"
        "• ในห้อง auto-respond: พิมพ์อะไรก็ได้ บอทจะตอบอัตโนมัติ\n"
        "• ส่งไฟล์ .py/.js/.txt แล้ว @mention เพื่อให้บอทวิเคราะห์\n"
    )


def _persona_list() -> str:
    lines = ["**🎭 Persona ทั้งหมด:**\n"]
    for key, name, desc in list_personas():
        lines.append(f"• `{key}` — **{name}**: {desc}")
    lines.append(f"\nใช้ `/persona <key>` เพื่อสลับ เช่น `/persona coder`")
    return "\n".join(lines)


# ---------- main ----------
def main():
    if not DISCORD_TOKEN or DISCORD_TOKEN.startswith("ใส่"):
        print(MSG_NO_TOKEN)
        sys.exit(1)

    log.info("🚀 กำลังเริ่มบอท...")
    log.info("📦 Model: %s | Auto-channels: %d | Owner IDs: %s",
             ai.model, len(AUTO_RESPOND_CHANNEL_IDS), OWNER_IDS or "(none)")

    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        log.info("หยุดบอทแล้ว (Ctrl+C)")
    except discord.LoginFailure:
        log.error("❌ Token ไม่ถูกต้อง — ตรวจสอบ DISCORD_TOKEN ใน .env")
        sys.exit(2)
    except Exception as e:
        log.exception("❌ บอท crash: %s", e)
        sys.exit(3)


if __name__ == "__main__":
    main()