# main.py
import discord
from discord.ext import commands
import asyncio
import logging
from config import Config
from utils.logger import setup_logger
from utils.db_manager import DatabaseManager
from cogs.punctuality_tracker import PunctualityTracker

# Set up logging
setup_logger()
logger = logging.getLogger("discord_bot")

# Initialize bot with intents
intents = discord.Intents.default()
intents.voice_states = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=Config.PREFIX, intents=intents)


@bot.event
async def on_ready():
    logger.info(f"Bot is ready! Logged in as {bot.user.name}")
    # Initialize database
    db = DatabaseManager()
    db.initialize()

    # Load cogs
    await bot.add_cog(PunctualityTracker(bot))
    logger.info("Punctuality tracker cog loaded")


async def main():
    async with bot:
        await bot.start(Config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
