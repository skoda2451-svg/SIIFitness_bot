from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from models import Base

# Для asyncpg нужен формат postgresql+asyncpg://...
if DATABASE_URL.startswith("postgresql://"):
    async_db_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    async_db_url = DATABASE_URL

engine = create_async_engine(async_db_url, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)