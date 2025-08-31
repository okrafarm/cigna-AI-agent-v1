import sqlite3
import asyncio
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pathlib import Path
from enum import Enum
import json
from dataclasses import dataclass


class ClaimStatus(Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    ERROR = "error"


@dataclass
class MedicalBill:
    provider_name: str
    patient_name: str
    service_date: date
    total_amount: float
    currency: str
    diagnosis_codes: List[str]
    treatment_description: str
    receipt_number: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None


@dataclass
class Claim:
    id: Optional[int]
    whatsapp_message_id: str
    bill_image_path: str
    extracted_data: MedicalBill
    status: ClaimStatus
    cigna_claim_number: Optional[str]
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    settlement_amount: Optional[float] = None
    settlement_currency: Optional[str] = None


class ClaimDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection = None
        
    async def connect(self):
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        await self._create_tables()
        
    async def _create_tables(self):
        await asyncio.to_thread(
            self._connection.execute,
            """
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                whatsapp_message_id TEXT UNIQUE NOT NULL,
                bill_image_path TEXT NOT NULL,
                provider_name TEXT,
                patient_name TEXT,
                service_date DATE,
                total_amount REAL,
                currency TEXT,
                diagnosis_codes TEXT,  -- JSON array
                treatment_description TEXT,
                receipt_number TEXT,
                additional_info TEXT,  -- JSON object
                status TEXT NOT NULL,
                cigna_claim_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT,
                settlement_amount REAL,
                settlement_currency TEXT
            )
            """
        )
        await asyncio.to_thread(self._connection.commit)
        
    async def insert_claim(self, claim: Claim) -> int:
        cursor = await asyncio.to_thread(
            self._connection.execute,
            """
            INSERT INTO claims (
                whatsapp_message_id, bill_image_path, provider_name, 
                patient_name, service_date, total_amount, currency,
                diagnosis_codes, treatment_description, receipt_number,
                additional_info, status, cigna_claim_number, created_at,
                updated_at, error_message, settlement_amount, settlement_currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim.whatsapp_message_id,
                claim.bill_image_path,
                claim.extracted_data.provider_name,
                claim.extracted_data.patient_name,
                claim.extracted_data.service_date.isoformat(),
                claim.extracted_data.total_amount,
                claim.extracted_data.currency,
                json.dumps(claim.extracted_data.diagnosis_codes),
                claim.extracted_data.treatment_description,
                claim.extracted_data.receipt_number,
                json.dumps(claim.extracted_data.additional_info) if claim.extracted_data.additional_info else None,
                claim.status.value,
                claim.cigna_claim_number,
                claim.created_at.isoformat(),
                claim.updated_at.isoformat(),
                claim.error_message,
                claim.settlement_amount,
                claim.settlement_currency
            )
        )
        await asyncio.to_thread(self._connection.commit)
        return cursor.lastrowid
        
    async def update_claim_status(self, claim_id: int, status: ClaimStatus, 
                                 error_message: Optional[str] = None,
                                 cigna_claim_number: Optional[str] = None,
                                 settlement_amount: Optional[float] = None,
                                 settlement_currency: Optional[str] = None):
        await asyncio.to_thread(
            self._connection.execute,
            """
            UPDATE claims 
            SET status = ?, updated_at = ?, error_message = ?,
                cigna_claim_number = ?, settlement_amount = ?, settlement_currency = ?
            WHERE id = ?
            """,
            (
                status.value,
                datetime.now().isoformat(),
                error_message,
                cigna_claim_number,
                settlement_amount,
                settlement_currency,
                claim_id
            )
        )
        await asyncio.to_thread(self._connection.commit)
        
    async def get_claim_by_id(self, claim_id: int) -> Optional[Claim]:
        cursor = await asyncio.to_thread(
            self._connection.execute,
            "SELECT * FROM claims WHERE id = ?",
            (claim_id,)
        )
        row = await asyncio.to_thread(cursor.fetchone)
        return self._row_to_claim(row) if row else None
        
    async def get_claims_by_status(self, status: ClaimStatus) -> List[Claim]:
        cursor = await asyncio.to_thread(
            self._connection.execute,
            "SELECT * FROM claims WHERE status = ? ORDER BY created_at DESC",
            (status.value,)
        )
        rows = await asyncio.to_thread(cursor.fetchall)
        return [self._row_to_claim(row) for row in rows]
        
    async def get_all_claims(self) -> List[Claim]:
        cursor = await asyncio.to_thread(
            self._connection.execute,
            "SELECT * FROM claims ORDER BY created_at DESC"
        )
        rows = await asyncio.to_thread(cursor.fetchall)
        return [self._row_to_claim(row) for row in rows]
        
    def _row_to_claim(self, row) -> Claim:
        extracted_data = MedicalBill(
            provider_name=row['provider_name'],
            patient_name=row['patient_name'],
            service_date=date.fromisoformat(row['service_date']),
            total_amount=row['total_amount'],
            currency=row['currency'],
            diagnosis_codes=json.loads(row['diagnosis_codes']) if row['diagnosis_codes'] else [],
            treatment_description=row['treatment_description'],
            receipt_number=row['receipt_number'],
            additional_info=json.loads(row['additional_info']) if row['additional_info'] else None
        )
        
        return Claim(
            id=row['id'],
            whatsapp_message_id=row['whatsapp_message_id'],
            bill_image_path=row['bill_image_path'],
            extracted_data=extracted_data,
            status=ClaimStatus(row['status']),
            cigna_claim_number=row['cigna_claim_number'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            error_message=row['error_message'],
            settlement_amount=row['settlement_amount'],
            settlement_currency=row['settlement_currency']
        )
        
    async def close(self):
        if self._connection:
            await asyncio.to_thread(self._connection.close)