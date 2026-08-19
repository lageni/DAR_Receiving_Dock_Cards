"""Pure calculations on read-rate data: dates, averages, trend, recommendation."""

def format_date_for_chart(date_str: str) -> str:
    """Convert YYYY-MM-DD to abbreviated month+year (e.g., 'Dec 2025')."""
    try:
        parts = date_str.split('-')
        if len(parts) == 3:
            year, month, day = parts
            months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            month_int = int(month)
            return f"{months[month_int]} {year}"
    except:
        pass
    return date_str


def get_avg_performance(item_rates: list) -> float:
    """Calculate average ACL Performance using total(acl_null_cnt) / total(acl_event_cnt).
    
    NOTE: Despite the name, acl_null_cnt actually means SUCCESSFUL reads (misleading naming).
    This is a WEIGHTED average - more accurate than averaging individual percentages.
    
    Returns:
        Performance percentage (0-100), where:
        - 100% = all reads successful
        - 0% = all reads failed
    """
    if not item_rates:
        return 0
    
    # Sum ALL null counts and ALL event counts (weighted average)
    total_null_cnt = sum(r['null_cnt'] for r in item_rates)
    total_event_cnt = sum(r['event_cnt'] for r in item_rates)
    
    if total_event_cnt == 0:
        return 0
    
    # Calculate performance: total(acl_null_cnt) / total(acl_event_cnt) * 100
    # acl_null_cnt = successful reads (despite misleading name)
    performance = (total_null_cnt / total_event_cnt) * 100
    
    return performance


def get_trend_status(item_rates: list) -> str:
    """Determine trend: Improving, Consistent, Inconsistent, or Declining."""
    if len(item_rates) < 2:
        return "N/A"
    
    # Calculate trend by comparing first half to second half
    mid = len(item_rates) // 2
    first_half = item_rates[:mid]
    second_half = item_rates[mid:]
    
    avg_first = sum(r['null_pct'] for r in first_half) / len(first_half) if first_half else 0
    avg_second = sum(r['null_pct'] for r in second_half) / len(second_half) if second_half else 0
    
    # Check for consistency
    first_values = [r['null_pct'] for r in first_half]
    second_values = [r['null_pct'] for r in second_half]
    first_std = max(first_values) - min(first_values) if first_values else 0
    second_std = max(second_values) - min(second_values) if second_values else 0
    
    # Determine status
    if first_std < 1 and second_std < 1:  # Both halves stable
        return "Consistent"
    elif avg_second > avg_first:  # Getting better
        return "Improving"
    elif abs(avg_second - avg_first) < 2:  # Similar trend
        return "Consistent"
    else:  # Getting worse
        return "Declining"


def get_color_for_performance(pct: float) -> str:
    """Get gradient color from red (0%) to green (100%)."""
    if pct < 25:
        return "#dc2626"  # Red
    elif pct < 50:
        return "#f59e0b"  # Amber
    elif pct < 75:
        return "#eab308"  # Yellow
    else:
        return "#16a34a"  # Green
def get_recommendation(avg_perf: float, trend_status: str, catalog_gtin: str = "", orderable_gtin: str = "") -> tuple:
    """Get ACL recommendation based on performance and trend.
    
    Special case: If performance < 50% AND catalog_gtin is DIFFERENT from orderable_gtin,
    this indicates a catalog mismatch issue -> "INSPECT CATALOG; TAKE TO PROBLEMS"
    
    If catalog_gtin == orderable_gtin, treat as if there's no catalog GTIN (it's just the normal GTIN).
    """
    # Check if catalog GTIN is truly different from orderable (real catalog issue)
    has_catalog_issue = catalog_gtin and catalog_gtin != orderable_gtin
    
    if avg_perf < 50 and has_catalog_issue:
        return "INSPECT CATALOG; TAKE TO PROBLEMS", "#dc2626", "from-red-50 via-red-50 to-red-100 border-red-300"
    elif avg_perf >= 85:
        return "ACL APPROVED", "#16a34a", "from-green-50 via-green-50 to-green-100 border-green-300"
    elif avg_perf < 50:
        return "WORKSTATION RECOMMENDED", "#dc2626", "from-red-50 via-red-50 to-red-100 border-red-300"
    elif avg_perf < 85:
        if trend_status == "Improving":
            return "ADEQUATE PERFORMANCE", "#eab308", "from-yellow-50 via-yellow-50 to-yellow-100 border-yellow-300"
        else:
            return "REQUIRES MANUAL INSPECTION", "#eab308", "from-yellow-50 via-yellow-50 to-yellow-100 border-yellow-300"
    return "UNKNOWN", "#6b7280", "from-gray-50 via-gray-50 to-gray-100 border-gray-300"
