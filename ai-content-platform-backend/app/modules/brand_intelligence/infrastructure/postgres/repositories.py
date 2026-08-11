"""Postgres repositories for Brand Intelligence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.postgres.models.brand_intelligence import (
    BrandBrowserSessionRow,
    BrandImportJobRow,
    BrandImportRow,
    BrandMemoryReviewRow,
    BrandMemoryRow,
    BrandMemoryVersionRow,
    BrandPersonaRow,
    BrandProfileRow,
    BrandVectorChunkRow,
    CanonicalBrandObjectRow,
    LogoAssetSetRow,
    NeverSayPolicyRow,
)
from app.modules.brand_intelligence.domain.models import (
    BrandImport,
    BrandImportJob,
    BrandMemory,
    BrandMemoryReview,
    BrandMemoryVersion,
    BrandPersona,
    BrandProfile,
    BrowserSessionRecord,
    CanonicalBrandObject,
    CboObjectType,
    CboSourceType,
    ImportStatus,
    LogoAssetSet,
    MemoryLifecycle,
    NeverSayPolicy,
    PersonaKind,
    ProfileKind,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PgBrandProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, row: BrandProfileRow) -> BrandProfile:
        return BrandProfile(
            id=row.id,
            organization_id=row.organization_id,
            kind=ProfileKind(row.kind),
            name=row.name,
            is_default=row.is_default,
            active_memory_id=row.active_memory_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list_for_org(self, org_id: uuid.UUID) -> list[BrandProfile]:
        result = await self._session.execute(
            select(BrandProfileRow).where(BrandProfileRow.organization_id == org_id)
        )
        return [self._to_domain(r) for r in result.scalars().all()]

    async def get(self, org_id: uuid.UUID, profile_id: uuid.UUID) -> BrandProfile | None:
        result = await self._session.execute(
            select(BrandProfileRow).where(
                BrandProfileRow.organization_id == org_id,
                BrandProfileRow.id == profile_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_default(self, org_id: uuid.UUID) -> BrandProfile | None:
        result = await self._session.execute(
            select(BrandProfileRow).where(
                BrandProfileRow.organization_id == org_id,
                BrandProfileRow.is_default.is_(True),
            )
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def create(self, profile: BrandProfile) -> BrandProfile:
        row = BrandProfileRow(
            id=profile.id,
            organization_id=profile.organization_id,
            kind=profile.kind.value,
            name=profile.name,
            is_default=profile.is_default,
            active_memory_id=profile.active_memory_id,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_domain(row)

    async def update(self, profile: BrandProfile) -> BrandProfile:
        result = await self._session.execute(
            select(BrandProfileRow).where(
                BrandProfileRow.organization_id == profile.organization_id,
                BrandProfileRow.id == profile.id,
            )
        )
        row = result.scalar_one()
        row.kind = profile.kind.value
        row.name = profile.name
        row.is_default = profile.is_default
        row.active_memory_id = profile.active_memory_id
        row.updated_at = _now()
        await self._session.flush()
        return self._to_domain(row)

    async def ensure_default_corporate(self, org_id: uuid.UUID) -> BrandProfile:
        existing = await self.get_default(org_id)
        if existing:
            return existing
        return await self.create(
            BrandProfile(
                id=uuid.uuid4(),
                organization_id=org_id,
                kind=ProfileKind.CORPORATE,
                name="Corporate",
                is_default=True,
            )
        )


class PgBrandPersonaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_profile(self, org_id: uuid.UUID, profile_id: uuid.UUID) -> list[BrandPersona]:
        result = await self._session.execute(
            select(BrandPersonaRow).where(
                BrandPersonaRow.organization_id == org_id,
                BrandPersonaRow.brand_profile_id == profile_id,
            )
        )
        return [
            BrandPersona(
                id=r.id,
                organization_id=r.organization_id,
                brand_profile_id=r.brand_profile_id,
                kind=PersonaKind(r.kind),
                name=r.name,
                is_default=r.is_default,
                voice_notes=r.voice_notes or "",
                metadata_json=dict(r.metadata_json or {}),
            )
            for r in result.scalars().all()
        ]

    async def upsert(self, persona: BrandPersona) -> BrandPersona:
        result = await self._session.execute(
            select(BrandPersonaRow).where(
                BrandPersonaRow.organization_id == persona.organization_id,
                BrandPersonaRow.id == persona.id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = BrandPersonaRow(
                id=persona.id,
                organization_id=persona.organization_id,
                brand_profile_id=persona.brand_profile_id,
                kind=persona.kind.value,
                name=persona.name,
                is_default=persona.is_default,
                voice_notes=persona.voice_notes,
                metadata_json=persona.metadata_json,
            )
            self._session.add(row)
        else:
            row.kind = persona.kind.value
            row.name = persona.name
            row.is_default = persona.is_default
            row.voice_notes = persona.voice_notes
            row.metadata_json = persona.metadata_json
            row.updated_at = _now()
        await self._session.flush()
        return persona


class PgNeverSayRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, org_id: uuid.UUID, profile_id: uuid.UUID) -> NeverSayPolicy | None:
        result = await self._session.execute(
            select(NeverSayPolicyRow).where(
                NeverSayPolicyRow.organization_id == org_id,
                NeverSayPolicyRow.brand_profile_id == profile_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return NeverSayPolicy(
            id=row.id,
            organization_id=row.organization_id,
            brand_profile_id=row.brand_profile_id,
            forbidden=list(row.forbidden or []),
            discouraged=list(row.discouraged or []),
            legal_restrictions=list(row.legal_restrictions or []),
            compliance_restrictions=list(row.compliance_restrictions or []),
            avoid_vocabulary=list(row.avoid_vocabulary or []),
            never_use=list(row.never_use or []),
            preferred_alternatives=dict(row.preferred_alternatives or {}),
        )

    async def upsert(self, policy: NeverSayPolicy) -> NeverSayPolicy:
        result = await self._session.execute(
            select(NeverSayPolicyRow).where(
                NeverSayPolicyRow.organization_id == policy.organization_id,
                NeverSayPolicyRow.brand_profile_id == policy.brand_profile_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = NeverSayPolicyRow(
                id=policy.id,
                organization_id=policy.organization_id,
                brand_profile_id=policy.brand_profile_id,
            )
            self._session.add(row)
        row.forbidden = policy.forbidden
        row.discouraged = policy.discouraged
        row.legal_restrictions = policy.legal_restrictions
        row.compliance_restrictions = policy.compliance_restrictions
        row.avoid_vocabulary = policy.avoid_vocabulary
        row.never_use = policy.never_use
        row.preferred_alternatives = policy.preferred_alternatives
        row.updated_at = _now()
        await self._session.flush()
        return policy


class PgBrandImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, row: BrandImportRow) -> BrandImport:
        return BrandImport(
            id=row.id,
            organization_id=row.organization_id,
            brand_profile_id=row.brand_profile_id,
            status=ImportStatus(row.status),
            source_mix_json=dict(row.source_mix_json or {}),
            watermark_json=dict(row.watermark_json or {}),
            last_sync_at=row.last_sync_at,
            error_json=row.error_json,
        )

    async def create(self, row: BrandImport) -> BrandImport:
        orm = BrandImportRow(
            id=row.id,
            organization_id=row.organization_id,
            brand_profile_id=row.brand_profile_id,
            status=row.status.value,
            source_mix_json=row.source_mix_json,
            watermark_json=row.watermark_json,
            last_sync_at=row.last_sync_at,
            error_json=row.error_json,
        )
        self._session.add(orm)
        await self._session.flush()
        return self._to_domain(orm)

    async def get(self, org_id: uuid.UUID, import_id: uuid.UUID) -> BrandImport | None:
        result = await self._session.execute(
            select(BrandImportRow).where(
                BrandImportRow.organization_id == org_id,
                BrandImportRow.id == import_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def update(self, row: BrandImport) -> BrandImport:
        result = await self._session.execute(
            select(BrandImportRow).where(
                BrandImportRow.organization_id == row.organization_id,
                BrandImportRow.id == row.id,
            )
        )
        orm = result.scalar_one()
        orm.status = row.status.value
        orm.source_mix_json = row.source_mix_json
        orm.watermark_json = row.watermark_json
        orm.last_sync_at = row.last_sync_at
        orm.error_json = row.error_json
        orm.updated_at = _now()
        await self._session.flush()
        return self._to_domain(orm)

    async def delete(self, org_id: uuid.UUID, import_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(BrandImportRow).where(
                BrandImportRow.organization_id == org_id,
                BrandImportRow.id == import_id,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            await self._session.delete(row)
            await self._session.flush()


class PgBrandImportJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, row: BrandImportJobRow) -> BrandImportJob:
        return BrandImportJob(
            id=row.id,
            organization_id=row.organization_id,
            import_id=row.import_id,
            job_id=row.job_id,
            stage=row.stage,
            progress_pct=row.progress_pct,
            message=row.message or "",
            error_json=row.error_json,
            eta_seconds=row.eta_seconds,
        )

    async def create(self, row: BrandImportJob) -> BrandImportJob:
        orm = BrandImportJobRow(
            id=row.id,
            organization_id=row.organization_id,
            import_id=row.import_id,
            job_id=row.job_id,
            stage=row.stage,
            progress_pct=row.progress_pct,
            message=row.message,
            error_json=row.error_json,
            eta_seconds=row.eta_seconds,
        )
        self._session.add(orm)
        await self._session.flush()
        return self._to_domain(orm)

    async def get(self, org_id: uuid.UUID, job_row_id: uuid.UUID) -> BrandImportJob | None:
        result = await self._session.execute(
            select(BrandImportJobRow).where(
                BrandImportJobRow.organization_id == org_id,
                BrandImportJobRow.id == job_row_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get_by_job_id(self, org_id: uuid.UUID, job_id: uuid.UUID) -> BrandImportJob | None:
        result = await self._session.execute(
            select(BrandImportJobRow).where(
                BrandImportJobRow.organization_id == org_id,
                BrandImportJobRow.job_id == job_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def update(self, row: BrandImportJob) -> BrandImportJob:
        result = await self._session.execute(
            select(BrandImportJobRow).where(
                BrandImportJobRow.organization_id == row.organization_id,
                BrandImportJobRow.id == row.id,
            )
        )
        orm = result.scalar_one()
        orm.job_id = row.job_id
        orm.stage = row.stage
        orm.progress_pct = row.progress_pct
        orm.message = row.message
        orm.error_json = row.error_json
        orm.eta_seconds = row.eta_seconds
        orm.updated_at = _now()
        await self._session.flush()
        return self._to_domain(orm)


class PgCanonicalObjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_upsert(self, objects: list[CanonicalBrandObject]) -> int:
        for obj in objects:
            self._session.add(
                CanonicalBrandObjectRow(
                    id=obj.id,
                    organization_id=obj.organization_id,
                    brand_profile_id=obj.brand_profile_id,
                    import_id=obj.import_id,
                    object_type=obj.object_type.value,
                    source_type=obj.source_type.value,
                    external_id=obj.external_id,
                    canonical_url=obj.canonical_url,
                    fingerprint=obj.fingerprint,
                    title=obj.title,
                    body_text=obj.body_text,
                    html_sanitized=obj.html_sanitized,
                    authored_at=obj.authored_at,
                    language=obj.language,
                    media_refs=obj.media_refs,
                    engagement=obj.engagement,
                    metadata_json=obj.metadata_json,
                )
            )
        await self._session.flush()
        return len(objects)

    def _row_to_domain(self, r: CanonicalBrandObjectRow) -> CanonicalBrandObject:
        return CanonicalBrandObject(
            id=r.id,
            organization_id=r.organization_id,
            brand_profile_id=r.brand_profile_id,
            import_id=r.import_id,
            object_type=CboObjectType(r.object_type),
            source_type=CboSourceType(r.source_type),
            external_id=r.external_id,
            canonical_url=r.canonical_url,
            fingerprint=r.fingerprint,
            title=r.title,
            body_text=r.body_text,
            html_sanitized=r.html_sanitized,
            authored_at=r.authored_at,
            language=r.language,
            media_refs=list(r.media_refs or []),
            engagement=dict(r.engagement or {}),
            metadata_json=dict(r.metadata_json or {}),
        )

    async def list_for_import(self, org_id: uuid.UUID, import_id: uuid.UUID) -> list[CanonicalBrandObject]:
        result = await self._session.execute(
            select(CanonicalBrandObjectRow).where(
                CanonicalBrandObjectRow.organization_id == org_id,
                CanonicalBrandObjectRow.import_id == import_id,
            )
        )
        return [self._row_to_domain(r) for r in result.scalars().all()]

    async def list_for_profile(
        self, org_id: uuid.UUID, profile_id: uuid.UUID, *, limit: int = 50
    ) -> list[CanonicalBrandObject]:
        result = await self._session.execute(
            select(CanonicalBrandObjectRow)
            .where(
                CanonicalBrandObjectRow.organization_id == org_id,
                CanonicalBrandObjectRow.brand_profile_id == profile_id,
            )
            .order_by(CanonicalBrandObjectRow.created_at.desc())
            .limit(limit)
        )
        return [self._row_to_domain(r) for r in result.scalars().all()]


class PgBrandMemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, row: BrandMemoryRow) -> BrandMemory:
        return BrandMemory(
            id=row.id,
            organization_id=row.organization_id,
            brand_profile_id=row.brand_profile_id,
            version_no=row.version_no,
            lifecycle=MemoryLifecycle(row.lifecycle),
            confidence=row.confidence,
            brand_dna_json=dict(row.brand_dna_json or {}),
            writing_dna_json=dict(row.writing_dna_json or {}),
            visual_dna_json=dict(row.visual_dna_json or {}),
            engagement_json=dict(row.engagement_json or {}),
            completeness_json=dict(row.completeness_json or {}),
            health_json=dict(row.health_json or {}),
            recommendations_json=list(row.recommendations_json or []),
        )

    async def get_active(self, org_id: uuid.UUID, profile_id: uuid.UUID) -> BrandMemory | None:
        result = await self._session.execute(
            select(BrandMemoryRow).where(
                BrandMemoryRow.organization_id == org_id,
                BrandMemoryRow.brand_profile_id == profile_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def get(self, org_id: uuid.UUID, memory_id: uuid.UUID) -> BrandMemory | None:
        result = await self._session.execute(
            select(BrandMemoryRow).where(
                BrandMemoryRow.organization_id == org_id,
                BrandMemoryRow.id == memory_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def save(self, memory: BrandMemory) -> BrandMemory:
        result = await self._session.execute(
            select(BrandMemoryRow).where(
                BrandMemoryRow.organization_id == memory.organization_id,
                BrandMemoryRow.brand_profile_id == memory.brand_profile_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = BrandMemoryRow(
                id=memory.id,
                organization_id=memory.organization_id,
                brand_profile_id=memory.brand_profile_id,
            )
            self._session.add(row)
        else:
            memory = BrandMemory(
                id=row.id,
                organization_id=memory.organization_id,
                brand_profile_id=memory.brand_profile_id,
                version_no=memory.version_no,
                lifecycle=memory.lifecycle,
                confidence=memory.confidence,
                brand_dna_json=memory.brand_dna_json,
                writing_dna_json=memory.writing_dna_json,
                visual_dna_json=memory.visual_dna_json,
                engagement_json=memory.engagement_json,
                completeness_json=memory.completeness_json,
                health_json=memory.health_json,
                recommendations_json=memory.recommendations_json,
            )
        row.version_no = memory.version_no
        row.lifecycle = memory.lifecycle.value
        row.confidence = memory.confidence
        row.brand_dna_json = memory.brand_dna_json
        row.writing_dna_json = memory.writing_dna_json
        row.visual_dna_json = memory.visual_dna_json
        row.engagement_json = memory.engagement_json
        row.completeness_json = memory.completeness_json
        row.health_json = memory.health_json
        row.recommendations_json = memory.recommendations_json
        row.updated_at = _now()
        await self._session.flush()
        return self._to_domain(row)

    async def list_versions(self, org_id: uuid.UUID, memory_id: uuid.UUID) -> list[BrandMemoryVersion]:
        result = await self._session.execute(
            select(BrandMemoryVersionRow)
            .where(
                BrandMemoryVersionRow.organization_id == org_id,
                BrandMemoryVersionRow.memory_id == memory_id,
            )
            .order_by(BrandMemoryVersionRow.version_no.desc())
        )
        return [
            BrandMemoryVersion(
                id=r.id,
                organization_id=r.organization_id,
                memory_id=r.memory_id,
                version_no=r.version_no,
                snapshot_json=dict(r.snapshot_json or {}),
                created_by=r.created_by,
            )
            for r in result.scalars().all()
        ]

    async def save_version(self, version: BrandMemoryVersion) -> BrandMemoryVersion:
        row = BrandMemoryVersionRow(
            id=version.id,
            organization_id=version.organization_id,
            memory_id=version.memory_id,
            version_no=version.version_no,
            snapshot_json=version.snapshot_json,
            created_by=version.created_by,
        )
        self._session.add(row)
        await self._session.flush()
        return version

    async def get_version(
        self, org_id: uuid.UUID, memory_id: uuid.UUID, version_no: int
    ) -> BrandMemoryVersion | None:
        result = await self._session.execute(
            select(BrandMemoryVersionRow).where(
                BrandMemoryVersionRow.organization_id == org_id,
                BrandMemoryVersionRow.memory_id == memory_id,
                BrandMemoryVersionRow.version_no == version_no,
            )
        )
        r = result.scalar_one_or_none()
        if not r:
            return None
        return BrandMemoryVersion(
            id=r.id,
            organization_id=r.organization_id,
            memory_id=r.memory_id,
            version_no=r.version_no,
            snapshot_json=dict(r.snapshot_json or {}),
            created_by=r.created_by,
        )


class PgBrandReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_open(self, org_id: uuid.UUID, memory_id: uuid.UUID) -> BrandMemoryReview | None:
        result = await self._session.execute(
            select(BrandMemoryReviewRow).where(
                BrandMemoryReviewRow.organization_id == org_id,
                BrandMemoryReviewRow.memory_id == memory_id,
                BrandMemoryReviewRow.status == "open",
            )
        )
        r = result.scalar_one_or_none()
        if not r:
            return None
        return BrandMemoryReview(
            id=r.id,
            organization_id=r.organization_id,
            memory_id=r.memory_id,
            status=r.status,
            detections_json=dict(r.detections_json or {}),
            edits_json=dict(r.edits_json or {}),
        )

    async def save(self, review: BrandMemoryReview) -> BrandMemoryReview:
        result = await self._session.execute(
            select(BrandMemoryReviewRow).where(
                BrandMemoryReviewRow.organization_id == review.organization_id,
                BrandMemoryReviewRow.id == review.id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = BrandMemoryReviewRow(
                id=review.id,
                organization_id=review.organization_id,
                memory_id=review.memory_id,
            )
            self._session.add(row)
        row.status = review.status
        row.detections_json = review.detections_json
        row.edits_json = review.edits_json
        row.updated_at = _now()
        await self._session.flush()
        return review


class PgLogoAssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, org_id: uuid.UUID, profile_id: uuid.UUID) -> LogoAssetSet | None:
        result = await self._session.execute(
            select(LogoAssetSetRow).where(
                LogoAssetSetRow.organization_id == org_id,
                LogoAssetSetRow.brand_profile_id == profile_id,
            )
        )
        r = result.scalar_one_or_none()
        if not r:
            return None
        return LogoAssetSet(
            id=r.id,
            organization_id=r.organization_id,
            brand_profile_id=r.brand_profile_id,
            variants_json={str(k): str(v) for k, v in dict(r.variants_json or {}).items()},
            primary_key=r.primary_key,
        )

    async def upsert(self, logo_set: LogoAssetSet) -> LogoAssetSet:
        result = await self._session.execute(
            select(LogoAssetSetRow).where(
                LogoAssetSetRow.organization_id == logo_set.organization_id,
                LogoAssetSetRow.brand_profile_id == logo_set.brand_profile_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = LogoAssetSetRow(
                id=logo_set.id,
                organization_id=logo_set.organization_id,
                brand_profile_id=logo_set.brand_profile_id,
            )
            self._session.add(row)
        row.variants_json = logo_set.variants_json
        row.primary_key = logo_set.primary_key
        row.updated_at = _now()
        await self._session.flush()
        return logo_set


class PgBrowserSessionStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, org_id: uuid.UUID, provider: str) -> BrowserSessionRecord | None:
        result = await self._session.execute(
            select(BrandBrowserSessionRow).where(
                BrandBrowserSessionRow.organization_id == org_id,
                BrandBrowserSessionRow.provider == provider,
                BrandBrowserSessionRow.revoked_at.is_(None),
            )
        )
        r = result.scalar_one_or_none()
        if not r:
            return None
        return BrowserSessionRecord(
            id=r.id,
            organization_id=r.organization_id,
            provider=r.provider,
            ciphertext=r.ciphertext,
            expires_at=r.expires_at,
            revoked_at=r.revoked_at,
        )

    async def save(self, record: BrowserSessionRecord) -> BrowserSessionRecord:
        result = await self._session.execute(
            select(BrandBrowserSessionRow).where(
                BrandBrowserSessionRow.organization_id == record.organization_id,
                BrandBrowserSessionRow.provider == record.provider,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = BrandBrowserSessionRow(
                id=record.id,
                organization_id=record.organization_id,
                provider=record.provider,
                ciphertext=record.ciphertext,
            )
            self._session.add(row)
        row.ciphertext = record.ciphertext
        row.expires_at = record.expires_at
        row.revoked_at = None
        row.updated_at = _now()
        await self._session.flush()
        return record

    async def revoke(self, org_id: uuid.UUID, provider: str) -> None:
        result = await self._session.execute(
            select(BrandBrowserSessionRow).where(
                BrandBrowserSessionRow.organization_id == org_id,
                BrandBrowserSessionRow.provider == provider,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.revoked_at = _now()
            row.updated_at = _now()
            await self._session.flush()


class PgBrandVectorChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_for_memory(
        self,
        *,
        org_id: uuid.UUID,
        profile_id: uuid.UUID,
        memory_id: uuid.UUID,
        version_no: int,
        chunks: list[dict],
    ) -> int:
        existing = await self._session.execute(
            select(BrandVectorChunkRow).where(
                BrandVectorChunkRow.organization_id == org_id,
                BrandVectorChunkRow.memory_id == memory_id,
            )
        )
        for row in existing.scalars().all():
            await self._session.delete(row)
        for chunk in chunks:
            self._session.add(
                BrandVectorChunkRow(
                    id=uuid.uuid4(),
                    organization_id=org_id,
                    brand_profile_id=profile_id,
                    memory_id=memory_id,
                    version_no=version_no,
                    section=str(chunk["section"]),
                    text=str(chunk["text"]),
                    embedding_ref=chunk.get("embedding_ref"),
                    metadata_json=chunk.get("metadata_json") or {},
                )
            )
        await self._session.flush()
        return len(chunks)

    async def list_for_profile(self, org_id: uuid.UUID, profile_id: uuid.UUID) -> list[BrandVectorChunkRow]:
        result = await self._session.execute(
            select(BrandVectorChunkRow).where(
                BrandVectorChunkRow.organization_id == org_id,
                BrandVectorChunkRow.brand_profile_id == profile_id,
            )
        )
        return list(result.scalars().all())
