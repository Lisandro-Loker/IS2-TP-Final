# Registro de Prompts de IA (CONTEXT.md)

Documento de trazabilidad de los prompts utilizados durante el desarrollo del Trabajo Práctico Final Integrador de Ingeniería de Software II.

## Fase 0: Diagnóstico y Pre-requisitos AWS
1. **Prompt:** Solicitud de análisis de consignas del TPFI y de los scripts auxiliares (`IS2_TPFI_demo.py`, `IS2_TPFI_insert.py`, `IS2_TPFI_test.py`, `IS2-TPFI-uuid.py`) provistos por la cátedra.
2. **Prompt:** Guía paso a paso para configurar el ambiente virtual (`venv`), `aws configure` y resolución de excepción `UnrecognizedClientException` en las pruebas iniciales de conexión con DynamoDB.

## Fase 2 - Paso 2.1: Esqueleto Cookiecutter y Archivos Base
3. **Prompt:** Explicación del funcionamiento e instalación de Cookiecutter y generación de la estructura base del proyecto junto con las plantillas iniciales de `README.md`, `CHANGELOG.md`, `CONTEXT.md`, `requirements.txt`, `VERSION` y `BUILD`.

## Fase 2 - Paso 2.2: Clases de Patrones Singleton, Proxy y Observer
4. **Prompt:** Desarrollo modular con programación orientada a objetos (OOP) del archivo `patterns.py` implementando dos patrones Singleton independientes (`CorporateDataSingleton` y `CorporateLogSingleton`), el patrón Observer (`ObserverManager`) y el patrón Proxy (`CorporateDataProxy`), junto con la resolución de observaciones de formato y tipado en `ruff`, `black`, `flake8` (PEP8), `pydocstyle` (PEP257), `mypy`, `pyright` y `bandit`.

## Fase 2 - Paso 2.3: Servidor de Aplicaciones (singletonproxyobserver.py)
5. **Prompt:** Implementación del servidor TCP `singletonproxyobserver.py` con soporte de argumentos `-p=port` y `-v` (`logging` por salida estándar), gestión de acciones `subscribe`, `get`, `set` y `list`, control de error ante intento de levantar dos veces el servidor y validación estática y de seguridad sin errores.

## Fase 2 - Paso 2.4: Cliente Operativo (singletonclient.py)
6. **Prompt:** Implementación del cliente `singletonclient.py` para lectura de requerimientos JSON (`-i=input.json`), salida estándar o por archivo (`-o=output.json`), validación de datos mínimos necesarios, manejo de excepción ante servidor caído y ajuste de docstrings y longitud de línea para `flake8` y `pydocstyle`.

## Fase 2 - Paso 2.5: Cliente Suscriptor (observerclient.py)
7. **Prompt:** Implementación del cliente suscriptor `observerclient.py` con armado automático de solicitud `subscribe` incluyendo el `UUID` local de CPU, escucha continua de notificaciones en socket TCP abierto y reconexión automática periódica cada 30 segundos ante caídas del servidor.

## Fase 3 - Paso 3.1: Pruebas Unitarias y de Patrones con Pytest
8. **Prompt:** Creación de la suite de tests unitarios `test_tpfi.py` para comprobar la identidad de instancias Singleton, la gestión de suscripciones en Observer, el ruteo en Proxy y el manejo de errores en clientes y servidor, superando el 85% de cobertura exigido con `pytest` y `pytest-cov` (88.40% alcanzado) y configurando el intérprete del entorno virtual en VS Code.

## Fase 3 - Paso 3.2: Pruebas de Aceptación V&V en Vivo contra AWS
9. **Prompt:** Desarrollo y ajuste del script automatizado de aceptación `acceptance_test.py` cubriendo los 5 escenarios de Validación y Verificación (camino feliz con auditoría en `CorporateLog`, argumentos malformados, datos mínimos faltantes, doble instancia del servidor y servidor caído), incorporando paginación de lectura en DynamoDB (`LastEvaluatedKey`), cierre limpio del socket en Windows y filtrado de logs de `boto3`, `botocore` y `urllib3`.

## Fase 4 - Paso 4.1 y 4.2: Documentación Automática y CI/CD en GitHub
10. **Prompt:** Generación automática de documentación técnica HTML mediante `pdoc`, actualización de archivos documentales (`CHANGELOG.md`, `CONTEXT.md` y `BUILD`) y configuración del workflow automatizado de Integración Continua (CI/CD) en GitHub Actions.