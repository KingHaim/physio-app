# Configuración de Google Calendar para PhysioTracker

Esta guía te ayudará a configurar la integración con Google Calendar en tu aplicación PhysioTracker.

## Funcionalidades

La integración con Google Calendar incluye:

- **Autenticación OAuth2 segura** - Sin necesidad de copiar/pegar tokens manualmente
- **Sincronización bidireccional** - Lee eventos de Google Calendar y puede crear nuevos eventos
- **Matching inteligente** - Asocia automáticamente eventos con pacientes existentes
- **Encriptación de tokens** - Todos los tokens se almacenan encriptados en la base de datos
- **Compatibilidad con Calendly** - Funciona en paralelo con la integración existente de Calendly

## Configuración paso a paso

### Paso 1: Configurar Google Cloud Console

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Habilita la **Google Calendar API**:
   - Ve a "APIs & Services" > "Library"
   - Busca "Google Calendar API"
   - Haz clic en "Enable"

### Paso 2: Configurar OAuth2

1. Ve a "APIs & Services" > "OAuth consent screen"
2. Selecciona "External" como tipo de usuario
3. Completa la información requerida:
   - Nombre de la aplicación: "PhysioTracker"
   - Email de soporte: tu email
   - Logo (opcional)
4. En "Scopes", agrega:
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/calendar.events`
5. En "Test users", agrega tu email y los de otros usuarios que necesiten acceso

### Paso 3: Crear credenciales OAuth2

1. Ve a "APIs & Services" > "Credentials"
2. Haz clic en "Create Credentials" > "OAuth client ID"
3. Selecciona "Web application"
4. Configura:

   - **Nombre**: PhysioTracker Google Calendar
   - **Authorized redirect URIs**:
     - Para desarrollo: `http://localhost:5000/google-calendar/callback`
     - Para producción: `https://tudominio.com/google-calendar/callback`

5. Descarga las credenciales JSON o copia el Client ID y Client Secret

### Paso 4: Configurar variables de entorno

#### Para desarrollo local:

Agrega al archivo `.env`:

```bash
# Google Calendar Integration
GOOGLE_CLIENT_ID=tu_client_id_aqui
GOOGLE_CLIENT_SECRET=tu_client_secret_aqui
GOOGLE_REDIRECT_URI=http://localhost:5000/google-calendar/callback
```

#### Para producción (Supabase/PythonAnywhere):

Configura las variables de entorno en tu plataforma:

```bash
GOOGLE_CLIENT_ID=tu_client_id_aqui
GOOGLE_CLIENT_SECRET=tu_client_secret_aqui
GOOGLE_REDIRECT_URI=https://tudominio.com/google-calendar/callback
```

### Paso 5: Aplicar migración de base de datos

#### Para desarrollo (SQLite):

```bash
python3 -m flask db upgrade
```

#### Para producción (Supabase):

La migración se aplicará automáticamente al hacer deploy. Si necesitas aplicarla manualmente:

```sql
-- Agregar campos a la tabla user
ALTER TABLE "user" ADD COLUMN google_calendar_token_encrypted TEXT;
ALTER TABLE "user" ADD COLUMN google_calendar_refresh_token_encrypted TEXT;
ALTER TABLE "user" ADD COLUMN google_calendar_enabled BOOLEAN DEFAULT false;
ALTER TABLE "user" ADD COLUMN google_calendar_primary_calendar_id VARCHAR(255);
ALTER TABLE "user" ADD COLUMN google_calendar_last_sync TIMESTAMP;

-- Agregar campos a la tabla treatment
ALTER TABLE treatment ADD COLUMN google_calendar_event_id VARCHAR(255);
ALTER TABLE treatment ADD COLUMN google_calendar_event_summary VARCHAR(255);

-- Crear índice para mejor rendimiento
CREATE INDEX idx_treatment_google_calendar_event_id ON treatment (google_calendar_event_id);
```

### Paso 6: Instalar dependencias

Asegúrate de que las siguientes dependencias estén instaladas:

```bash
pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2
```

## Uso de la integración

### Conectar Google Calendar

1. Ve a "Configuraciones de Usuario" > pestaña "Integraciones API"
2. Marca la casilla "Habilitar integración de Google Calendar"
3. Haz clic en "Conectar Google Calendar"
4. Autoriza el acceso en la ventana de Google que se abre
5. Serás redirigido de vuelta a la aplicación

### Sincronizar eventos

Una vez conectado, puedes:

- **Sincronización automática**: Los eventos se sincronizan automáticamente al conectar
- **Sincronización manual**: Haz clic en "Sincronizar Eventos" en cualquier momento
- **Crear eventos**: La aplicación puede crear eventos directamente en tu Google Calendar

### Desconectar

Para desconectar Google Calendar:

1. Ve a "Configuraciones de Usuario" > pestaña "Integraciones API"
2. Haz clic en "Desconectar" en la sección de Google Calendar
3. Opcionalmente, desmarca la casilla de integración

## Funcionalidades técnicas

### Matching de pacientes

El sistema intenta asociar eventos de Google Calendar con pacientes existentes usando:

1. **Emails de asistentes**: Busca coincidencias con emails de pacientes
2. **Nombres en el título**: Busca nombres de pacientes en el título del evento
3. **Descripción del evento**: Analiza la descripción para encontrar referencias a pacientes

### Sincronización bidireccional

- **Desde Google Calendar**: Importa eventos como tratamientos
- **Hacia Google Calendar**: Puede crear eventos cuando se programan citas

### Seguridad

- **Tokens encriptados**: Todos los tokens OAuth2 se almacenan encriptados
- **Refresh automático**: Los tokens se renuevan automáticamente cuando expiran
- **Scopes mínimos**: Solo solicita permisos necesarios para el calendario

## Solución de problemas

### Error: "Module not found 'googleapiclient'"

```bash
pip install google-api-python-client
```

### Error: "OAuth client not found"

Verifica que:

- Las variables de entorno estén configuradas correctamente
- La URI de redirección coincida exactamente con la configurada en Google Cloud Console

### Error: "Access denied"

Asegúrate de que:

- Tu email esté en la lista de usuarios de prueba (si la app no está verificada)
- Los scopes estén configurados correctamente en la consola de OAuth

### No se sincronizan eventos

Verifica que:

- La conexión esté activa (estado "Connected")
- Los eventos tengan fechas válidas
- Los calendarios sean accesibles

## API Endpoints disponibles

- `GET /google-calendar/connect` - Iniciar flujo OAuth2
- `GET /google-calendar/callback` - Callback OAuth2
- `POST /google-calendar/sync` - Sincronizar eventos manualmente
- `POST /google-calendar/create-event` - Crear evento
- `GET /google-calendar/status` - Estado de la conexión
- `GET /google-calendar/disconnect` - Desconectar integración

## Consideraciones de producción

1. **Rate limiting**: Google Calendar API tiene límites de uso - implementa caching si es necesario
2. **Monitoreo**: Configura logs para rastrear errores de sincronización
3. **Backup**: Asegúrate de hacer backup de los tokens encriptados
4. **Verificación de la app**: Para uso público, considera verificar tu aplicación con Google

## Compatibilidad

Esta integración es compatible con:

- ✅ La integración existente de Calendly
- ✅ Múltiples calendarios de Google
- ✅ Eventos recurrentes
- ✅ Zonas horarias diferentes
- ✅ SQLite (desarrollo) y PostgreSQL (producción)

La aplicación puede usar ambas integraciones (Calendly y Google Calendar) simultáneamente.
