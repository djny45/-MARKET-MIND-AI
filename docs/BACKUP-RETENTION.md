# Backup retention and off-host protection

## Retention policy

The default retention target is the **14 newest timestamped SQLite backups** in a dedicated backup directory. Backups use the exact UTC filename format:

`market_mind-YYYYMMDDTHHMMSSZ.db`

The retention utility is `backend/backup_retention.py`. It considers only exact matching names, sorts by the UTC timestamp embedded in the filename, and leaves unrelated files untouched. A matching symlink or non-regular file causes the operation to fail closed. The backup directory itself must not be a symlink.

Dry-run is the default and performs no deletion:

```bash
python backend/backup_retention.py ./backups --keep 14
```

Review the JSON list of retained and expired files. Apply deletion only after reviewing that output:

```bash
python backend/backup_retention.py ./backups --keep 14 --apply
```

Use a dedicated directory containing only backups for this application. Keep at least 14 known-good copies; do not run retention against the live SQLite data directory, an arbitrary directory, or a directory containing the only recovery copy. Retention is a local cleanup policy, not a backup strategy: it does not create backups, encrypt files, upload them, or guarantee geographic separation.

## Encrypted off-host copy

The repository backup drill creates and verifies a plaintext SQLite backup. **Do not upload that plaintext file to general-purpose cloud storage.** Before off-host transfer, encrypt it with an organization-approved, authenticated file-encryption tool (for example, age) using a recipient public key whose corresponding private identity is held separately from the host. Do not store the decryption identity, passphrase, or cloud credentials beside the backup or in this repository.

Example workflow when `age` is installed and a recipient public key has been provisioned:

```bash
age -r "$BACKUP_AGE_RECIPIENT" -o "$BACKUP_FILE.age" "$BACKUP_FILE"
age -d -i "$BACKUP_AGE_IDENTITY" -o /tmp/market_mind-restore-check.db "$BACKUP_FILE.age"
sha256sum "$BACKUP_FILE.age" /tmp/market_mind-restore-check.db
```

Set `BACKUP_AGE_RECIPIENT` from the approved public recipient key and keep `BACKUP_AGE_IDENTITY` only on a separately controlled recovery workstation or secret manager. Verify the decrypted database using the repository restore utility against a disposable destination before accepting the encrypted object. Transfer only the `.age` artifact to the approved off-host storage location. Confirm upload completion, object versioning/immutability where available, access restrictions, and a checksum recorded independently of the upload channel.

This is a documented operator procedure, **not an implemented automated uploader or key-management integration**. The project has not yet verified that `age` is installed on the target VPS, that the recipient/identity pair is managed correctly, or that an off-host restore succeeds. Do not mark encrypted off-host backup acceptance complete until the actual operator drill records those results.

## Recovery acceptance record

For each target VPS, record (without recording secrets):

- Host and deployment identifier.
- Backup UTC timestamp, file size, and SHA-256 digest.
- Encryption tool/version and recipient-key fingerprint (never private key material).
- Off-host storage provider/bucket/object identifier and upload verification.
- Restore host, restore UTC timestamp, integrity-check result, and application smoke-test result.
- Recovery time and data-loss window observed.
- Operator and independent reviewer sign-off.

A successful GitHub Actions run or local unit test is not evidence of a VPS recovery. Complete the restore into an isolated target first; validate SQLite integrity, schema, API readiness, authenticated browser login, CSRF-protected request, and read-only terminal page; then document migration rollback separately. Never overwrite the only production database during a drill.
