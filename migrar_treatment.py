from sqlalchemy import create_engine
import pandas as pd
import json

sqlite_url = 'sqlite:////Users/haimganancia/Desktop/PROYECTOS/physio-app/instance/physio.db'
sqlite_engine = create_engine(sqlite_url)

supabase_url = 'postgresql://postgres.cyjtlvrektrkxnuebvuq:FR29marb08650421@aws-0-eu-central-1.pooler.supabase.com:5432/postgres'
supabase_engine = create_engine(supabase_url)

print("📥 Extrayendo tratamientos desde SQLite...")
df = pd.read_sql_table('treatment', sqlite_engine)
print(f"📊 Se encontraron {len(df)} tratamientos.")

# Limpieza segura del campo JSON
if 'evaluation_data' in df.columns:
    def to_valid_json(x):
        if isinstance(x, dict):
            return json.dumps(x)
        if isinstance(x, str):
            try:
                parsed = eval(x)
                if isinstance(parsed, (dict, list)):
                    return json.dumps(parsed)
            except:
                return None
        return None
    df['evaluation_data'] = df['evaluation_data'].apply(to_valid_json)

# Campos sensibles al truncado (todos convertidos a str primero)
truncar = {
    'treatment_type': 50,
    'notes': 50,
    'assessment': 50,
    'provider': 50,
    'location': 50,
    'calendly_invitee_uri': 255  # <-- Aumentamos este a 255
}
for col, limit in truncar.items():
    if col in df.columns:
        df[col] = df[col].astype(str).fillna('').str.slice(0, limit)

# Migración
try:
    print("🚀 Migrando a Supabase...")
    df.to_sql('treatment', supabase_engine, if_exists='append', index=False)
    print("🎉 ¡Migración de tratamientos completada!")
except Exception as e:
    print("❌ Error durante la migración:")
    print(e)
