# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo.

## [1.0.0] - Build 1 - 2026-10-20
### Agregado
- Creación del esqueleto inicial del proyecto basado en Cookiecutter.
- Configuración de entorno virtual (`venv`) y dependencias en `requirements.txt`.
- Verificación de conectividad y pre-requisitos con AWS DynamoDB (`CorporateData` y `CorporateLog`).
- Inicialización de archivos documentales (`README.md`, `CONTEXT.md`, `LICENSE`, `VERSION`, `BUILD`).

# Changelog

Registro de cambios del proyecto IS2 TP Final.

## [1.0.0] - Build 2 - 2026-10-23
### Agregado
- Implementación del módulo `patterns.py` con los patrones `CorporateDataSingleton`, `CorporateLogSingleton`, `ObserverManager` y `CorporateDataProxy`.
- Desarrollo del servidor TCP `singletonproxyobserver.py` y los clientes `singletonclient.py` y `observerclient.py`.
- Suite de pruebas unitarias `test_tpfi.py` con cobertura superior al 88% en Pytest.
- Script de pruebas de aceptación `acceptance_test.py` (Validación y Verificación) contra AWS DynamoDB.
- Generación automática de documentación técnica HTML mediante `pdoc`.

## [1.0.0] - Build 1 - 2026-10-21
### Agregado
- Esqueleto inicial del proyecto generado con Cookiecutter (`is2_tp_final`).
- Verificación de entorno virtual y conexión a tablas `CorporateData` y `CorporateLog` en AWS DynamoDB.
- Archivos de control de configuración: `README.md`, `CONTEXT.md`, `requirements.txt`, `VERSION` y `BUILD`.

