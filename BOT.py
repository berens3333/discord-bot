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
SANCIONES_ARCHIVO = "sanciones.json"

def cargar_sanciones():
    if os.path.exists(SANCIONES_ARCHIVO):
        with open(SANCIONES_ARCHIVO, "r") as f:
            return json.load(f)
    return {}

def guardar_sanciones(data):
    with open(SANCIONES_ARCHIVO, "w") as f:
        json.dump(data, f, indent=2)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def sancion(ctx, miembro: discord.Member, *, motivo: str):
    """Registra una sanción. Uso: !sancion @usuario motivo"""
    data = cargar_sanciones()
    uid = str(miembro.id)
    if uid not in data:
        data[uid] = []
    data[uid].append({
        "motivo": motivo,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "por": ctx.author.display_name
    })
    guardar_sanciones(data)
    total = len(data[uid])
    await ctx.send(f"⚠️ Sanción registrada a **{miembro.display_name}**.\nMotivo: {motivo}\nTotal de avisos: **{total}**")
    if total >= 2:
        await ctx.send(f"🚨 **{miembro.display_name}** lleva {total} avisos. Considera expulsarlo.")

@bot.command()
async def sanciones(ctx, miembro: discord.Member):
    """Ver sanciones de un miembro. Uso: !sanciones @usuario"""
    data = cargar_sanciones()
    uid = str(miembro.id)
    if uid not in data or not data[uid]:
        await ctx.send(f"✅ {miembro.display_name} no tiene sanciones.")
        return
    lineas = [f"**Sanciones de {miembro.display_name}:**"]
    for i, s in enumerate(data[uid], 1):
        fecha = datetime.fromisoformat(s['fecha']).strftime("%d/%m/%Y")
        lineas.append(f"{i}. `{fecha}` — {s['motivo']} *(por {s['por']})*")
    await ctx.send("\n".join(lineas))

@bot.command()
@commands.has_permissions(manage_roles=True)
async def limpiar_sanciones(ctx, miembro: discord.Member):
    """Borra todas las sanciones de un miembro. Uso: !limpiar_sanciones @usuario"""
    data = cargar_sanciones()
    uid = str(miembro.id)
    if uid in data:
        del data[uid]
        guardar_sanciones(data)
    await ctx.send(f"✅ Sanciones de **{miembro.display_name}** eliminadas.")
TICKETS_ARCHIVO = "tickets.json"

def cargar_tickets():
    if os.path.exists(TICKETS_ARCHIVO):
        with open(TICKETS_ARCHIVO, "r") as f:
            return json.load(f)
    return {}

def guardar_tickets(data):
    with open(TICKETS_ARCHIVO, "w") as f:
        json.dump(data, f, indent=2)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def ticket(ctx, *, nombre: str):
    """Abre el proceso de votación para un ticket. Uso: !ticket NombreDelJugador"""
    data = cargar_tickets()
    clave = nombre.lower()
    if clave in data and data[clave]["estado"] == "pendiente":
        await ctx.send(f"⚠️ Ya hay un ticket abierto para **{nombre}**.")
        return
    data[clave] = {
        "nombre": nombre,
        "estado": "pendiente",
        "votos_si": [],
        "votos_no": [],
        "abierto_por": ctx.author.display_name,
        "fecha": datetime.now(timezone.utc).isoformat()
    }
    guardar_tickets(data)
    await ctx.send(f"🎫 Ticket abierto para **{nombre}**.\nEl staff puede votar con `!votar {nombre} si/no`")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def votar(ctx, nombre: str, voto: str):
    """Vota por un ticket. Uso: !votar NombreDelJugador si/no"""
    data = cargar_tickets()
    clave = nombre.lower()
    voter = str(ctx.author.id)
    voto = voto.lower()

    if clave not in data or data[clave]["estado"] != "pendiente":
        await ctx.send(f"❌ No hay ningún ticket abierto para **{nombre}**.")
        return
    if voto not in ("si", "no"):
        await ctx.send("❌ El voto debe ser `si` o `no`.")
        return
    if voter in data[clave]["votos_si"] or voter in data[clave]["votos_no"]:
        await ctx.send("⚠️ Ya has votado para este ticket.")
        return

    if voto == "si":
        data[clave]["votos_si"].append(voter)
    else:
        data[clave]["votos_no"].append(voter)

    guardar_tickets(data)
    total_si = len(data[clave]["votos_si"])
    total_no = len(data[clave]["votos_no"])
    await ctx.send(f"✅ Voto registrado.\n**{nombre}** — 👍 {total_si} a favor / 👎 {total_no} en contra")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def resultado(ctx, *, nombre: str):
    """Cierra la votación y muestra el resultado. Uso: !resultado NombreDelJugador"""
    data = cargar_tickets()
    clave = nombre.lower()

    if clave not in data or data[clave]["estado"] != "pendiente":
        await ctx.send(f"❌ No hay ningún ticket abierto para **{nombre}**.")
        return

    total_si = len(data[clave]["votos_si"])
    total_no = len(data[clave]["votos_no"])
    entra = total_si >= 4

    data[clave]["estado"] = "aceptado" if entra else "rechazado"
    guardar_tickets(data)

    if entra:
        await ctx.send(f"✅ **{nombre}** entra en la banda.\n👍 {total_si} a favor / 👎 {total_no} en contra")
    else:
        await ctx.send(f"❌ **{nombre}** no entra en la banda.\n👍 {total_si} a favor / 👎 {total_no} en contra")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def tickets(ctx):
    """Lista todos los tickets pendientes de votación."""
    data = cargar_tickets()
    pendientes = [(v["nombre"], len(v["votos_si"]), len(v["votos_no"])) for v in data.values() if v["estado"] == "pendiente"]

    if not pendientes:
        await ctx.send("No hay tickets abiertos.")
        return

    lineas = ["**Tickets pendientes de votación:**"]
    for nombre, si, no in pendientes:
        lineas.append(f"• **{nombre}** — 👍 {si} / 👎 {no}")
    await ctx.send("\n".join(lineas))

    
token = os.environ.get("DISCORD_TOKEN")
print(f"Token found: {token is not None}")
bot.run(token)
