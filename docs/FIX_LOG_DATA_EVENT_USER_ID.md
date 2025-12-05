# Fix: log_data_event Missing user_id Parameter

## Issue
**Error:** `TypeError: log_data_event() missing 1 required positional argument: 'user_id'`

**Affected File:** `app/features/donations.py`

**Root Cause:** The `log_data_event()` function requires a `user_id` parameter as its second argument, but the donation module was calling it without this required parameter.

---

## Function Signature

**File:** `app/security/audit_logger.py` (Line 304)

```python
def log_data_event(
    action: AuditAction,
    user_id: int,              # <-- This parameter was missing in calls
    entity_type: str,
    entity_id: Optional[Union[int, str]] = None,
    details: Optional[dict] = None,
    outcome: AuditOutcome = AuditOutcome.SUCCESS
) -> None:
```

---

## Changes Required

### Change 1: Create Donation (Line ~528)

**Before:**
```python
log_data_event(
    action='CREATE',
    entity_type='donation',
    entity_id=donation.donation_id,
    outcome='SUCCESS',
    details={
        'item_count': len(item_data),
        'document_count': document_count,
        'total_value': str(tot_item_cost_value),
        'donor_id': donation.donor_id
    }
)
```

**After:**
```python
log_data_event(
    action='CREATE',
    user_id=current_user.user_id,    # <-- ADD THIS LINE
    entity_type='donation',
    entity_id=donation.donation_id,
    outcome='SUCCESS',
    details={
        'item_count': len(item_data),
        'document_count': document_count,
        'total_value': str(tot_item_cost_value),
        'donor_id': donation.donor_id
    }
)
```

---

### Change 2: Update Donation (Line ~880)

**Before:**
```python
log_data_event(
    action='UPDATE',
    entity_type='donation',
    entity_id=donation.donation_id,
    outcome='SUCCESS',
    details={
        'items_added': items_added_count,
        'items_removed': items_removed_count,
        'total_value': str(tot_item_cost_value)
    }
)
```

**After:**
```python
log_data_event(
    action='UPDATE',
    user_id=current_user.user_id,    # <-- ADD THIS LINE
    entity_type='donation',
    entity_id=donation.donation_id,
    outcome='SUCCESS',
    details={
        'items_added': items_added_count,
        'items_removed': items_removed_count,
        'total_value': str(tot_item_cost_value)
    }
)
```

---

### Change 3: Verify Donation (Line ~1667)

**Before:**
```python
log_data_event(
    action='VERIFY',
    entity_type='donation',
    entity_id=donation_id,
    outcome='SUCCESS',
    details={
        'item_count': len(item_data),
        'total_value': str(tot_item_cost_value),
        'previous_status': 'E',
        'new_status': 'V'
    }
)
```

**After:**
```python
log_data_event(
    action='VERIFY',
    user_id=current_user.user_id,    # <-- ADD THIS LINE
    entity_type='donation',
    entity_id=donation_id,
    outcome='SUCCESS',
    details={
        'item_count': len(item_data),
        'total_value': str(tot_item_cost_value),
        'previous_status': 'E',
        'new_status': 'V'
    }
)
```

---

## Summary

| Location | Function | Line (approx) | Change |
|----------|----------|---------------|--------|
| Create Donation | `create_donation()` | ~528 | Add `user_id=current_user.user_id` |
| Update Donation | `edit_donation()` | ~880 | Add `user_id=current_user.user_id` |
| Verify Donation | `verify_donation_detail()` | ~1667 | Add `user_id=current_user.user_id` |

---

## Verification

After applying these changes, restart the Flask application and test:
1. Create a new donation
2. Edit an existing donation
3. Verify a donation

All operations should complete without the `TypeError` and audit logs should be properly recorded.
