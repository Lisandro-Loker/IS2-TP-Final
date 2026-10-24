# Trabajo Práctico Final Integrador - Ingeniería de Software II (UADER-FCyT)

## Naturaleza del Proyecto
Sistema cliente-servidor en Python para la provisión y gestión de datos corporativos centralizados (`CorporateData`) y auditoría de accesos (`CorporateLog`) sobre AWS DynamoDB, implementando los patrones de diseño **Singleton**, **Proxy** y **Observer**.

## Componentes Principales
* `singletonproxyobserver.py`: Servidor de aplicaciones TCP que implementa los patrones Singleton (acceso a `CorporateData` y `CorporateLog`), Proxy (gestión de operaciones `get`, `set`, `list`) y Observer (notificación a clientes suscriptos).
* `singletonclient.py`: Cliente TCP para consultar (`get`, `list`) o modificar (`set`) datos corporativos mediante archivos JSON.
* `observerclient.py`: Cliente suscriptor TCP que mantiene una conexión activa para recibir notificaciones en tiempo real ante modificaciones en `CorporateData`.

## Versión y Licencia
* **Versión:** 1.0.0 (Build 1)
* **Licencia:** MIT