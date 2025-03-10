import sqlite3
import logging
from config import Config


class DatabaseManager:
    def __init__(self, db_path=Config.DATABASE_PATH):
        self.db_path = db_path
        self.logger = logging.getLogger("discord_bot")

    def initialize(self):
        """Initialize the database with necessary tables"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create meetings table
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                channel_id INTEGER NOT NULL,
                description TEXT
            )
            """
            )

            # Create punctuality table - simplified to only track lateness
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS punctuality (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                join_time TEXT NOT NULL,
                late_minutes INTEGER DEFAULT 0,
                fee_amount REAL DEFAULT 0,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id)
            )
            """
            )

            conn.commit()
            self.logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            self.logger.error(f"Database initialization error: {e}")
        finally:
            if conn:
                conn.close()

    def create_meeting(self, meeting_date, start_time, channel_id, description=None):
        """Create a new meeting record"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
            INSERT INTO meetings (meeting_date, start_time, channel_id, description)
            VALUES (?, ?, ?, ?)
            """,
                (meeting_date, start_time, channel_id, description),
            )

            meeting_id = cursor.lastrowid
            conn.commit()
            self.logger.info(f"Created meeting record with ID: {meeting_id}")
            return meeting_id
        except sqlite3.Error as e:
            self.logger.error(f"Error creating meeting: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def record_punctuality(
        self, meeting_id, user_id, user_name, join_time, late_minutes=0, fee_amount=0
    ):
        """Record a user's punctuality for a meeting"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if this user already has a record for this meeting
            cursor.execute(
                """
            SELECT id FROM punctuality 
            WHERE meeting_id = ? AND user_id = ?
            """,
                (meeting_id, user_id),
            )

            existing = cursor.fetchone()

            if existing:
                self.logger.info(
                    f"User {user_name} already has a punctuality record for meeting {meeting_id}"
                )
                return existing[0]

            cursor.execute(
                """
            INSERT INTO punctuality (meeting_id, user_id, user_name, join_time, late_minutes, fee_amount)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
                (meeting_id, user_id, user_name, join_time, late_minutes, fee_amount),
            )

            conn.commit()
            self.logger.info(
                f"Recorded punctuality for user {user_name} in meeting {meeting_id}"
            )
            return cursor.lastrowid
        except sqlite3.Error as e:
            self.logger.error(f"Error recording punctuality: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_active_meeting(self, channel_id, meeting_date=None):
        """Get the active meeting for a channel on a specific date"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if meeting_date:
                cursor.execute(
                    """
                SELECT id, meeting_date, start_time, description FROM meetings
                WHERE channel_id = ? AND meeting_date = ?
                ORDER BY start_time DESC LIMIT 1
                """,
                    (channel_id, meeting_date),
                )
            else:
                # Get today's date
                from datetime import datetime

                today = datetime.now().strftime("%Y-%m-%d")

                cursor.execute(
                    """
                SELECT id, meeting_date, start_time, description FROM meetings
                WHERE channel_id = ? AND meeting_date = ?
                ORDER BY start_time DESC LIMIT 1
                """,
                    (channel_id, today),
                )

            meeting = cursor.fetchone()
            return meeting
        except sqlite3.Error as e:
            self.logger.error(f"Error getting active meeting: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_punctuality_report(self, meeting_id):
        """Get punctuality report for a meeting"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
            SELECT user_name, join_time, late_minutes, fee_amount
            FROM punctuality WHERE meeting_id = ?
            ORDER BY late_minutes DESC
            """,
                (meeting_id,),
            )

            punctuality_records = cursor.fetchall()
            return punctuality_records
        except sqlite3.Error as e:
            self.logger.error(f"Error getting punctuality report: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_all_meetings(self, limit=10):
        """Get list of meetings"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
            SELECT id, meeting_date, start_time, description
            FROM meetings
            ORDER BY meeting_date DESC, start_time DESC
            LIMIT ?
            """,
                (limit,),
            )

            meetings = cursor.fetchall()
            return meetings
        except sqlite3.Error as e:
            self.logger.error(f"Error getting meetings list: {e}")
            return []
        finally:
            if conn:
                conn.close()
