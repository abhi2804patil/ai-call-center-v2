import asyncio
import io
import logging
import uuid
from datetime import datetime, timezone

import boto3
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.campaign import Campaign
from app.models.phone_number import PhoneNumber
from app.models.script import Script
from app.schemas.campaign import CampaignCreate, CampaignProgress, PhoneUploadResult
from app.utils.validators import validate_csv_file

logger = logging.getLogger(__name__)
settings = get_settings()


class CampaignManager:
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.bucket = settings.AWS_S3_BUCKET

    async def create_campaign(
        self, db: AsyncSession, company_id: uuid.UUID, data: CampaignCreate
    ) -> Campaign:
        result = await db.execute(
            select(Script).where(
                Script.id == data.script_id,
                Script.company_id == company_id,
                Script.is_active == True,
            )
        )
        script = result.scalar_one_or_none()
        if not script:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Script not found or does not belong to your company",
            )

        if script.audio_status != "ready":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Script audio is not ready (status: {script.audio_status}). Generate audio first.",
            )

        campaign = Campaign(
            company_id=company_id,
            script_id=data.script_id,
            name=data.name,
            direction=data.direction,
            schedule=data.schedule,
            settings=data.settings or {"max_retries": 3, "retry_interval_minutes": 30, "concurrent_limit": 10},
        )
        db.add(campaign)
        await db.flush()
        logger.info(f"Campaign created: {campaign.name} (id={campaign.id})")
        return campaign

    async def upload_phone_list(
        self, db: AsyncSession, campaign_id: uuid.UUID, company_id: uuid.UUID, file_content: bytes
    ) -> PhoneUploadResult:
        result = await db.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.company_id == company_id,
            )
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

        if campaign.status not in ("draft", "paused"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only upload phone numbers for draft or paused campaigns",
            )

        is_valid, errors, parsed_rows = validate_csv_file(file_content)

        valid_count = len(parsed_rows)
        invalid_count = len(errors)

        existing_result = await db.execute(
            select(PhoneNumber.phone_number).where(PhoneNumber.campaign_id == campaign_id)
        )
        existing_numbers = {r[0] for r in existing_result.all()}

        duplicates_removed = 0
        new_numbers = []
        for row in parsed_rows:
            if row["phone_number"] in existing_numbers:
                duplicates_removed += 1
                continue
            new_numbers.append(row)
            existing_numbers.add(row["phone_number"])

        for row in new_numbers:
            phone = PhoneNumber(
                campaign_id=campaign_id,
                phone_number=row["phone_number"],
                customer_data=row["customer_data"],
            )
            db.add(phone)

        campaign.total_numbers = len(existing_numbers)

        s3_key = f"csv/{company_id}/{campaign_id}/phone_list.csv"
        await asyncio.to_thread(
            self.s3.upload_fileobj,
            io.BytesIO(file_content),
            self.bucket,
            s3_key,
            ExtraArgs={"ContentType": "text/csv"},
        )
        campaign.phone_list_url = f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"

        await db.flush()

        return PhoneUploadResult(
            total=valid_count + invalid_count,
            valid=valid_count,
            invalid=invalid_count,
            duplicates_removed=duplicates_removed,
            errors=errors[:20],
        )

    async def start_campaign(self, db: AsyncSession, campaign_id: uuid.UUID, company_id: uuid.UUID) -> Campaign:
        result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id, Campaign.company_id == company_id)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

        if campaign.total_numbers == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign has no phone numbers. Upload a CSV first.",
            )

        script_result = await db.execute(select(Script).where(Script.id == campaign.script_id))
        script = script_result.scalar_one_or_none()
        if not script or script.audio_status != "ready":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Script audio is not ready",
            )

        campaign.status = "active"
        campaign.started_at = datetime.now(timezone.utc)
        await db.flush()

        from app.workers.call_worker import process_campaign_calls
        process_campaign_calls.delay(str(campaign_id))

        logger.info(f"Campaign started: {campaign.name}")
        return campaign

    async def pause_campaign(self, db: AsyncSession, campaign_id: uuid.UUID, company_id: uuid.UUID) -> Campaign:
        result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id, Campaign.company_id == company_id)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        if campaign.status != "active":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign is not active")

        campaign.status = "paused"
        await db.flush()
        logger.info(f"Campaign paused: {campaign.name}")
        return campaign

    async def resume_campaign(self, db: AsyncSession, campaign_id: uuid.UUID, company_id: uuid.UUID) -> Campaign:
        result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id, Campaign.company_id == company_id)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
        if campaign.status != "paused":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign is not paused")

        campaign.status = "active"
        await db.flush()

        from app.workers.call_worker import process_campaign_calls
        process_campaign_calls.delay(str(campaign_id))

        logger.info(f"Campaign resumed: {campaign.name}")
        return campaign

    async def stop_campaign(self, db: AsyncSession, campaign_id: uuid.UUID, company_id: uuid.UUID) -> Campaign:
        result = await db.execute(
            select(Campaign).where(Campaign.id == campaign_id, Campaign.company_id == company_id)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

        campaign.status = "cancelled"
        campaign.completed_at = datetime.now(timezone.utc)
        await db.flush()
        logger.info(f"Campaign stopped: {campaign.name}")
        return campaign

    async def get_progress(self, db: AsyncSession, campaign_id: uuid.UUID, company_id: uuid.UUID) -> CampaignProgress:
        result = await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.company_id == company_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

        remaining = campaign.total_numbers - campaign.called_count
        percent = (campaign.called_count / campaign.total_numbers * 100) if campaign.total_numbers > 0 else 0

        return CampaignProgress(
            total=campaign.total_numbers,
            called=campaign.called_count,
            succeeded=campaign.success_count,
            failed=campaign.failed_count,
            remaining=max(0, remaining),
            percent=round(percent, 1),
        )
