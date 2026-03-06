"""
Task 2: Database Schema
PostgreSQL schema and Python repository for call records.
"""

import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import logging

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

try:
    import psycopg
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False


logger = logging.getLogger(__name__)


# PostgreSQL CREATE TABLE DDL
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS call_records (
    id SERIAL PRIMARY KEY,
    
    -- Customer Information
    customer_phone VARCHAR(20) NOT NULL,
    
    -- Call Metadata
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('voice', 'whatsapp', 'chat')),
    transcript TEXT,
    
    -- AI Response Information
    ai_response TEXT NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    
    -- Outcome and Resolution
    outcome VARCHAR(20) NOT NULL CHECK (outcome IN ('resolved', 'escalated', 'failed')),
    
    -- Customer Satisfaction
    csat_score INTEGER CHECK (csat_score IS NULL OR (csat_score >= 1 AND csat_score <= 5)),
    
    -- Timestamps and Duration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_seconds INTEGER NOT NULL,
    
    -- Index support fields
    intent_type VARCHAR(50),
    
    -- Audit fields
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INDEX 1: Customer phone lookup for retrieving recent interactions
-- WHY: Frequently queried by fetch_recent() method and customer history reports.
-- Enables fast lookups when a customer calls back - need recent interaction context.
CREATE INDEX IF NOT EXISTS idx_call_records_phone_created 
ON call_records (customer_phone, created_at DESC);

-- INDEX 2: Outcome filtering for analytics and escalation metrics
-- WHY: Reports group by outcome status (resolved, escalated, failed).
-- Querying "all escalated calls in last 7 days" is a common operation.
CREATE INDEX IF NOT EXISTS idx_call_records_outcome_created
ON call_records (outcome, created_at DESC);

-- INDEX 3: Intent-based analytics for training and troubleshooting
-- WHY: Need to find "repeat complaints" - same intent appearing frequently.
-- Essential for escalation rules and identifying problematic intent types.
CREATE INDEX IF NOT EXISTS idx_call_records_intent_csat
ON call_records (intent_type, csat_score, created_at DESC);
"""

# SQL query for top 5 intent types with lowest resolution rate
TOP_INTENTS_LOWEST_RESOLUTION_SQL = """
SELECT 
    intent_type,
    COUNT(*) as total_interactions,
    SUM(CASE WHEN outcome = 'resolved' THEN 1 ELSE 0 END) as resolved_count,
    ROUND(100.0 * SUM(CASE WHEN outcome = 'resolved' THEN 1 ELSE 0 END) / 
          COUNT(*), 2) as resolution_rate_percent,
    ROUND(AVG(csat_score)::NUMERIC, 2) as avg_csat
FROM call_records
WHERE created_at >= NOW() - INTERVAL '7 days'
    AND intent_type IS NOT NULL
GROUP BY intent_type
ORDER BY resolution_rate_percent ASC, avg_csat ASC
LIMIT 5;
"""


class CallRecordRepository:
    """
    Async repository for reading and writing call records.
    Uses parameterized queries - NEVER formats variables directly into SQL strings.
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize repository with database connection details.
        
        Args:
            connection_string: PostgreSQL connection string
                              (format: postgresql://user:password@host:port/dbname)
        """
        self.connection_string = connection_string or (
            "postgresql://user:password@localhost:5432/telecom"
        )
        self.pool = None
        self.use_asyncpg = HAS_ASYNCPG
    
    async def initialize(self):
        """Initialize connection pool - call this before using the repository."""
        if self.use_asyncpg:
            self.pool = await asyncpg.create_pool(self.connection_string)
        else:
            raise RuntimeError("asyncpg not installed. Install with: pip install asyncpg")
    
    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
    
    async def save(self, call_data: Dict[str, Any]) -> int:
        """
        Save a call record to the database.
        
        Args:
            call_data: Dictionary with call information:
                - customer_phone (str, required): Customer phone number
                - channel (str, required): 'voice', 'whatsapp', or 'chat'
                - transcript (str, optional): Call transcript
                - ai_response (str, required): AI response text
                - confidence (float, required): 0-1
                - outcome (str, required): 'resolved', 'escalated', 'failed'
                - csat_score (int, optional): 1-5 or None
                - duration_seconds (int, required): Call duration
                - intent_type (str, optional): Intent classification
        
        Returns:
            ID of the saved record
        
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate required fields
        required = ["customer_phone", "channel", "ai_response", "confidence", 
                   "outcome", "duration_seconds"]
        for field in required:
            if field not in call_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate enums
        valid_channels = {"voice", "whatsapp", "chat"}
        if call_data["channel"] not in valid_channels:
            raise ValueError(f"Invalid channel: {call_data['channel']}")
        
        valid_outcomes = {"resolved", "escalated", "failed"}
        if call_data["outcome"] not in valid_outcomes:
            raise ValueError(f"Invalid outcome: {call_data['outcome']}")
        
        # Validate ranges
        if not 0 <= call_data["confidence"] <= 1:
            raise ValueError(f"Confidence must be 0-1, got {call_data['confidence']}")
        
        if call_data.get("csat_score") is not None:
            if not 1 <= call_data["csat_score"] <= 5:
                raise ValueError(f"CSAT must be 1-5, got {call_data['csat_score']}")
        
        if call_data["duration_seconds"] < 0:
            raise ValueError("Duration cannot be negative")
        
        # Use parameterized query - NEVER format variables directly
        query = """
        INSERT INTO call_records 
        (customer_phone, channel, transcript, ai_response, confidence, 
         outcome, csat_score, duration_seconds, intent_type, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id;
        """
        
        try:
            async with self.pool.acquire() as conn:
                record_id = await conn.fetchval(
                    query,
                    call_data["customer_phone"],
                    call_data["channel"],
                    call_data.get("transcript"),
                    call_data["ai_response"],
                    call_data["confidence"],
                    call_data["outcome"],
                    call_data.get("csat_score"),
                    call_data["duration_seconds"],
                    call_data.get("intent_type"),
                    datetime.utcnow(),
                )
                return record_id
        except Exception as e:
            logger.error(f"Error saving call record: {e}")
            raise
    
    async def get_recent(
        self, phone: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recent call records for a customer.
        
        Args:
            phone: Customer phone number
            limit: Number of records to return (default 5)
        
        Returns:
            List of dictionaries representing recent calls
        """
        # Use parameterized query - NEVER format variables directly
        query = """
        SELECT 
            id, customer_phone, channel, transcript, ai_response, 
            confidence, outcome, csat_score, duration_seconds, 
            intent_type, created_at, updated_at
        FROM call_records
        WHERE customer_phone = $1
        ORDER BY created_at DESC
        LIMIT $2;
        """
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, phone, limit)
                
                # Convert to list of dicts
                records = []
                for row in rows:
                    records.append(dict(row))
                return records
        except Exception as e:
            logger.error(f"Error fetching call records for {phone}: {e}")
            raise
    
    async def get_top_intents_lowest_resolution(self) -> List[Dict[str, Any]]:
        """
        Get top 5 intent types with lowest resolution rate in last 7 days.
        
        Returns:
            List of dicts with: intent_type, total_interactions, resolved_count,
                               resolution_rate_percent, avg_csat
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(TOP_INTENTS_LOWEST_RESOLUTION_SQL)
                records = [dict(row) for row in rows]
                return records
        except Exception as e:
            logger.error(f"Error querying top intents: {e}")
            raise


async def initialize_schema(connection_string: str):
    """
    Initialize the database schema.
    Run this once to create the call_records table.
    """
    if not HAS_ASYNCPG:
        raise RuntimeError("asyncpg required. Install with: pip install asyncpg")
    
    try:
        pool = await asyncpg.create_pool(connection_string, min_size=1, max_size=5)
        async with pool.acquire() as conn:
            await conn.execute(CREATE_TABLE_SQL)
            logger.info("Database schema initialized successfully")
        await pool.close()
    except Exception as e:
        logger.error(f"Error initializing schema: {e}")
        raise


if __name__ == "__main__":
    # Example schema initialization
    import os
    
    logging.basicConfig(level=logging.INFO)
    
    # This would be run once to set up the database
    # db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/telecom")
    # asyncio.run(initialize_schema(db_url))
    
    print("CallRecordRepository available for use")
    print("Schema file: CREATE_TABLE_SQL")
    print("Query file: TOP_INTENTS_LOWEST_RESOLUTION_SQL")
