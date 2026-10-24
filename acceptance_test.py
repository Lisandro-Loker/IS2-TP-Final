"""Script de pruebas de aceptación automatizadas (V&V) para el TPFI IS2."""

import json
import logging
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import observerclient
import singletonclient
import singletonproxyobserver
from patterns import CorporateDataSingleton, CorporateLogSingleton

TEST_PORT = 8085
CLOSED_PORT = 8099
TARGET_ID = "UADER-FCYT-IS2"


def check_case(condition: bool, message: str) -> None:
    """Comprueba una condición de aceptación sin alertas B101 en Bandit."""
    if not condition:
        raise RuntimeError(f"Fallo en prueba de aceptación: {message}")


def fetch_session_logs(session_id: str) -> list[str]:
    """Consulta en AWS DynamoDB las acciones auditadas para la sesión."""
    log_singleton = CorporateLogSingleton()
    actions: list[str] = []
    scan_kwargs: dict[str, Any] = {}

    while True:
        response = log_singleton.table.scan(**scan_kwargs)
        items: list[dict[str, Any]] = response.get("Items", [])
        for item in items:
            if str(item.get("sessionid", "")) == session_id:
                actions.append(str(item.get("action", "")))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    return actions


def run_happy_path(
    server: singletonproxyobserver.SingletonProxyObserverServer,
    tmp_dir: Path,
) -> None:
    """Ejecuta el camino feliz de subscribe, get, set y list en AWS."""
    logging.info("=== CASO 1: CAMINO FELIZ (SUBSCRIBE, GET, SET, LIST) ===")
    obs_output = tmp_dir / "observer_out.json"
    obs_client = observerclient.ObserverClient(
        host="127.0.0.1",
        port=TEST_PORT,
        output_file=str(obs_output),
        retry_interval=1,
    )
    obs_thread = threading.Thread(
        target=obs_client.run,
        kwargs={"max_messages": 1, "max_retries": 2},
        daemon=True,
    )
    obs_thread.start()
    time.sleep(0.5)

    cpu_uuid = str(uuid.getnode())

    get_in = tmp_dir / "get_in.json"
    get_out = tmp_dir / "get_out.json"
    get_in.write_text(
        json.dumps({"UUID": cpu_uuid, "ID": TARGET_ID, "ACTION": "get"}),
        encoding="utf-8",
    )
    rc_get = singletonclient.main(
        [f"-i={get_in}", f"-o={get_out}", f"-p={TEST_PORT}", "-v"]
    )
    check_case(rc_get == 0, "Acción GET debe retornar código 0.")

    set_in = tmp_dir / "set_in.json"
    set_out = tmp_dir / "set_out.json"
    set_payload = {
        "UUID": cpu_uuid,
        "ID": TARGET_ID,
        "ACTION": "set",
        "cp": "3260",
        "CUIT": "30-70925411-8",
        "domicilio": "25 de Mayo 385-1P",
        "idreq": "473",
        "idSeq": "1146",
        "localidad": "Concepción del Uruguay",
        "provincia": "Entre Rios",
        "sede": "FCyT",
        "seqID": "23",
        "telefono": "03442 43-1442",
        "web": "http://www.uader.edu.ar",
    }
    set_in.write_text(json.dumps(set_payload), encoding="utf-8")
    rc_set = singletonclient.main(
        [f"-i={set_in}", f"-o={set_out}", f"-p={TEST_PORT}", "-v"]
    )
    check_case(rc_set == 0, "Acción SET debe retornar código 0.")

    obs_thread.join(timeout=5.0)
    check_case(
        obs_output.is_file(),
        "ObserverClient debe guardar la notificación recibida.",
    )

    list_in = tmp_dir / "list_in.json"
    list_out = tmp_dir / "list_out.json"
    list_in.write_text(
        json.dumps({"UUID": cpu_uuid, "ACTION": "list"}),
        encoding="utf-8",
    )
    rc_list = singletonclient.main(
        [f"-i={list_in}", f"-o={list_out}", f"-p={TEST_PORT}", "-v"]
    )
    check_case(rc_list == 0, "Acción LIST debe retornar código 0.")

    db_item = CorporateDataSingleton().get_record(TARGET_ID)
    check_case(
        db_item.get("sede") == "FCyT",
        "CorporateData debe contener los datos actualizados.",
    )

    logged_actions = fetch_session_logs(server.proxy.session_id)
    for expected in ("subscribe", "get", "set", "list"):
        check_case(
            expected in logged_actions,
            f"La acción '{expected}' debe figurar en CorporateLog.",
        )
    logging.info(
        "[OK] CASO 1 SUPERADO. Auditoría en CorporateLog (sesión %s): %s",
        server.proxy.session_id,
        logged_actions,
    )


def run_malformed_args_cases() -> None:
    """Comprueba el rechazo de argumentos malformados en los 3 programas."""
    logging.info("=== CASO 2: PRUEBA DE ARGUMENTOS MALFORMADOS ===")
    rc_srv = singletonproxyobserver.main(["-p=invalido"])
    check_case(rc_srv == 2, "Servidor debe rechazar puerto inválido.")

    rc_cli = singletonclient.main(["--argumento-invalido"])
    check_case(rc_cli == 2, "SingletonClient debe rechazar flag inválido.")

    rc_obs = observerclient.main(["-p=99999"])
    check_case(rc_obs == 2, "ObserverClient debe rechazar puerto inválido.")
    logging.info("[OK] CASO 2 SUPERADO: Argumentos malformados rechazados.")


def run_missing_data_cases(tmp_dir: Path) -> None:
    """Comprueba el rechazo de requerimientos sin datos mínimos."""
    logging.info("=== CASO 3: PRUEBA DE DATOS MÍNIMOS FALTANTES ===")
    err_out = tmp_dir / "err_out.json"
    bad_json = tmp_dir / "missing_action.json"
    bad_json.write_text(
        json.dumps({"UUID": str(uuid.getnode())}),
        encoding="utf-8",
    )
    rc_no_act = singletonclient.main(
        [f"-i={bad_json}", f"-o={err_out}", f"-p={TEST_PORT}", "-v"]
    )
    check_case(rc_no_act == 1, "Debe fallar cuando falta ACTION.")

    no_id_json = tmp_dir / "missing_id.json"
    no_id_json.write_text(
        json.dumps({"UUID": str(uuid.getnode()), "ACTION": "get"}),
        encoding="utf-8",
    )
    rc_no_id = singletonclient.main(
        [f"-i={no_id_json}", f"-o={err_out}", f"-p={TEST_PORT}", "-v"]
    )
    check_case(rc_no_id == 1, "Debe fallar cuando falta ID en GET.")
    logging.info("[OK] CASO 3 SUPERADO: Datos faltantes detectados.")


def run_duplicate_server_case() -> None:
    """Comprueba el bloqueo al intentar levantar dos veces el servidor."""
    logging.info("=== CASO 4: PRUEBA DE DOBLE INSTANCIA DEL SERVIDOR ===")
    dup_server = singletonproxyobserver.SingletonProxyObserverServer(
        host="127.0.0.1",
        port=TEST_PORT,
    )
    failed_as_expected = False
    try:
        dup_server.start()
    except SystemExit as exc:
        failed_as_expected = exc.code == 1
    check_case(
        failed_as_expected,
        "El segundo servidor en el mismo puerto debe abortar con código 1.",
    )
    logging.info("[OK] CASO 4 SUPERADO: Segunda instancia bloqueada.")


def run_server_down_cases(tmp_dir: Path) -> None:
    """Comprueba el manejo en clientes cuando el servidor está caído."""
    logging.info(
        "=== CASO 5: SIMULACIÓN DE SERVIDOR CAÍDO (PUERTO %s) ===",
        CLOSED_PORT,
    )
    down_out = tmp_dir / "down_out.json"
    list_in = tmp_dir / "down_list.json"
    list_in.write_text(
        json.dumps({"UUID": str(uuid.getnode()), "ACTION": "list"}),
        encoding="utf-8",
    )
    rc_cli_down = singletonclient.main(
        [f"-i={list_in}", f"-o={down_out}", f"-p={CLOSED_PORT}", "-v"]
    )
    check_case(
        rc_cli_down == 1,
        "SingletonClient debe manejar el error de servidor caído.",
    )

    obs_down = observerclient.ObserverClient(
        host="127.0.0.1",
        port=CLOSED_PORT,
        retry_interval=1,
    )
    rc_obs_down = obs_down.run(max_retries=1)
    check_case(
        rc_obs_down == 1,
        "ObserverClient debe manejar el error de servidor caído.",
    )
    logging.info("[OK] CASO 5 SUPERADO: Clientes manejaron el servidor caído.")


def main() -> int:
    """Ejecuta la batería completa de pruebas de aceptación (V&V)."""
    singletonproxyobserver.configure_logging(True)
    logging.info("Iniciando batería de Validación y Verificación (V&V)...")

    server = singletonproxyobserver.SingletonProxyObserverServer(
        host="127.0.0.1",
        port=TEST_PORT,
    )
    srv_thread = threading.Thread(target=server.start, daemon=True)
    srv_thread.start()
    time.sleep(0.5)

    try:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp_dir = Path(tmp_name)
            run_happy_path(server, tmp_dir)
            run_malformed_args_cases()
            run_missing_data_cases(tmp_dir)
            run_duplicate_server_case()
            run_server_down_cases(tmp_dir)
    finally:
        server.stop()
        srv_thread.join(timeout=3.0)

    logging.info("TODAS LAS PRUEBAS DE ACEPTACIÓN FINALIZARON CON ÉXITO.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
