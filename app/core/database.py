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
    # 1. Run enum additions outside transaction block (Postgres requires autocommit for ALTER TYPE)
    try:
        async with engine.connect() as autocommit_conn:
            await autocommit_conn.execution_options(isolation_level="AUTOCOMMIT")
            for enum_val in ("counsellor", "COUNSELLOR"):
                try:
                    await autocommit_conn.execute(text(f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{enum_val}';"))
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Synchronize tables and columns within transaction, protected by savepoints
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS qualification VARCHAR(255);",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS reg_number VARCHAR(100);",
            "ALTER TABLE treatment_cycle_types ADD COLUMN IF NOT EXISTS category VARCHAR(100);",
            "ALTER TABLE branches ADD COLUMN IF NOT EXISTS gstin VARCHAR(50);",
            "ALTER TABLE branches ADD COLUMN IF NOT EXISTS receipt_header JSONB DEFAULT '{}'::jsonb;",
            "ALTER TABLE branches ADD COLUMN IF NOT EXISTS ip_whitelist JSONB DEFAULT '[]'::jsonb;",
            "ALTER TABLE treatment_cycles ADD COLUMN IF NOT EXISTS medication_calendar JSONB DEFAULT '[]'::jsonb;",
            "ALTER TABLE treatment_cycles ADD COLUMN IF NOT EXISTS et_discharge_summary JSONB DEFAULT '{}'::jsonb;",
            "ALTER TABLE protocol_templates ADD COLUMN IF NOT EXISTS timeline_events JSONB DEFAULT '[]'::jsonb;",
            "ALTER TABLE patients ADD COLUMN IF NOT EXISTS marketing_person_name VARCHAR(255);",
            "ALTER TABLE patients ADD COLUMN IF NOT EXISTS referring_doctor VARCHAR(255);",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS branch_id UUID REFERENCES branches(id);",
            "ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS branch_id UUID REFERENCES branches(id);",
            # Unified Billing schema extensions
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS source_module VARCHAR(100) DEFAULT 'opd';",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS source_reference_id UUID;",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS payment_transactions JSONB DEFAULT '[]'::jsonb;",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS round_off NUMERIC(12, 2) DEFAULT 0;",
            "ALTER TABLE ipd_admissions ADD COLUMN IF NOT EXISTS invoice_id UUID REFERENCES invoices(id);",
            "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS invoice_id UUID REFERENCES invoices(id);",
            "ALTER TABLE clinical_records ADD COLUMN IF NOT EXISTS invoice_id UUID REFERENCES invoices(id);",
            "ALTER TABLE counseling_notes ADD COLUMN IF NOT EXISTS comments TEXT;",
            "ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS pack_size INTEGER DEFAULT 1;",
            "ALTER TABLE crm_telecaller_sessions ADD COLUMN IF NOT EXISTS device_id VARCHAR(100);",
            "ALTER TABLE crm_telecaller_sessions ADD COLUMN IF NOT EXISTS is_revoked BOOLEAN DEFAULT FALSE;",
            "UPDATE cosgyn_treatments SET price = 8000.00 WHERE (LOWER(name) LIKE '%tesla%' AND LOWER(name) NOT LIKE '%jet%' AND (LOWER(name) LIKE '%single%' OR tesla_chair_sessions = 1)) AND price < 8000.00;",
            "UPDATE hospitals SET active_plugins = active_plugins || '[\"referrals\"]'::jsonb WHERE NOT (active_plugins @> '[\"referrals\"]'::jsonb);",
        ]

        for stmt in migrations:
            try:
                async with conn.begin_nested():
                    await conn.execute(text(stmt))
            except Exception:
                pass

        try:
            async with conn.begin_nested():
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS treatment_cycle_types (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name VARCHAR(150) NOT NULL UNIQUE,
                        display_order INTEGER DEFAULT 0,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """))
        except Exception:
            pass

        try:
            async with conn.begin_nested():
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
        except Exception:
            pass

        try:
            async with conn.begin_nested():
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS referral_commission_configs (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        tenant_id UUID NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE UNIQUE,
                        opd_pct DOUBLE PRECISION DEFAULT 10.0,
                        pharmacy_pct DOUBLE PRECISION DEFAULT 5.0,
                        iui_pct DOUBLE PRECISION DEFAULT 10.0,
                        embryology_pct DOUBLE PRECISION DEFAULT 15.0,
                        lims_pct DOUBLE PRECISION DEFAULT 10.0,
                        ipd_pct DOUBLE PRECISION DEFAULT 10.0,
                        other_pct DOUBLE PRECISION DEFAULT 5.0,
                        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                    );
                """))
        except Exception:
            pass

        try:
            async with conn.begin_nested():
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS referring_doctors (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        tenant_id UUID NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        clinic_name VARCHAR(255),
                        specialty VARCHAR(100),
                        phone VARCHAR(50),
                        email VARCHAR(255),
                        address TEXT,
                        bank_name VARCHAR(150),
                        account_number VARCHAR(100),
                        ifsc_code VARCHAR(50),
                        upi_id VARCHAR(100),
                        pan_number VARCHAR(50),
                        custom_commission_pct DOUBLE PRECISION,
                        notes TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                    );
                """))
        except Exception:
            pass

        try:
            async with conn.begin_nested():
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS referral_settlements (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        settlement_number VARCHAR(50) UNIQUE NOT NULL,
                        tenant_id UUID NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
                        doctor_name VARCHAR(255) NOT NULL,
                        doctor_id UUID REFERENCES referring_doctors(id) ON DELETE SET NULL,
                        amount_paid DOUBLE PRECISION NOT NULL,
                        payment_method VARCHAR(50) DEFAULT 'neft',
                        reference_number VARCHAR(100),
                        settlement_date DATE DEFAULT CURRENT_DATE,
                        notes TEXT,
                        invoice_ids JSONB DEFAULT '[]'::jsonb NOT NULL,
                        created_by UUID REFERENCES users(id) ON DELETE SET NULL,
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                    );
                """))
        except Exception:
            pass


