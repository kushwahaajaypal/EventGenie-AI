"""
EventGenie AI - Budget Calculation Service
All arithmetic is done in Python, not delegated to the AI.
"""
from typing import Any


def calculate_budget_totals(budget_items: list[dict]) -> dict[str, Any]:
    """
    Calculate budget totals from a list of budget item dicts.
    Returns summary dict with totals, remaining, and overrun flag.
    """
    total_allocated = sum(float(item.get('amount', 0)) for item in budget_items)
    total_estimated = sum(float(item.get('estimated_amount', 0)) for item in budget_items)

    return {
        'total_allocated': round(total_allocated, 2),
        'total_estimated': round(total_estimated, 2),
        'item_count': len(budget_items),
    }


def recalculate_percentages(budget_items: list[dict], total_budget: float) -> list[dict]:
    """
    Recalculate percentage share of each item against the total budget.
    Mutates and returns the list.
    """
    if total_budget <= 0:
        return budget_items
    for item in budget_items:
        amount = float(item.get('amount', 0))
        item['percentage'] = round((amount / total_budget) * 100, 2)
    return budget_items


def check_budget_overrun(budget_items: list[dict], total_budget: float) -> dict[str, Any]:
    """
    Check whether total allocations exceed the stated budget.
    Returns overrun details.
    """
    totals = calculate_budget_totals(budget_items)
    total_allocated = totals['total_allocated']
    remaining = round(total_budget - total_allocated, 2)
    is_overrun = remaining < 0

    return {
        'total_budget': round(total_budget, 2),
        'total_allocated': total_allocated,
        'remaining': remaining,
        'is_overrun': is_overrun,
        'overrun_amount': round(abs(remaining), 2) if is_overrun else 0,
        'utilization_percent': round((total_allocated / total_budget * 100), 1) if total_budget > 0 else 0,
    }


def apply_contingency(budget_items: list[dict], total_budget: float, contingency_pct: float = 5.0) -> float:
    """
    Calculate a contingency reserve amount.
    Returns the contingency amount (not added to items; caller manages this).
    """
    contingency_pct = max(0.0, min(contingency_pct, 50.0))  # clamp 0-50%
    return round(total_budget * contingency_pct / 100, 2)


def parse_ai_budget_items(budget_breakdown: list[dict], total_budget: float) -> list[dict]:
    """
    Parse and validate AI-generated budget items.
    Ensures amounts sum correctly against the total budget.
    """
    validated = []
    for item in budget_breakdown:
        if not isinstance(item, dict):
            continue
        category = str(item.get('category', 'Miscellaneous')).strip()
        if not category:
            continue

        estimated_amount = _safe_float(item.get('estimated_amount', 0))
        percentage = _safe_float(item.get('percentage', 0))

        # If estimated_amount not set but percentage is, derive from total
        if estimated_amount == 0 and percentage > 0 and total_budget > 0:
            estimated_amount = round(total_budget * percentage / 100, 2)

        validated.append({
            'category': category,
            'description': str(item.get('description', '')),
            'estimated_amount': estimated_amount,
            'amount': estimated_amount,  # Start with estimate as actual
            'percentage': percentage,
            'notes': str(item.get('notes', '')),
            'is_confirmed': False,  # All AI amounts are estimates
        })

    # Correct total if AI math is off
    if validated and total_budget > 0:
        ai_total = sum(v['estimated_amount'] for v in validated)
        if ai_total > 0 and abs(ai_total - total_budget) / total_budget > 0.05:
            # Scale to match budget within 5% tolerance
            scale = total_budget / ai_total
            for v in validated:
                v['estimated_amount'] = round(v['estimated_amount'] * scale, 2)
                v['amount'] = v['estimated_amount']

        # Recalculate percentages after scaling
        for v in validated:
            v['percentage'] = round(v['amount'] / total_budget * 100, 2) if total_budget > 0 else 0

    return validated


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
