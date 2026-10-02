"""
Persistence for the Notification Service.

Every send attempt (per channel, per incident event) is logged so the
dashboard/audit trail can show "who was paged, on what channel, did it
succeed" -- this is the `Notifications` table from the platform's DB spec.
"""
import datetime

from sqlalchemy import Column, DateTime, Integer, String, Boolean, Text

from shared.db import Base


class NotificationLog(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, index=True, nullable=True)
    incident_uid = Column(String(32), index=True, nullable=True)
    service_name = Column(String(128), index=True)
    severity = Column(String(16))
    status = Column(String(32))
    channel = Column(String(16), index=True)
    sent = Column(Boolean, default=False)
    reason = Column(Text, nullable=True)
    title = Column(String(256), nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
