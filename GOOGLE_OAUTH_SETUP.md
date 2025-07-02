# Configuración de Google OAuth

## 📋 Resumen

Se ha agregado soporte para login con Google OAuth a tu aplicación de fisioterapia. Los usuarios ahora pueden:

- Registrarse usando su cuenta de Google
- Iniciar sesión con Google (sin necesidad de contraseña)
- Vincular cuentas existentes con Google

## 🔧 Configuración Requerida

### 1. Crear un Proyecto en Google Cloud Console

1. Ve a [Google Cloud Console](https://console.developers.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Habilita la **Google+ API**

### 2. Configurar OAuth 2.0

1. Ve a **APIs & Services** > **Credentials**
2. Haz clic en **Create Credentials** > **OAuth 2.0 Client ID**
3. Selecciona **Web application**
4. Configura las URLs autorizadas:

**Authorized JavaScript origins** (agregar TODAS estas):

- `http://localhost:5000` (desarrollo)
- `http://127.0.0.1:5000` (desarrollo)
- `https://www.trxcker.tech` (producción)
- `https://trxcker.tech` (producción)

**Authorized redirect URIs** (agregar TODAS estas):

- `http://localhost:5000/auth/callback/google` (desarrollo)
- `http://127.0.0.1:5000/auth/callback/google` (desarrollo)
- `https://www.trxcker.tech/auth/callback/google` (producción)
- `https://trxcker.tech/auth/callback/google` (producción)

### 3. Variables de Entorno

Agrega estas variables a tu archivo `.env`:

```bash
# Google OAuth configuration
GOOGLE_CLIENT_ID=tu-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=tu-client-secret
```

### 4. Instalar Dependencias

Las siguientes dependencias ya han sido agregadas a `requirements.txt`:

```bash
pip install Authlib google-auth google-auth-oauthlib google-auth-httplib2
```

### 5. Migración de Base de Datos

Se han agregado campos OAuth al modelo User:

- `oauth_provider` - El proveedor OAuth (google, facebook, etc.)
- `oauth_id` - ID único del usuario en el proveedor OAuth
- `avatar_url` - URL de la foto de perfil

Ejecuta la migración:

```bash
# Crear migración
python3 -c "from flask_migrate import migrate; from app import create_app, db; app = create_app(); app.app_context().push(); migrate(message='Add OAuth fields')"

# Aplicar migración
python3 -c "from flask_migrate import upgrade; from app import create_app; app = create_app(); app.app_context().push(); upgrade()"
```

## ✨ Funcionalidades Implementadas

### 🔐 Autenticación

- **Registro con Google**: Los nuevos usuarios pueden registrarse directamente con Google
- **Login con Google**: Los usuarios existentes pueden iniciar sesión con Google
- **Vinculación de cuentas**: Si un usuario tiene una cuenta con email/password y luego usa Google con el mismo email, las cuentas se vinculan automáticamente

### 🔒 Seguridad

- Verificación automática de email para usuarios de Google
- Tokens seguros usando el flujo OAuth 2.0
- Protección CSRF incluida

### 🎨 Interfaz de Usuario

- Botón "Continuar con Google" en la página de login
- Diseño integrado con el estilo existente de la aplicación
- Mensajes de éxito/error apropiados

## 🚀 Uso

### Para Usuarios Nuevos

1. Van a la página de login
2. Hacen clic en "Continuar con Google"
3. Autorizan la aplicación en Google
4. Se crea automáticamente su cuenta y son redirigidos al dashboard

### Para Usuarios Existentes

1. Si ya tienen cuenta con email/password, pueden vincularla usando Google con el mismo email
2. Una vez vinculada, pueden usar tanto email/password como Google para login

## 🔍 Archivos Modificados

- `requirements.txt` - Dependencias OAuth agregadas
- `config.py` - Configuración de Google OAuth
- `app/models.py` - Campos OAuth agregados al modelo User
- `app/routes/auth.py` - Rutas OAuth implementadas
- `app/__init__.py` - Inicialización OAuth
- `app/templates/auth/login.html` - Botón de Google agregado

## ⚠️ Notas Importantes

1. **Desarrollo vs Producción**: Asegúrate de configurar las URLs correctas en Google Console para cada entorno
2. **Seguridad**: Mantén el `GOOGLE_CLIENT_SECRET` seguro y nunca lo expongas en el código
3. **Emails únicos**: La aplicación maneja automáticamente la vinculación de cuentas basada en el email
4. **Foto de perfil**: Se guarda la URL del avatar de Google para uso futuro

## 🛠️ Solución de Problemas

### Error: "Google OAuth not configured"

- Verifica que `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` estén configurados en `.env`

### Error: "redirect_uri_mismatch"

- Verifica que la URL de callback esté configurada correctamente en Google Console

### Error de migración

- Puede que necesites arreglar las migraciones existentes antes de crear la nueva migración OAuth
