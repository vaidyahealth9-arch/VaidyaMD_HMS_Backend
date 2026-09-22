"""
VaidyaMD HMS — Database Engine & Session
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables and run safe additive schema migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE treatment_cycles ADD COLUMN IF NOT EXISTS medication_calendar JSONB DEFAULT '[]'::jsonb;"))
            await conn.execute(text("ALTER TABLE treatment_cycles ADD COLUMN IF NOT EXISTS et_discharge_summary JSONB DEFAULT '{}'::jsonb;"))
            await conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS marketing_person_name VARCHAR(255);"))
            await conn.execute(text("ALTER TABLE patients ADD COLUMN IF NOT EXISTS referring_doctor VARCHAR(255);"))
            await conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS branch_id UUID REFERENCES branches(id);"))
            await conn.execute(text("ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS branch_id UUID REFERENCES branches(id);"))
            # New: treatment cycle type lookup (auto-created by create_all but guard here)
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS treatment_cycle_types (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(150) NOT NULL UNIQUE,
                    display_order INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """))
            try:
                await conn.execute(text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'counsellor';"))
                await conn.execute(text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'COUNSELLOR';"))
            except Exception:
                pass
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS counseling_notes (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
                    tenant_id UUID NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
                    branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
                    counselor_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    source VARCHAR(255),
                    comments TEXT,
                    procedure VARCHAR(255),
                    egg_pick_up TEXT,
                    discussion TEXT,
                    laparoscopy_hysteroscopy TEXT,
                    egg_transfer TEXT,
                    remarks TEXT,
                    signature VARCHAR(255),
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                );
            """))
            try:
                await conn.execute(text("ALTER TABLE counseling_notes ADD COLUMN IF NOT EXISTS comments TEXT;"))
            except Exception:
                pass
        except Exception:
            pass

