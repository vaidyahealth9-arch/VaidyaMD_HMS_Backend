"""
VaidyaMD HMS — CRM & Telecaller Business Logic Service
Handles Leads, CSV Ingestion, Progressive Dialing Queue, Call Logs, and Reporting.
"""

import csv
import io
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, date, time, timedelta
from sqlalchemy import select, func, and_, or_, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import User
from app.modules.crm.model import (
    Lead, CallLog, LeadStatusHistory, TelecallerSession,
    LeadStatus, LeadSource, CallDisposition
)
from app.modules.crm.schemas import (
    LeadCreate, LeadUpdate, CallLogCreate, CallDispositionUpdate,
    CRMAnalyticsResponse, DialerQueueItem, LeadResponse,
    HeartbeatPayload, TelecallerRosterItem, TelecallerKPIItem
)
from app.modules.crm.exceptions import (
    LeadNotFoundException, CallLogNotFoundException, InvalidFileFormatException,
    TelecallerSessionNotFoundException
)


class CRMService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------------
    # Leads Management
    # ------------------------------------------------------------------------

    async def list_leads(
        self,
        tenant_id: UUID,
        branch_id: Optional[UUID] = None,
        status: Optional[LeadStatus] = None,
        source: Optional[LeadSource] = None,
        city: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[int, List[Lead]]:
        query = select(Lead).where(Lead.tenant_id == tenant_id)

        if branch_id:
            query = query.where(or_(Lead.branch_id == branch_id, Lead.branch_id.is_(None)))
        if status:
            query = query.where(Lead.status == status)
        if source:
            query = query.where(Lead.source == source)
        if city:
            query = query.where(Lead.city.ilike(f"%{city}%"))
        if search:
            search_filter = f"%{search}%"
            query = query.where(
                or_(
                    Lead.name.ilike(search_filter),
                    Lead.phone.ilike(search_filter),
                    Lead.city.ilike(search_filter)
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # Execute paginated query
        query = query.order_by(desc(Lead.created_at)).offset(offset).limit(limit)
        result = await self.db.execute(query)
        leads = list(result.scalars().all())

        return total, leads

    async def get_lead_by_id(self, lead_id: UUID, tenant_id: UUID) -> Lead:
        stmt = select(Lead).where(and_(Lead.id == lead_id, Lead.tenant_id == tenant_id))
        result = await self.db.execute(stmt)
        lead = result.scalar_one_or_none()
        if not lead:
            raise LeadNotFoundException(f"Lead with id {lead_id} not found")
        return lead

    async def create_lead(
        self,
        data: LeadCreate,
        tenant_id: UUID,
        branch_id: Optional[UUID],
        creator_id: Optional[UUID] = None
    ) -> Lead:
        lead = Lead(
            tenant_id=tenant_id,
            branch_id=branch_id,
            name=data.name,
            phone=data.phone,
            alternate_phone=data.alternate_phone,
            email=data.email,
            city=data.city,
            state=data.state,
            source=data.source,
            source_campaign=data.source_campaign,
            priority=data.priority,
            assigned_to_id=data.assigned_to_id or creator_id,
            next_follow_up_date=data.next_follow_up_date,
            tags=data.tags,
            notes_summary=data.notes_summary,
            status=LeadStatus.NEW
        )
        self.db.add(lead)
        await self.db.flush()

        # Audit history entry
        history = LeadStatusHistory(
            lead_id=lead.id,
            old_status=None,
            new_status=LeadStatus.NEW.value,
            changed_by_id=creator_id,
            notes="Lead created in system"
        )
        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(lead)
        return lead

    async def update_lead(
        self,
        lead_id: UUID,
        data: LeadUpdate,
        tenant_id: UUID,
        user_id: Optional[UUID] = None
    ) -> Lead:
        lead = await self.get_lead_by_id(lead_id, tenant_id)
        old_status = lead.status.value

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(lead, field, value)

        # Record audit if status changed
        if data.status and data.status.value != old_status:
            history = LeadStatusHistory(
                lead_id=lead.id,
                old_status=old_status,
                new_status=data.status.value,
                changed_by_id=user_id,
                notes=f"Status updated to {data.status.value}"
            )
            self.db.add(history)

        await self.db.commit()
        await self.db.refresh(lead)
        return lead

    # ------------------------------------------------------------------------
    # CSV Import Engine
    # ------------------------------------------------------------------------

    async def import_leads_csv(
        self,
        file_content: bytes,
        tenant_id: UUID,
        branch_id: Optional[UUID],
        creator_id: Optional[UUID]
    ) -> dict[str, Any]:
        try:
            decoded = file_content.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(decoded))
        except Exception:
            raise InvalidFileFormatException("Failed to parse CSV file. Ensure valid UTF-8 encoding.")

        imported_count = 0
        skipped_count = 0
        errors = []

        # Query existing phones in tenant to prevent duplicate calls
        existing_phones_stmt = select(Lead.phone).where(Lead.tenant_id == tenant_id)
        existing_res = await self.db.execute(existing_phones_stmt)
        existing_phones = {p.strip().replace(" ", "") for p in existing_res.scalars().all() if p}
        seen_in_batch = set()

        for row_idx, row in enumerate(reader, start=1):
            if not row:
                continue
            normalized_row = {
                (k.strip().lower() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items() if k is not None
            }
            name = (
                normalized_row.get("name")
                or normalized_row.get("full name")
                or normalized_row.get("patient name")
                or normalized_row.get("lead name")
                or normalized_row.get("patient")
            )
            phone = (
                normalized_row.get("phone")
                or normalized_row.get("mobile")
                or normalized_row.get("contact")
                or normalized_row.get("phone number")
                or normalized_row.get("mobile number")
                or normalized_row.get("contact number")
            )

            if not name or not phone:
                skipped_count += 1
                errors.append(f"Row {row_idx}: Missing required name or phone")
                continue

            clean_phone = phone.strip().replace(" ", "")
            if clean_phone in existing_phones or clean_phone in seen_in_batch:
                skipped_count += 1
                errors.append(f"Row {row_idx}: Skipped duplicate phone {clean_phone}")
                continue
            seen_in_batch.add(clean_phone)

            city = (
                normalized_row.get("city")
                or normalized_row.get("location")
                or normalized_row.get("town")
                or normalized_row.get("place")
            )
            email = (
                normalized_row.get("email")
                or normalized_row.get("e-mail")
                or normalized_row.get("email address")
            )
            campaign = (
                normalized_row.get("campaign")
                or normalized_row.get("source campaign")
                or normalized_row.get("campaign name")
            )
            raw_val = (
                normalized_row.get("source")
                or normalized_row.get("channel")
                or normalized_row.get("lead source")
                or "excel_import"
            )
            source_raw = str(raw_val).lower().replace(" ", "_").replace("-", "_")

            source_enum = LeadSource.EXCEL_IMPORT
            for s in LeadSource:
                if s.value == source_raw:
                    source_enum = s
                    break

            lead = Lead(
                tenant_id=tenant_id,
                branch_id=branch_id,
                name=name,
                phone=phone,
                email=email if email else None,
                city=city if city else None,
                source=source_enum,
                source_campaign=campaign if campaign else None,
                assigned_to_id=creator_id,
                status=LeadStatus.NEW
            )
            self.db.add(lead)
            imported_count += 1

        await self.db.commit()
        return {
            "imported": imported_count,
            "skipped": skipped_count,
            "errors": errors[:10]  # Return top 10 errors if any
        }

    # ------------------------------------------------------------------------
    # Progressive Dialer Queue
    # ------------------------------------------------------------------------

    async def get_next_lead_in_queue(
        self,
        tenant_id: UUID,
        branch_id: Optional[UUID],
        user_id: Optional[UUID]
    ) -> Optional[DialerQueueItem]:
        """
        Retrieves the next priority lead for the telecaller.
        Priority:
        1. Follow-ups scheduled for today / overdue
        2. New leads awaiting first call
        3. Previously contacted leads requesting callback
        """
        now = datetime.utcnow()

        # Step 1: Check scheduled follow-ups
        follow_up_stmt = (
            select(Lead)
            .where(
                and_(
                    Lead.tenant_id == tenant_id,
                    Lead.status.in_([LeadStatus.FOLLOW_UP, LeadStatus.INTERESTED]),
                    Lead.next_follow_up_date <= now,
                    or_(Lead.assigned_to_id == user_id, Lead.assigned_to_id.is_(None))
                )
            )
            .order_by(Lead.next_follow_up_date.asc())
            .limit(1)
        )
        lead = (await self.db.execute(follow_up_stmt)).scalar_one_or_none()

        # Step 2: If no due follow-ups, pick next NEW lead
        if not lead:
            new_lead_stmt = (
                select(Lead)
                .where(
                    and_(
                        Lead.tenant_id == tenant_id,
                        Lead.status == LeadStatus.NEW,
                        or_(Lead.assigned_to_id == user_id, Lead.assigned_to_id.is_(None))
                    )
                )
                .order_by(Lead.priority.desc(), Lead.created_at.asc())
                .limit(1)
            )
            lead = (await self.db.execute(new_lead_stmt)).scalar_one_or_none()

        if not lead:
            return None

        # Fetch recent call history summary for this lead
        history_stmt = (
            select(CallLog)
            .where(CallLog.lead_id == lead.id)
            .order_by(desc(CallLog.created_at))
            .limit(1)
        )
        last_call = (await self.db.execute(history_stmt)).scalar_one_or_none()

        call_count_stmt = select(func.count(CallLog.id)).where(CallLog.lead_id == lead.id)
        call_count = (await self.db.execute(call_count_stmt)).scalar() or 0

        return DialerQueueItem(
            lead=LeadResponse.model_validate(lead),
            previous_call_count=call_count,
            last_disposition=last_call.disposition.value if (last_call and last_call.disposition) else None,
            last_notes=last_call.notes if last_call else None
        )

    # ------------------------------------------------------------------------
    # Call Logging & Disposition
    # ------------------------------------------------------------------------

    async def log_call_start(
        self,
        lead_id: UUID,
        phone_dialed: str,
        tenant_id: UUID,
        branch_id: Optional[UUID],
        telecaller_id: UUID
    ) -> CallLog:
        lead = await self.get_lead_by_id(lead_id, tenant_id)

        call_log = CallLog(
            tenant_id=tenant_id,
            branch_id=branch_id,
            lead_id=lead.id,
            telecaller_id=telecaller_id,
            phone_dialed=phone_dialed,
            call_started_at=datetime.utcnow(),
            transcript_status="pending"
        )
        self.db.add(call_log)
        lead.last_contacted_at = datetime.utcnow()
        if lead.status == LeadStatus.NEW:
            lead.status = LeadStatus.CONTACTED

        await self.db.commit()
        await self.db.refresh(call_log)
        return call_log

    async def update_call_disposition(
        self,
        call_id: UUID,
        data: CallDispositionUpdate,
        tenant_id: UUID,
        user_id: UUID
    ) -> CallLog:
        stmt = select(CallLog).where(and_(CallLog.id == call_id, CallLog.tenant_id == tenant_id))
        call_log = (await self.db.execute(stmt)).scalar_one_or_none()
        if not call_log:
            raise CallLogNotFoundException()

        call_log.disposition = data.disposition
        call_log.notes = data.notes
        call_log.follow_up_scheduled_at = data.follow_up_scheduled_at
        call_log.call_ended_at = datetime.utcnow()
        
        # Calculate duration if started
        if call_log.call_started_at:
            delta = call_log.call_ended_at - call_log.call_started_at
            call_log.duration_seconds = int(delta.total_seconds())

        # Update lead parent record
        lead = await self.get_lead_by_id(call_log.lead_id, tenant_id)
        if data.follow_up_scheduled_at:
            lead.next_follow_up_date = data.follow_up_scheduled_at
            lead.status = LeadStatus.FOLLOW_UP
        elif data.lead_status:
            lead.status = data.lead_status

        if data.disposition == CallDisposition.CONVERTED_APPOINTMENT:
            lead.is_converted = True
            lead.status = LeadStatus.CONVERTED

        await self.db.commit()
        await self.db.refresh(call_log)
        return call_log

    async def log_call_end(
        self,
        call_id: UUID,
        tenant_id: UUID,
        duration_seconds: int
    ) -> CallLog:
        stmt = select(CallLog).where(and_(CallLog.id == call_id, CallLog.tenant_id == tenant_id))
        call_log = (await self.db.execute(stmt)).scalar_one_or_none()
        if not call_log:
            raise CallLogNotFoundException()

        now = datetime.utcnow()
        call_log.call_ended_at = now
        if duration_seconds > 0:
            call_log.duration_seconds = duration_seconds
        elif call_log.call_started_at:
            call_log.duration_seconds = max(int((now - call_log.call_started_at).total_seconds()), 1)

        await self.db.commit()
        await self.db.refresh(call_log)
        return call_log

    async def list_call_logs(
        self,
        tenant_id: UUID,
        telecaller_id: Optional[UUID] = None,
        lead_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[CallLog]:
        stmt = (
            select(CallLog, Lead.name.label("lead_name"))
            .outerjoin(Lead, CallLog.lead_id == Lead.id)
            .where(CallLog.tenant_id == tenant_id)
        )
        if telecaller_id:
            stmt = stmt.where(CallLog.telecaller_id == telecaller_id)
        if lead_id:
            stmt = stmt.where(CallLog.lead_id == lead_id)
        stmt = stmt.order_by(desc(CallLog.call_started_at)).offset(offset).limit(limit)
        res = await self.db.execute(stmt)
        items = []
        for call_log, lead_name in res.all():
            setattr(call_log, "lead_name", lead_name)
            setattr(call_log, "recording_url", f"/api/crm/calls/{call_log.id}/recording" if call_log.recording_file_path else None)
            items.append(call_log)
        return items

    # ------------------------------------------------------------------------
    # Manager Dashboard KPIs
    # ------------------------------------------------------------------------

    async def get_analytics(self, tenant_id: UUID, branch_id: Optional[UUID] = None) -> CRMAnalyticsResponse:
        lead_query = select(Lead).where(Lead.tenant_id == tenant_id)
        if branch_id:
            lead_query = lead_query.where(or_(Lead.branch_id == branch_id, Lead.branch_id.is_(None)))

        leads = (await self.db.execute(lead_query)).scalars().all()
        now = datetime.utcnow()
        today_start = datetime.combine(date.today(), time.min)

        total_leads = len(leads)
        new_leads = sum(1 for l in leads if l.status == LeadStatus.NEW)
        conversions = sum(1 for l in leads if l.is_converted or l.status == LeadStatus.CONVERTED)

        # Status & source distributions
        status_counts = {}
        for l in leads:
            status_counts[l.status.value] = status_counts.get(l.status.value, 0) + 1

        source_counts = {}
        for l in leads:
            source_counts[l.source.value] = source_counts.get(l.source.value, 0) + 1

        # Follow-up counters
        pending_today = sum(
            1 for l in leads
            if l.next_follow_up_date and today_start <= l.next_follow_up_date <= datetime.combine(date.today(), time.max)
        )
        overdue = sum(
            1 for l in leads
            if l.next_follow_up_date and l.next_follow_up_date < today_start and l.status in [LeadStatus.FOLLOW_UP, LeadStatus.INTERESTED]
        )

        # Calls made today
        calls_today_stmt = (
            select(func.count(CallLog.id))
            .where(and_(CallLog.tenant_id == tenant_id, CallLog.call_started_at >= today_start))
        )
        calls_today = (await self.db.execute(calls_today_stmt)).scalar() or 0

        return CRMAnalyticsResponse(
            total_leads=total_leads,
            new_leads=new_leads,
            calls_made_today=calls_today,
            conversions_total=conversions,
            pending_follow_ups_today=pending_today,
            overdue_follow_ups=overdue,
            status_breakdown=status_counts,
            source_breakdown=source_counts
        )

    # ------------------------------------------------------------------------
    # Telecaller Fleet Heartbeat & Admin Roster
    # ------------------------------------------------------------------------

    async def record_heartbeat(
        self,
        user_id: UUID,
        tenant_id: UUID,
        branch_id: Optional[UUID],
        payload: HeartbeatPayload
    ) -> TelecallerSession:
        """
        Updates telecaller presence every 30-60 seconds from companion Android app.
        Enforces remote revocation lock.
        """
        stmt = select(TelecallerSession).where(TelecallerSession.user_id == user_id)
        session = (await self.db.execute(stmt)).scalar_one_or_none()

        now = datetime.utcnow()
        if not session:
            session = TelecallerSession(
                tenant_id=tenant_id,
                branch_id=branch_id,
                user_id=user_id,
                device_id=payload.device_id,
                device_model=payload.device_model,
                app_version=payload.app_version,
                sim_operator=payload.sim_operator,
                battery_level=payload.battery_level,
                is_online=True,
                is_revoked=False,
                current_state=payload.current_state,
                current_lead_id=payload.current_lead_id,
                last_heartbeat_at=now,
                paired_at=now
            )
            self.db.add(session)
        else:
            session.last_heartbeat_at = now
            if not session.is_revoked:
                session.is_online = True
                session.current_state = payload.current_state
            if payload.device_id:
                session.device_id = payload.device_id
            if payload.device_model:
                session.device_model = payload.device_model
            if payload.app_version:
                session.app_version = payload.app_version
            if payload.sim_operator:
                session.sim_operator = payload.sim_operator
            if payload.battery_level is not None:
                session.battery_level = payload.battery_level
            if payload.current_lead_id:
                session.current_lead_id = payload.current_lead_id

        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def revoke_device(self, user_id: UUID, tenant_id: UUID) -> TelecallerSession:
        """Admin Kill-Switch: De-authorizes the telecaller device."""
        stmt = select(TelecallerSession).where(and_(TelecallerSession.user_id == user_id, TelecallerSession.tenant_id == tenant_id))
        session = (await self.db.execute(stmt)).scalar_one_or_none()
        if not session:
            raise TelecallerSessionNotFoundException("Telecaller session not found")
        session.is_revoked = True
        session.is_online = False
        session.current_state = "revoked"
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get_telecaller_roster(
        self,
        tenant_id: UUID,
        branch_id: Optional[UUID] = None
    ) -> List[TelecallerRosterItem]:
        """
        Returns all registered telecallers with live online/offline status,
        current call states, and daily metrics.
        Optimized with single grouped aggregation query.
        """
        stmt = (
            select(TelecallerSession, User, Lead)
            .join(User, TelecallerSession.user_id == User.id)
            .outerjoin(Lead, TelecallerSession.current_lead_id == Lead.id)
            .where(TelecallerSession.tenant_id == tenant_id)
        )
        if branch_id:
            stmt = stmt.where(or_(TelecallerSession.branch_id == branch_id, TelecallerSession.branch_id.is_(None)))

        results = (await self.db.execute(stmt)).all()
        now = datetime.utcnow()
        today_start = datetime.combine(date.today(), time.min)

        # Batch aggregate all telecallers' stats for today in a single query
        summary_stmt = (
            select(
                CallLog.telecaller_id,
                func.count(CallLog.id).label("calls_today"),
                func.coalesce(func.sum(CallLog.duration_seconds), 0).label("talk_time_secs"),
                func.count(CallLog.id).filter(CallLog.disposition == CallDisposition.CONVERTED_APPOINTMENT).label("conversions_today")
            )
            .where(and_(CallLog.tenant_id == tenant_id, CallLog.call_started_at >= today_start))
            .group_by(CallLog.telecaller_id)
        )
        summary_rows = (await self.db.execute(summary_stmt)).all()
        stats_by_telecaller = {
            row.telecaller_id: {
                "calls": row.calls_today or 0,
                "talk_time": row.talk_time_secs or 0,
                "conversions": row.conversions_today or 0,
            }
            for row in summary_rows
        }

        roster_items: List[TelecallerRosterItem] = []

        for session, user, current_lead in results:
            # Device considered offline if no heartbeat in last 90 seconds or revoked
            is_active_online = session.is_online and not session.is_revoked and (now - session.last_heartbeat_at < timedelta(seconds=90))
            display_state = "revoked" if session.is_revoked else (session.current_state if is_active_online else "offline")

            caller_stats = stats_by_telecaller.get(user.id, {"calls": 0, "talk_time": 0, "conversions": 0})
            calls_today_count = caller_stats["calls"]
            talk_time_secs = caller_stats["talk_time"]
            conversions_count = caller_stats["conversions"]

            # Live call duration
            call_duration = 0
            if is_active_online and session.current_state == "on_call" and session.current_call_started_at:
                call_duration = int((now - session.current_call_started_at).total_seconds())

            roster_items.append(
                TelecallerRosterItem(
                    user_id=user.id,
                    user_name=user.full_name or user.email,
                    email=user.email,
                    device_id=session.device_id,
                    device_model=session.device_model,
                    app_version=session.app_version,
                    sim_operator=session.sim_operator,
                    battery_level=session.battery_level,
                    is_online=is_active_online,
                    is_revoked=session.is_revoked or False,
                    current_state=display_state,
                    current_lead_name=current_lead.name if current_lead else None,
                    current_lead_phone=current_lead.phone if current_lead else None,
                    call_duration_seconds=call_duration,
                    last_heartbeat_at=session.last_heartbeat_at,
                    calls_today=calls_today_count,
                    conversions_today=conversions_count,
                    total_talk_time_seconds=talk_time_secs
                )
            )

        return roster_items

    async def get_telecaller_kpis(
        self,
        tenant_id: UUID,
        branch_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> List[TelecallerKPIItem]:
        """
        Computes aggregate KPI metrics per telecaller across all calls within date range.
        Includes detailed outcomes: conversions, callbacks, not interested, dnd, wrong number, and skipped.
        """
        # Fetch only users with telecaller sessions or existing call logs
        t_ids = (await self.db.execute(select(TelecallerSession.user_id).where(TelecallerSession.tenant_id == tenant_id))).scalars().all()
        c_ids = (await self.db.execute(select(CallLog.telecaller_id).where(CallLog.tenant_id == tenant_id))).scalars().all()
        active_user_ids = list(set(t_ids + c_ids))
        if not active_user_ids:
            return []
        
        users_stmt = select(User).where(and_(User.tenant_id == tenant_id, User.id.in_(active_user_ids)))
        users = (await self.db.execute(users_stmt)).scalars().all()
        now = datetime.utcnow()
        today_start = datetime.combine(date.today(), time.min)

        kpis: List[TelecallerKPIItem] = []
        for user in users:
            # Build query with optional date filters
            call_conditions = [CallLog.telecaller_id == user.id, CallLog.tenant_id == tenant_id]
            if date_from:
                call_conditions.append(CallLog.created_at >= date_from)
            if date_to:
                call_conditions.append(CallLog.created_at <= date_to)

            call_metrics_stmt = select(
                func.count(CallLog.id),
                func.coalesce(func.sum(CallLog.duration_seconds), 0),
                func.coalesce(func.sum(case((CallLog.duration_seconds > 0, 1), else_=0)), 0),
                func.coalesce(func.sum(case((CallLog.disposition == CallDisposition.CONVERTED_APPOINTMENT, 1), else_=0)), 0),
                func.coalesce(func.sum(case((CallLog.disposition == CallDisposition.CALLBACK_REQUESTED, 1), else_=0)), 0),
                func.coalesce(func.sum(case((CallLog.disposition == CallDisposition.NOT_INTERESTED, 1), else_=0)), 0),
                func.coalesce(func.sum(case((CallLog.disposition == CallDisposition.DND, 1), else_=0)), 0),
                func.coalesce(func.sum(case((CallLog.disposition == CallDisposition.WRONG_NUMBER, 1), else_=0)), 0),
                func.coalesce(func.sum(case((
                    or_(
                        CallLog.disposition == CallDisposition.NOT_REACHABLE,
                        CallLog.duration_seconds == 0,
                        and_(CallLog.duration_seconds < 5, CallLog.disposition.is_(None))
                    ), 1), else_=0)), 0)
            ).where(and_(*call_conditions))

            row = (await self.db.execute(call_metrics_stmt)).one()
            total_calls = int(row[0] or 0)
            total_duration = int(row[1] or 0)
            answered_calls = int(row[2] or 0)
            conversions = int(row[3] or 0)
            callback_count = int(row[4] or 0)
            not_interested_count = int(row[5] or 0)
            dnd_invalid_count = int(row[6] or 0)
            wrong_number_count = int(row[7] or 0)
            skipped_count = int(row[8] or 0)

            # Overdue follow-ups assigned to this telecaller
            overdue_stmt = select(func.count(Lead.id)).where(
                and_(
                    Lead.assigned_to_id == user.id,
                    Lead.next_follow_up_date < today_start,
                    Lead.status.in_([LeadStatus.FOLLOW_UP, LeadStatus.INTERESTED])
                )
            )
            overdue_count = (await self.db.execute(overdue_stmt)).scalar() or 0

            avg_duration = int(total_duration / answered_calls) if answered_calls > 0 else 0
            conversion_pct = round((conversions / total_calls * 100), 1) if total_calls > 0 else 0.0

            kpis.append(
                TelecallerKPIItem(
                    user_id=user.id,
                    user_name=user.full_name or user.email,
                    email=user.email,
                    total_calls=total_calls,
                    answered_calls=answered_calls,
                    total_duration_seconds=total_duration,
                    avg_duration_seconds=avg_duration,
                    conversions=conversions,
                    conversion_rate_percentage=conversion_pct,
                    overdue_follow_ups=overdue_count,
                    callback_count=callback_count,
                    not_interested_count=not_interested_count,
                    dnd_invalid_count=dnd_invalid_count,
                    wrong_number_count=wrong_number_count,
                    skipped_count=skipped_count
                )
            )

        return sorted(kpis, key=lambda k: (k.conversions, k.total_calls), reverse=True)
