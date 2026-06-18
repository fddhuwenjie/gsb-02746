from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.core.database import Base


class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    author = Column(String(200))
    content = Column(Text)
    source = Column(String(200))
    issue = Column(String(50))  # 期数
    year = Column(Integer)
    month = Column(Integer)
    category = Column(String(100))
    file_path = Column(String(500))
    url = Column(String(1000))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
