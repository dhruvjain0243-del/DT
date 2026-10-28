This folder contains an encrypted backup of local ParkWise configuration, databases,
database backups, logs, and built web assets. Project documents and screenshots are
committed normally. Reinstallable dependencies, Python environments, and caches are
excluded.

Encryption: AES-256-GCM, authenticated format `PARKWISE-AESGCM-1`.
The recovery key is **not** committed. Keep a separate secure copy of:

`outputs/parkwise-backup-recovery.key`

To restore on a computer with that key in the same location:

```powershell
python -m pip install cryptography
python scripts/private_backup.py --restore
```

This writes `outputs/parkwise-private-restored.zip`. Extract it into a separate
folder and review files before replacing any current configuration or data.
Without the recovery key, the encrypted backup cannot be restored.

To refresh the encrypted backup, run `python scripts/private_backup.py`.
