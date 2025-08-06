# 📅 Guía de Usuario: Google Calendar en PhysioTracker

## ¿Qué es la integración de Google Calendar?

La integración de Google Calendar te permite sincronizar automáticamente tus eventos de Google Calendar con PhysioTracker, creando tratamientos automáticamente y manteniendo todo organizado en un solo lugar.

## 🚀 Configuración súper simple

### Para Administradores (una sola vez)

1. **Ve a Configuraciones de Usuario → pestaña "API Integrations"**
2. **Busca la sección amarilla "Admin: Google Calendar Application Configuration"**
3. **Completa estos 3 campos:**
   - ✅ **Google Client ID**: De tu proyecto en Google Cloud
   - ✅ **Google Client Secret**: De tu proyecto en Google Cloud
   - ✅ **Redirect URI**: Se genera automáticamente
4. **Marca "Enable Google Calendar for all users"**
5. **Guarda la configuración**

### Para Usuarios Normales (súper fácil)

1. **Ve a Configuraciones de Usuario → pestaña "API Integrations"**
2. **Marca "Enable Google Calendar Integration"**
3. **Haz clic en "Connect Google Calendar"**
4. **Autoriza en la ventana de Google que se abre**
5. **¡Listo! Ya está conectado**

## 🎯 ¿Cómo usar la integración?

### Sincronización automática

- Al conectar por primera vez, se sincronizan automáticamente tus eventos
- Los eventos se convierten en tratamientos si coinciden con pacientes existentes

### Sincronización manual

- **Desde Configuraciones**: Botón "Sync Events" en la pestaña API Integrations
- **Desde el menú**: Link "Sync Google Calendar" en la barra lateral (si está conectado)

### ¿Qué eventos se sincronizan?

- ✅ Eventos de los últimos 30 días
- ✅ Eventos de los próximos 90 días
- ✅ Solo eventos que puedan asociarse con pacientes existentes

## 🔧 Configuración de Google Cloud (Solo para Administradores)

### Paso 1: Crear proyecto en Google Cloud

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Habilita la **Google Calendar API**

### Paso 2: Configurar OAuth

1. Ve a "APIs & Services" → "OAuth consent screen"
2. Configura la información de tu aplicación
3. Agrega los scopes de Google Calendar

### Paso 3: Crear credenciales

1. Ve a "APIs & Services" → "Credentials"
2. Crea "OAuth client ID" tipo "Web application"
3. Agrega la redirect URI que muestra PhysioTracker
4. Copia el Client ID y Client Secret a PhysioTracker

## ✨ Funcionalidades

### Para usuarios

- 🔄 **Sincronización en un clic**
- 🔒 **Totalmente seguro** (tokens encriptados)
- 📱 **Sin configuración técnica**
- 🤝 **Compatible con Calendly**

### Para administradores

- ⚙️ **Configuración centralizada**
- 👥 **Habilitar para todos los usuarios**
- 📊 **Control total de la integración**
- 🔧 **Fácil mantenimiento**

## 🚨 Solución de problemas

### "Google Calendar not configured by administrator"

- **Solución**: El administrador debe configurar las credenciales en la sección amarilla

### "Error connecting to Google Calendar"

- **Verificar**: Client ID y Client Secret correctos
- **Verificar**: Redirect URI coincide con Google Cloud Console

### "No se sincronizan eventos"

- **Verificar**: Eventos tienen fechas válidas
- **Verificar**: Eventos están en el rango de tiempo (último mes a próximos 3 meses)

## 🆚 Diferencias con Calendly

| Característica    | Calendly              | Google Calendar            |
| ----------------- | --------------------- | -------------------------- |
| **Configuración** | Manual por usuario    | Una vez por admin          |
| **Tipo**          | Plataforma de citas   | Calendario personal        |
| **Tokens**        | API Token manual      | OAuth2 automático          |
| **Usuarios**      | Cada uno se configura | Admin configura para todos |

## 💡 Consejos

1. **Para administradores**: Configura una sola vez y todos los usuarios podrán usar Google Calendar
2. **Para usuarios**: Solo necesitas hacer clic en "Connect" - ¡es súper fácil!
3. **Compatibilidad**: Puedes usar tanto Calendly como Google Calendar al mismo tiempo
4. **Seguridad**: Todos los tokens se almacenan encriptados automáticamente

## 🎉 ¡Eso es todo!

La integración está diseñada para ser **súper simple para usuarios** y **fácil de mantener para administradores**. Una vez configurada, funciona automáticamente y mantiene todo sincronizado.
