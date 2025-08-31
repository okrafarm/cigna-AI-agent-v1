import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from loguru import logger

from src.config.settings import Settings
from src.database.models import ClaimDatabase, Claim, ClaimStatus


class CSVExporter:
    def __init__(self, settings: Settings, db: ClaimDatabase):
        self.settings = settings
        self.db = db
        self._running = False
        
    async def export_loop(self):
        """Continuously export claims data to CSV"""
        self._running = True
        logger.info("Started CSV export loop")
        
        while self._running:
            try:
                await self.export_all_claims()
                
                # Export every 10 minutes
                await asyncio.sleep(600)
                
            except Exception as e:
                logger.error(f"Error in CSV export loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
                
        logger.info("CSV export loop stopped")
        
    async def export_all_claims(self) -> Path:
        """Export all claims to CSV file"""
        try:
            # Get all claims from database
            claims = await self.db.get_all_claims()
            
            if not claims:
                logger.info("No claims to export")
                return None
                
            # Convert claims to DataFrame
            df = self._claims_to_dataframe(claims)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cigna_claims_{timestamp}.csv"
            filepath = self.settings.export_dir / filename
            
            # Also create a "latest" version for easy access
            latest_filepath = self.settings.export_dir / "cigna_claims_latest.csv"
            
            # Export to CSV
            df.to_csv(filepath, index=False)
            df.to_csv(latest_filepath, index=False)
            
            logger.info(f"Exported {len(claims)} claims to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to export claims to CSV: {e}")
            return None
            
    async def export_claims_by_status(self, status: ClaimStatus) -> Path:
        """Export claims with specific status to CSV"""
        try:
            claims = await self.db.get_claims_by_status(status)
            
            if not claims:
                logger.info(f"No claims with status {status.value} to export")
                return None
                
            df = self._claims_to_dataframe(claims)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cigna_claims_{status.value}_{timestamp}.csv"
            filepath = self.settings.export_dir / filename
            
            df.to_csv(filepath, index=False)
            
            logger.info(f"Exported {len(claims)} {status.value} claims to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to export {status.value} claims to CSV: {e}")
            return None
            
    def _claims_to_dataframe(self, claims: List[Claim]) -> pd.DataFrame:
        """Convert list of claims to pandas DataFrame"""
        data = []
        
        for claim in claims:
            # Flatten claim data into a single row
            row = {
                # Basic claim info
                'claim_id': claim.id,
                'whatsapp_message_id': claim.whatsapp_message_id,
                'status': claim.status.value,
                'cigna_claim_number': claim.cigna_claim_number or '',
                'created_at': claim.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': claim.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                
                # Medical bill info
                'provider_name': claim.extracted_data.provider_name,
                'patient_name': claim.extracted_data.patient_name,
                'service_date': claim.extracted_data.service_date.strftime('%Y-%m-%d'),
                'total_amount': claim.extracted_data.total_amount,
                'currency': claim.extracted_data.currency,
                'treatment_description': claim.extracted_data.treatment_description,
                'receipt_number': claim.extracted_data.receipt_number or '',
                'diagnosis_codes': ', '.join(claim.extracted_data.diagnosis_codes) if claim.extracted_data.diagnosis_codes else '',
                
                # Settlement info
                'settlement_amount': claim.settlement_amount or 0,
                'settlement_currency': claim.settlement_currency or '',
                
                # Additional info
                'error_message': claim.error_message or '',
                'bill_image_path': claim.bill_image_path,
                
                # Calculated fields
                'days_since_submission': (datetime.now() - claim.created_at).days,
                'processing_time_hours': (claim.updated_at - claim.created_at).total_seconds() / 3600,
            }
            
            # Add additional info fields if available
            if claim.extracted_data.additional_info:
                for key, value in claim.extracted_data.additional_info.items():
                    row[f'additional_{key}'] = str(value) if value is not None else ''
                    
            data.append(row)
            
        # Create DataFrame and sort by creation date (newest first)
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values('created_at', ascending=False)
            
        return df
        
    async def generate_summary_report(self) -> Path:
        """Generate a summary report with statistics"""
        try:
            claims = await self.db.get_all_claims()
            
            if not claims:
                logger.info("No claims to summarize")
                return None
                
            # Calculate summary statistics
            summary_data = self._calculate_summary_stats(claims)
            
            # Create summary DataFrame
            summary_df = pd.DataFrame([summary_data])
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cigna_claims_summary_{timestamp}.csv"
            filepath = self.settings.export_dir / filename
            
            # Also create a "latest" version
            latest_filepath = self.settings.export_dir / "cigna_claims_summary_latest.csv"
            
            # Export summary
            summary_df.to_csv(filepath, index=False)
            summary_df.to_csv(latest_filepath, index=False)
            
            logger.info(f"Generated summary report: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to generate summary report: {e}")
            return None
            
    def _calculate_summary_stats(self, claims: List[Claim]) -> Dict[str, Any]:
        """Calculate summary statistics for claims"""
        total_claims = len(claims)
        
        # Count by status
        status_counts = {}
        for status in ClaimStatus:
            status_counts[f'count_{status.value}'] = sum(1 for c in claims if c.status == status)
            
        # Calculate amounts
        total_claimed = sum(c.extracted_data.total_amount for c in claims)
        total_settled = sum(c.settlement_amount or 0 for c in claims if c.settlement_amount)
        
        # Average processing time
        completed_claims = [c for c in claims if c.status in [ClaimStatus.APPROVED, ClaimStatus.PAID, ClaimStatus.REJECTED]]
        avg_processing_hours = 0
        if completed_claims:
            total_processing_time = sum((c.updated_at - c.created_at).total_seconds() / 3600 for c in completed_claims)
            avg_processing_hours = total_processing_time / len(completed_claims)
            
        # Success rate
        successful_claims = sum(1 for c in claims if c.status in [ClaimStatus.APPROVED, ClaimStatus.PAID])
        success_rate = (successful_claims / total_claims * 100) if total_claims > 0 else 0
        
        return {
            'report_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_claims': total_claims,
            'total_claimed_amount': total_claimed,
            'total_settled_amount': total_settled,
            'success_rate_percent': round(success_rate, 2),
            'average_processing_hours': round(avg_processing_hours, 2),
            **status_counts
        }
        
    async def stop(self):
        """Stop the CSV export loop"""
        self._running = False
        logger.info("Stopping CSV exporter")
        
    async def export_for_google_sheets(self) -> Path:
        """Export in a format optimized for Google Sheets viewing"""
        try:
            claims = await self.db.get_all_claims()
            
            if not claims:
                return None
                
            # Create simplified view for Google Sheets
            simplified_data = []
            
            for claim in claims:
                row = {
                    'ID': claim.id,
                    'Status': claim.status.value.upper(),
                    'Patient': claim.extracted_data.patient_name,
                    'Provider': claim.extracted_data.provider_name,
                    'Service Date': claim.extracted_data.service_date.strftime('%Y-%m-%d'),
                    'Amount': f"{claim.extracted_data.total_amount} {claim.extracted_data.currency}",
                    'Treatment': claim.extracted_data.treatment_description[:50] + '...' if len(claim.extracted_data.treatment_description) > 50 else claim.extracted_data.treatment_description,
                    'Cigna Claim #': claim.cigna_claim_number or 'N/A',
                    'Settlement': f"{claim.settlement_amount} {claim.settlement_currency}" if claim.settlement_amount else 'N/A',
                    'Created': claim.created_at.strftime('%Y-%m-%d'),
                    'Updated': claim.updated_at.strftime('%Y-%m-%d'),
                    'Days Pending': (datetime.now() - claim.created_at).days,
                    'Notes': claim.error_message or ''
                }
                simplified_data.append(row)
                
            df = pd.DataFrame(simplified_data)
            
            # Sort by most recent first
            if not df.empty:
                df = df.sort_values('Created', ascending=False)
                
            # Export to Google Sheets friendly file
            filepath = self.settings.export_dir / "cigna_claims_google_sheets.csv"
            df.to_csv(filepath, index=False)
            
            logger.info(f"Exported Google Sheets format: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to export Google Sheets format: {e}")
            return None