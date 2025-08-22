import os
import json
import aiohttp
import discord
from discord import app_commands
from dotenv import load_dotenv
import asyncio

# Loading values from the .env file
load_dotenv()

# Loading tokens from environment
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ORION_API_TOKEN = os.getenv("ORION_API_TOKEN")
ORION_BASE = "https://api.orion-security.pro/v1"

print("Script is running.")
print(f"Token: {DISCORD_TOKEN}")

if not DISCORD_TOKEN:
    print("Token is not set!")
else:
    print(f"Token: {DISCORD_TOKEN}")

# ==== YOUR WHITELIST (Discord user_id -> seller_id in Orion) ====
SELLER_MAP = {
    858781827850698792: 230,  # Davca
    # 987654321098765432: 194,  # Seller 2
}

# Optional product preferences (simplifies /genkey)
PRODUCTS = {
    "spoof-1d": (225, 91),
    "spoof-3d": (225, 97),
    "spoof-7d": (225, 94),
    "spoof-15d": (225, 98),
    "spoof-30d": (225, 95),
    "spoof-life": (225, 96),
    "fortnite-1d": (226, 91),
    "fortnite-3d": (226, 97),
    "fortnite-7d": (226, 94),
    "fortnite-15d": (226, 98),
    "fortnite-30d": (226, 95),
    "fortnite-life": (226, 96),
}

# Discord client and commands
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# --------- Helper HTTP call to Orion API ----------
async def orion_post(session: aiohttp.ClientSession, path: str, payload: dict):
    headers = {
        "Authorization": f"Bearer {ORION_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    async with session.post(f"{ORION_BASE}{path}", headers=headers, json=payload) as resp:
        text = await resp.text()
        print(f"POST {path} - Status: {resp.status} - Response: {text}")  # Logging the response
        if 200 <= resp.status < 300:
            try:
                return await resp.json()
            except Exception:
                return {"raw": text}
        raise RuntimeError(f"Orion API {resp.status}: {text}")

# --------- Function to create keys ----------
async def create_keys(session, product_id: int, duration_id: int, seller_id: int, amount: int = 1):
    payload = {
        "product_id": product_id,
        "duration_id": duration_id,
        "seller_id": seller_id,
        "amount": amount
    }
    return await orion_post(session, "/keys", payload)

# --------- Function to reset HWID ----------
async def reset_hwid(session, key_code: str):
    path = f"/keys/{key_code}/reset-hwid"
    return await orion_post(session, path, {})

# --------- Function to delete a key ----------
async def delete_key(session, key_code: str):
    path = f"/keys/{key_code}"
    return await orion_delete(session, path)

# --------- Slash commands ----------
@tree.command(name="genkey", description="Generates a key(s). Supports both preferences and manual input.")
async def genkey(
    interaction: discord.Interaction, 
    product: str, 
    duration: str = "1d",  # Default duration "1d"
    amount: int = 1
):
    print(f"Creating key for: {product}, {duration}, {amount}")  # Logging for diagnostics

    product_map = {
        "Fortnite": 226,
        "Temp Spoofer": 225
    }

    duration_map = {
        "1d": 91,
        "3d": 97,
        "7d": 94,
        "30d": 95,
        "lifetime": 96
    }

    if product not in product_map:
        return await interaction.response.send_message("Invalid product. Choose between 'Fortnite' or 'Temp Spoofer'.", ephemeral=True)

    if duration not in duration_map:
        return await interaction.response.send_message("Invalid duration. Choose between '1d', '3d', '7d', '30d', or 'lifetime'.", ephemeral=True)

    product_id = product_map[product]
    duration_id = duration_map[duration]

    seller_id = SELLER_MAP.get(interaction.user.id)
    if not seller_id:
        return await interaction.response.send_message("You don't have reseller access.", ephemeral=True)

    amount = max(1, min(100, amount))
    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        async with aiohttp.ClientSession() as session:
            data = await create_keys(session, product_id, duration_id, seller_id, amount)
        keys = data.get("data") if isinstance(data, dict) else data
        if isinstance(keys, list):
            keys_text = "\n".join(f"`{k}`" for k in keys)
        else:
            keys_text = "```json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```"
        await interaction.followup.send(
            f"✅ **{amount}** key(s) generated\nProduct: `{product}` | Duration: `{duration}` | Seller: `{seller_id}`\n{keys_text}",
            ephemeral=True
        )
    except asyncio.TimeoutError:
        print("❌ Timeout occurred during API call.")
        await interaction.followup.send("❌ Timeout occurred during API call.", ephemeral=True)
    except Exception as e:
        print(f"❌ Error generating key: {e}")  # Error logging
        await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

# Synchronizing commands for the server
@client.event
async def on_ready():
    await tree.sync()  # Synchronizing commands globally across the server
    print(f"✅ Commands have been synchronized for bot: {client.user}")

client.run(DISCORD_TOKEN)
