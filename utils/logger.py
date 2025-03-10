# utils/logger.py
import logging
import os
from datetime import datetime
from config import Config


def setup_logger():
    if not os.path.exists(Config.LOG_PATH):
        os.makedirs(Config.LOG_PATH)

    logger = logging.getLogger("discord_bot")
    logger.setLevel(logging.INFO)

    # Create file handler
    log_file = os.path.join(
        Config.LOG_PATH, f'bot_{datetime.now().strftime("%Y-%m-%d")}.log'
    )
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
