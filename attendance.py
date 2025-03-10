# models/attendance.py
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Meeting:
    id: int = None
    meeting_date: str = None
    start_time: str = None
    end_time: str = None
    channel_id: int = None

    @classmethod
    def from_db_record(cls, record):
        if not record:
            return None
        return cls(
            id=record[0],
            meeting_date=record[1],
            start_time=record[2],
            end_time=record[3] if len(record) > 3 else None,
            channel_id=record[4] if len(record) > 4 else None,
        )


@dataclass
class AttendanceRecord:
    id: int = None
    meeting_id: int = None
    user_id: int = None
    user_name: str = None
    join_time: str = None
    leave_time: str = None
    late_minutes: int = 0
    fee_amount: float = 0.0

    @classmethod
    def from_db_record(cls, record):
        if not record:
            return None
        return cls(
            id=record[0],
            meeting_id=record[1],
            user_id=record[2],
            user_name=record[3],
            join_time=record[4],
            leave_time=record[5] if len(record) > 5 else None,
            late_minutes=record[6] if len(record) > 6 else 0,
            fee_amount=record[7] if len(record) > 7 else 0.0,
        )
