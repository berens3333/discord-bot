import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import json
import os
from dotenv import load_dotenv
load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

ARCHIVO = "actividad.json"

# Última actividad de texto y de voz por usuario (claves como string)
last_text = {}
last_voice = {}

def cargar_datos():
    global last_text, last_voice
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO, "r") as f:
            data = json.load(f)
            last_text = {k: datetime.fromisoformat(v) for k, v in data.get("last_text", {}).items()}
            last_voice = {k: datetime.fromisoformat(v) for k, v in data.get("last_voice", {}).items()}

def guardar_datos():
    data = {
        "last_text": {k: v.isoformat() for k, v in last_text.items()},
        "last_voice": {k: v.isoformat() for k, v in last_voice.items()}
    }
    with open(ARCHIVO, "w") as f:
        json.dump(data, f)

@bot.event
async def on_ready():
    cargar_datos()
    print(f"Bot conectado como {bot.user}")

@bot.event
async def on_message(message):
    if not message.author.bot:
        last_text[str(message.author.id)] = datetime.now(timezone.utc)
        guardar_datos()
    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
    now = datetime.now(timezone.utc)
    last_voice[str(member.id)] = now
    guardar_datos()

    if before.channel is None and after.channel is not None:
        print(f"[VOZ] {member.display_name} entró a {after.channel.name} - {now}")
    elif before.channel is not None and after.channel is None:
        print(f"[VOZ] {member.display_name} salió de {before.channel.name} - {now}")
    elif before.channel != after.channel:
        print(f"[VOZ] {member.display_name} se movió de {before.channel.name} a {after.channel.name} - {now}")

@bot.command()
async def voz_ahora(ctx):
    """Muestra el estado de todos los canales de voz."""
    lineas = []
    for vc in ctx.guild.voice_channels:
        miembros = [m.display_name for m in vc.members if not m.bot]
        if miembros:
            nombres = ", ".join(miembros)
            lineas.append(f"🔊 **{vc.name}**: {nombres}")
        else:
            lineas.append(f"⚪ **{vc.name}**: (vacío)")

    await ctx.send("\n".join(lineas))

@bot.command()
async def inactivos_voz(ctx, dias: int = 30):
    """Lista miembros sin actividad en canales de voz en X días."""
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    inactivos_list = []

    for member in ctx.guild.members:
        if member.bot:
            continue
        ultima = last_voice.get(str(member.id))
        if ultima is None or ultima < limite:
            inactivos_list.append(member.display_name)

    if not inactivos_list:
        await ctx.send(f"Todos han usado voz en los últimos {dias} días.")
        return

    texto = "\n".join(inactivos_list)
    await ctx.send(f"**Inactivos en voz (más de {dias} días sin conectarse a voz):**\n{texto}")

@bot.command()
async def inactivos(ctx, dias: int = 30):
    """Lista miembros sin actividad (texto NI voz) en X días. Uso: !inactivos 30"""
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    inactivos_list = []

    for member in ctx.guild.members:
        if member.bot:
            continue
        ultima_actividad = max(
            last_text.get(str(member.id), datetime.min.replace(tzinfo=timezone.utc)),
            last_voice.get(str(member.id), datetime.min.replace(tzinfo=timezone.utc))
        )
        if ultima_actividad < limite:
            inactivos_list.append(member.display_name)

    if not inactivos_list:
        await ctx.send(f"No hay miembros inactivos hace más de {dias} días.")
        return

    texto = "\n".join(inactivos_list)
    await ctx.send(f"**Inactivos (sin texto ni voz en {dias} días):**\n{texto}")

token = os.environ.get("DISCORD_TOKEN")
print(f"Token found: {token is not None}")
bot.run(token)
