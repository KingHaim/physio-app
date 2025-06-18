from sqlalchemy import create_engine, MetaData
import pandas as pd

# Configura las URLs de conexión
sqlite_url = 'sqlite:///instance/physio.db'
supabase_url = 'postgresql://postgres.cyjtlvrektrkxnuebvuq:FR29marb08650421@aws-0-eu-central-1.pooler.supabase.com:5432/postgres'

# Crea motores de conexión
sqlite_engine = create_engine(sqlite_url)
supabase_engine = create_engine(supabase_url)

# Tablas que se pueden excluir (por ejemplo, alembic_version)
tablas_excluidas = ['alembic_version']

# Extrae las tablas de SQLite
sqlite_metadata = MetaData()
sqlite_metadata.reflect(bind=sqlite_engine)
tablas_sqlite = list(sqlite_metadata.tables.keys())
print("📦 Tablas encontradas en SQLite:", tablas_sqlite)

# Migra cada tabla
for table_name in tablas_sqlite:
    if table_name in tablas_excluidas:
        print(f"⏭️  Saltando tabla excluida: {table_name}")
        continue

    try:
        df = pd.read_sql_table(table_name, sqlite_engine)
        if df.empty:
            print(f"⚠️  Tabla {table_name} está vacía. Nada que migrar.")
            continue

        print(f"📤 Migrando {table_name} ({len(df)} filas)...")
        df.to_sql(table_name, supabase_engine, if_exists='append', index=False)
        print(f"✅ {table_name} migrada exitosamente.\n")
    except Exception as e:
        print(f"❌ Error al migrar {table_name}: {e}\n")

print("🎉 ¡Migración completada con éxito!")
