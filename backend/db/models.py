from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.database import Base
import uuid


class Review(Base):
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo = Column(String, nullable=False)
    pr_number = Column(Integer, nullable=False)
    pr_title = Column(String)
    pr_url = Column(String)
    status = Column(String, default="pending")
    overall_risk_score = Column(Float)
    github_comment_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    agent_outputs = relationship("AgentOutput", back_populates="review")
    trace_events = relationship("TraceEvent", back_populates="review")


class AgentOutput(Base):
    __tablename__ = "agent_outputs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id = Column(UUID(as_uuid=True), ForeignKey("reviews.id"))
    agent_name = Column(String)
    output = Column(JSONB)
    tokens_used = Column(Integer)
    latency_ms = Column(Integer)
    eval_score = Column(Float)

    review = relationship("Review", back_populates="agent_outputs")


class TraceEvent(Base):
    __tablename__ = "trace_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id = Column(UUID(as_uuid=True), ForeignKey("reviews.id"))
    event_type = Column(String)
    agent_name = Column(String)
    payload = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    review = relationship("Review", back_populates="trace_events")
