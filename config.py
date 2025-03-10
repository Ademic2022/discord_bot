from decouple import config


class Config:
    TOKEN = config("DISCORD_TOKEN")
    PREFIX = config("COMMAND_PREFIX", "!")
    MEETING_CHANNEL_ID = int(config("MEETING_CHANNEL_ID"))
    ANNOUNCEMENT_CHANNEL_ID = int(config("ANNOUNCEMENT_CHANNEL_ID"))
    REMINDER_MINUTES = int(config("REMINDER_MINUTES", "15"))
    GRACE_PERIOD_MINUTES = int(config("GRACE_PERIOD_MINUTES", "1"))
    FEE_PER_MINUTE = float(
        config("FEE_PER_MINUTE", "200")
    )  # Fee amount per minute late
    DATABASE_PATH = config("DATABASE_PATH", "attendance.db")
    LOG_PATH = config("LOG_PATH", "logs")


