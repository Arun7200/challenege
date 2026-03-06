"""
Task 3: Parallel Data Fetcher
Async parallelism exercise - fetch from multiple systems concurrently.
"""

import asyncio
import random
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CustomerContext:
    """Merged context from all data sources."""
    crm_data: Optional[Dict[str, Any]] = None
    billing_data: Optional[Dict[str, Any]] = None
    ticket_history: Optional[list] = None
    data_complete: bool = False
    fetch_time_ms: float = 0.0
    warnings: list = field(default_factory=list)


# ============================================================================
# MOCK ASYNC FUNCTIONS - Simulating external system latency
# ============================================================================

async def fetch_crm(phone: str) -> Dict[str, Any]:
    """
    Simulate CRM system fetch (200-400ms delay).
    Returns customer account information.
    """
    delay = random.uniform(0.2, 0.4)
    await asyncio.sleep(delay)
    
    return {
        "customer_id": f"CRM_{phone}",
        "phone": phone,
        "name": f"Customer_{phone.replace('+', '').replace('-', '')}",
        "account_status": "active",
        "customer_tier": random.choice(["standard", "vip", "premium"]),
        "years_as_customer": random.randint(1, 15),
        "account_balance": round(random.uniform(-100, 500), 2),
    }


async def fetch_billing(phone: str) -> Dict[str, Any]:
    """
    Simulate billing system fetch (150-350ms delay).
    Returns payment status and billing information.
    10% chance of TimeoutError.
    """
    # 10% random chance of timeout
    if random.random() < 0.1:
        raise TimeoutError(f"Billing system timeout for {phone}")
    
    delay = random.uniform(0.15, 0.35)
    await asyncio.sleep(delay)
    
    return {
        "phone": phone,
        "current_bill": round(random.uniform(20, 200), 2),
        "due_date": "2026-03-15",
        "overdue_amount": round(random.uniform(0, 150), 2),
        "payment_status": random.choice(["current", "30_days", "60_days"]),
        "plan_type": random.choice(["basic", "premium", "family"]),
        "auto_pay_enabled": random.choice([True, False]),
    }


async def fetch_ticket_history(phone: str) -> list:
    """
    Simulate ticket history fetch (100-300ms delay).
    Returns last 5 customer complaints/tickets.
    """
    delay = random.uniform(0.1, 0.3)
    await asyncio.sleep(delay)
    
    intents = ["connectivity", "billing", "cancellation", "upgrade", "downgrade"]
    tickets = []
    for i in range(random.randint(2, 5)):
        tickets.append({
            "ticket_id": f"TKT_{phone}_{i}",
            "intent": random.choice(intents),
            "created_date": f"2026-{random.randint(1,3):02d}-{random.randint(1,28):02d}",
            "status": random.choice(["resolved", "escalated", "open"]),
            "resolution_time_hours": random.randint(1, 48),
        })
    
    return sorted(tickets, key=lambda x: x["created_date"], reverse=True)[:5]


# ============================================================================
# SEQUENTIAL VS PARALLEL FETCHERS
# ============================================================================

async def fetch_sequential(phone: str) -> CustomerContext:
    """
    Fetch data sequentially (one after another).
    Slow because we wait for each request to complete before starting the next.
    
    Expected time: ~500-1000ms (sum of all three requests)
    """
    start_time = time.time()
    context = CustomerContext()
    
    try:
        # Sequential: each blocks on the previous
        logger.info(f"[SEQUENTIAL] Starting fetch for {phone}")
        context.crm_data = await fetch_crm(phone)
        logger.info(f"[SEQUENTIAL] CRM complete")
        
        context.billing_data = await fetch_billing(phone)
        logger.info(f"[SEQUENTIAL] Billing complete")
        
        context.ticket_history = await fetch_ticket_history(phone)
        logger.info(f"[SEQUENTIAL] Tickets complete")
        
        context.data_complete = True
    
    except TimeoutError as e:
        logger.warning(f"[SEQUENTIAL] Billing timeout: {e}")
        context.warnings.append(f"Billing system unavailable: {e}")
        context.data_complete = False
    except Exception as e:
        logger.error(f"[SEQUENTIAL] Error: {e}")
        context.data_complete = False
    
    elapsed = (time.time() - start_time) * 1000
    context.fetch_time_ms = elapsed
    return context


async def fetch_parallel(phone: str) -> CustomerContext:
    """
    Fetch data in parallel (all at once).
    Fast because all three requests happen simultaneously.
    Uses asyncio.gather() with return_exceptions=True to handle failures gracefully.
    
    Expected time: ~400ms (duration of the slowest request)
    Speed improvement: 2x-2.5x faster than sequential
    """
    start_time = time.time()
    context = CustomerContext()
    
    try:
        logger.info(f"[PARALLEL] Starting concurrent fetch for {phone}")
        
        # Parallel: all three run concurrently
        # return_exceptions=True means errors don't crash - we get them in the results
        results = await asyncio.gather(
            fetch_crm(phone),
            fetch_billing(phone),
            fetch_ticket_history(phone),
            return_exceptions=True
        )
        
        # Process results - some might be exceptions
        crm_result, billing_result, ticket_result = results
        
        # Handle each result carefully
        if isinstance(crm_result, Exception):
            logger.warning(f"[PARALLEL] CRM error: {crm_result}")
            context.warnings.append(f"CRM fetch failed: {crm_result}")
        else:
            context.crm_data = crm_result
            logger.info(f"[PARALLEL] CRM complete")
        
        if isinstance(billing_result, Exception):
            logger.warning(f"[PARALLEL] Billing error: {billing_result}")
            context.warnings.append(f"Billing fetch failed: {billing_result}")
        else:
            context.billing_data = billing_result
            logger.info(f"[PARALLEL] Billing complete")
        
        if isinstance(ticket_result, Exception):
            logger.warning(f"[PARALLEL] Ticket error: {ticket_result}")
            context.warnings.append(f"Ticket fetch failed: {ticket_result}")
        else:
            context.ticket_history = ticket_result
            logger.info(f"[PARALLEL] Tickets complete")
        
        # data_complete is True only if ALL sources succeeded
        context.data_complete = (
            not isinstance(crm_result, Exception)
            and not isinstance(billing_result, Exception)
            and not isinstance(ticket_result, Exception)
        )
    
    except Exception as e:
        logger.error(f"[PARALLEL] Unexpected error: {e}")
        context.data_complete = False
        context.warnings.append(f"Unexpected error: {e}")
    
    elapsed = (time.time() - start_time) * 1000
    context.fetch_time_ms = elapsed
    return context


# ============================================================================
# COMPARISON AND BENCHMARKING
# ============================================================================

async def benchmark_fetchers(phone: str, num_iterations: int = 5):
    """
    Run both fetchers multiple times and show performance comparison.
    """
    print(f"\n{'='*70}")
    print(f"PERFORMANCE BENCHMARK: {num_iterations} iterations for phone {phone}")
    print(f"{'='*70}\n")
    
    sequential_times = []
    parallel_times = []
    
    for i in range(num_iterations):
        print(f"Iteration {i+1}/{num_iterations}...")
        
        # Sequential fetch
        seq_context = await fetch_sequential(phone)
        sequential_times.append(seq_context.fetch_time_ms)
        print(f"  Sequential: {seq_context.fetch_time_ms:.0f}ms")
        
        # Parallel fetch
        par_context = await fetch_parallel(phone)
        parallel_times.append(par_context.fetch_time_ms)
        print(f"  Parallel:   {par_context.fetch_time_ms:.0f}ms")
        print()
    
    # Statistics
    avg_sequential = sum(sequential_times) / len(sequential_times)
    avg_parallel = sum(parallel_times) / len(parallel_times)
    speedup = avg_sequential / avg_parallel
    
    print(f"\n{'='*70}")
    print(f"RESULTS:")
    print(f"{'='*70}")
    print(f"Average Sequential: {avg_sequential:.1f}ms")
    print(f"Average Parallel:   {avg_parallel:.1f}ms")
    print(f"Speed Improvement:  {speedup:.2f}x faster")
    print(f"Time Saved per Call: {(avg_sequential - avg_parallel):.1f}ms")
    print(f"{'='*70}\n")
    
    return {
        "sequential_times": sequential_times,
        "parallel_times": parallel_times,
        "avg_sequential": avg_sequential,
        "avg_parallel": avg_parallel,
        "speedup_factor": speedup,
    }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def print_context(context: CustomerContext, label: str = ""):
    """Pretty-print a CustomerContext."""
    print(f"\n{label}")
    print(f"{'─'*60}")
    print(f"Data Complete: {context.data_complete}")
    print(f"Fetch Time: {context.fetch_time_ms:.1f}ms")
    
    if context.crm_data:
        print(f"\nCRM Data ({len(context.crm_data)} fields):")
        for k, v in context.crm_data.items():
            print(f"  {k}: {v}")
    else:
        print("\nCRM Data: NOT AVAILABLE")
    
    if context.billing_data:
        print(f"\nBilling Data ({len(context.billing_data)} fields):")
        for k, v in context.billing_data.items():
            print(f"  {k}: {v}")
    else:
        print("\nBilling Data: NOT AVAILABLE")
    
    if context.ticket_history:
        print(f"\nTicket History ({len(context.ticket_history)} tickets):")
        for ticket in context.ticket_history:
            print(f"  - {ticket['intent']}: {ticket['status']} ({ticket['created_date']})")
    else:
        print("\nTicket History: NOT AVAILABLE")
    
    if context.warnings:
        print(f"\nWarnings ({len(context.warnings)}):")
        for warning in context.warnings:
            print(f"  ⚠️  {warning}")
    
    print(f"{'─'*60}\n")


# ============================================================================
# MAIN EXAMPLES
# ============================================================================

async def main():
    """Run example demonstrations."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    phone = "+1-555-123-4567"
    
    # Example 1: Single parallel fetch
    print("\n[EXAMPLE 1] Single Parallel Fetch")
    context = await fetch_parallel(phone)
    print_context(context, "Results from fetch_parallel():")
    
    # Example 2: Benchmark comparison
    print("\n[EXAMPLE 2] Performance Benchmark")
    results = await benchmark_fetchers(phone, num_iterations=3)
    
    print(f"\n✅ Parallel is {results['speedup_factor']:.2f}x faster than sequential!")
    print(f"   That's {(results['avg_sequential'] - results['avg_parallel']):.0f}ms saved per call.")


if __name__ == "__main__":
    asyncio.run(main())
