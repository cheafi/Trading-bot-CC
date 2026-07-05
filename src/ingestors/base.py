"""
TradingAI Bot - Base Ingestor
Abstract base class for all data ingestors.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import asyncio

from src.core.database import get_session


class BaseIngestor(ABC):
    """
    Abstract base class for data ingestors.
    
    All ingestors should:
    1. Fetch data from external APIs
    2. Transform to internal format
    3. Store in database
    4. Handle rate limiting and errors
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"ingestor.{name}")
        self._rate_limit_delay: float = 0.1  # Default delay between requests
        self._last_request_time: Optional[datetime] = None
    
    @abstractmethod
    async def fetch(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch data from external source.
        
        Returns:
            List of raw data records
        """
        pass
    
    @abstractmethod
    async def transform(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform raw data to internal format.
        
        Args:
            raw_data: Raw records from fetch()
        
        Returns:
            Transformed records ready for storage
        """
        pass
    
    @abstractmethod
    async def store(self, records: List[Dict[str, Any]]) -> int:
        """
        Store records in database.
        
        Args:
            records: Transformed records from transform()
        
        Returns:
            Number of records stored
        """
        pass
    
    async def run(self, **kwargs) -> Dict[str, Any]:
        """
        Execute full ingestion pipeline.
        
        Returns:
            Summary of ingestion run
        """
        start_time = datetime.utcnow()
        result = {
            'ingestor': self.name,
            'started_at': start_time.isoformat(),
            'status': 'pending',
            'records_fetched': 0,
            'records_stored': 0,
            'errors': []
        }
        
        try:
            # Fetch
            self.logger.info(f"Starting {self.name} ingestion")
            raw_data = await self.fetch(**kwargs)
            result['records_fetched'] = len(raw_data)
            
            if not raw_data:
                self.logger.warning(f"No data fetched for {self.name}")
                result['status'] = 'empty'
                return result
            
            # Transform
            transformed = await self.transform(raw_data)
            
            # Store
            stored_count = await self.store(transformed)
            result['records_stored'] = stored_count
            result['status'] = 'success'
            
            self.logger.info(
                f"{self.name} ingestion complete: "
                f"{result['records_fetched']} fetched, {stored_count} stored"
            )
            
        except Exception as e:
            self.logger.error(f"{self.name} ingestion failed: {e}")
            result['status'] = 'error'
            result['errors'].append(str(e))
        
        result['completed_at'] = datetime.utcnow().isoformat()
        result['duration_seconds'] = (
            datetime.utcnow() - start_time
        ).total_seconds()
        
        return result
    
    async def _respect_rate_limit(self):
        """Wait if needed to respect rate limits."""
        if self._last_request_time:
            elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
            if elapsed < self._rate_limit_delay:
                await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = datetime.utcnow()
