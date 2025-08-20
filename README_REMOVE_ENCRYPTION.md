### Removing application-level encryption (keeping data on PythonAnywhere)

1. Backup and export decrypted data

```bash
# Ensure FERNET_SECRET_KEY is present in env so export can decrypt
export FERNET_SECRET_KEY="<your-prod-key>"
python3 export_plaintext_data.py
```

This writes a JSON file in `backups/` with fully decrypted content for Patients, Treatments, Users, etc.

2. Migrate database values to plaintext

```bash
# Turn off encryption behavior and rewrite values as plaintext
export DISABLE_ENCRYPTION=true
python3 migrate_to_plaintext.py
```

This reads via properties (auto-decrypt) and stores plaintext back into the same underscore-backed columns.

3. Run the app with encryption disabled

- Ensure env var `DISABLE_ENCRYPTION=true` in PythonAnywhere.
- `FERNET_SECRET_KEY` can be removed from the environment once all data is plaintext and integrations work.

4. Optional schema cleanup (future)

- If desired, rename underscored columns (e.g., `_name`) to normal names by creating Alembic migrations. Not required for performance; properties already bypass encryption.

5. Rollback

- You can re-enable encryption later by setting `DISABLE_ENCRYPTION=false` and ensuring `FERNET_SECRET_KEY` is set.
