# Fix: log_data_event Audit Logging Errors in Donations

## Issues Fixed

### Issue 1: Missing user_id Parameter
**Error:** `TypeError: log_data_event() missing 1 required positional argument: 'user_id'`

### Issue 2: String Instead of Enum Values  
**Error:** `AttributeError: 'str' object has no attribute 'value'`

**Affected File:** `app/features/donations.py`

**Root Cause:** 
1. The `log_data_event()` function requires a `user_id` parameter, but calls were missing it
2. The function expects `AuditAction` and `AuditOutcome` enum values, not string literals

---

## Function Signature

**File:** `app/security/audit_logger.py` (Line 304)

```python
def log_data_event(
    action: AuditAction,           # Must be enum, not string
    user_id: int,                  # Required parameter
    entity_type: str,
    entity_id: Optional[Union[int, str]] = None,
    details: Optional[dict] = None,
    outcome: AuditOutcome = AuditOutcome.SUCCESS  # Must be enum, not string
) -> None:
```

---

## Changes Required

### Change 0: Update Import Statement (Line ~16)

**Before:**
```python
from app.security.audit_logger import log_data_event
```

**After:**
```python
from app.security.audit_logger import log_data_event, AuditAction, AuditOutcome
```

---

### Change 1: Create Donation (Line ~531)

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
    action=AuditAction.CREATE,           # Changed from string to enum
    user_id=current_user.user_id,        # Added missing parameter
    entity_type='donation',
    entity_id=donation.donation_id,
    outcome=AuditOutcome.SUCCESS,        # Changed from string to enum
    details={
        'item_count': len(item_data),
        'document_count': document_count,
        'total_value': str(tot_item_cost_value),
        'donor_id': donation.donor_id
    }
)
```

---

### Change 2: Update Donation (Line ~882)

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
    action=AuditAction.UPDATE,           # Changed from string to enum
    user_id=current_user.user_id,        # Added missing parameter
    entity_type='donation',
    entity_id=donation.donation_id,
    outcome=AuditOutcome.SUCCESS,        # Changed from string to enum
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
    action=AuditAction.VERIFY,           # Changed from string to enum
    user_id=current_user.user_id,        # Added missing parameter
    entity_type='donation',
    entity_id=donation_id,
    outcome=AuditOutcome.SUCCESS,        # Changed from string to enum
    details={
        'item_count': len(item_data),
        'total_value': str(tot_item_cost_value),
        'previous_status': 'E',
        'new_status': 'V'
    }
)
```

---

## Summary of All Changes

| Location | Line (approx) | Changes |
|----------|---------------|---------|
| Import statement | ~16 | Add `AuditAction, AuditOutcome` to import |
| Create Donation | ~531 | Add `user_id`, use enum values |
| Update Donation | ~882 | Add `user_id`, use enum values |
| Verify Donation | ~1667 | Add `user_id`, use enum values |

---

## Available Enum Values

### AuditAction (from `app/security/audit_logger.py`)
```python
AuditAction.CREATE
AuditAction.READ
AuditAction.UPDATE
AuditAction.DELETE
AuditAction.VERIFY
AuditAction.APPROVE
AuditAction.REJECT
AuditAction.DISPATCH
AuditAction.CANCEL
AuditAction.SUBMIT
AuditAction.EXPORT
AuditAction.IMPORT
```

### AuditOutcome
```python
AuditOutcome.SUCCESS
AuditOutcome.FAILURE
AuditOutcome.DENIED
AuditOutcome.ERROR
```

---

## Verification

After applying these changes, restart the Flask application and test:
1. Create a new donation
2. Edit an existing donation
3. Verify a donation

All operations should complete without errors and audit logs should be properly recorded.
