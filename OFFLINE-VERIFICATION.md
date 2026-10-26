# Offline verification boundary

Import nested System Doctor 0.1.0 check findings correctly; reject non-object JSON without crashing.

## Reproduce

`python -m pytest`

The versioned report is a synthetic fixture matching public DoctorReport fields. Existing bounded apply/recheck/rollback tests operate only on synthetic snapshots; no live runtime modification.

## Rollback

Review the commit diff and use a new checkout of the pre-change commit for source rollback. Keep user data and live installations untouched. A source rollback is not permission to restore unsafe network exposure or bypass approval.
