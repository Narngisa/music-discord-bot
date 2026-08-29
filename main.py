import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

if not TOKEN:
    raise RuntimeError("Not found TOKEN in environments. Pls setting TOKEN in .env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True


class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.load_extension("cogs.music")

        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(f"Synced {len(synced)} commands (Guild: {GUILD_ID})")
        else:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} commands global.")

    async def on_ready(self):
        if self.user:
            logger.info(f"Logged in as {self.user} (ID: {self.user.id})")


bot = MusicBot()

if __name__ == "__main__":
    bot.run(TOKEN)