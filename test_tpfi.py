"""Suite de pruebas unitarias y de patrones para el TPFI IS2."""

import socket
import threading
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

import observerclient
import patterns
import singletonclient
import singletonproxyobserver


def check(condition: bool, message: str = "Fallo de validación") -> None:
    """Valida una condición booleana sin disparar alertas B101 en Bandit."""
    if not condition:
        raise AssertionError(message)


def make_client_error() -> ClientError:
    """Construye una excepción simulada de AWS Boto3 ClientError."""
    err_resp: Any = {"Error": {"Code": "500", "Message": "Simulated Error"}}
    return ClientError(err_resp, "TestOperation")


@pytest.fixture(autouse=True)
def reset_singletons(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Reinicia las instancias Singleton y simula DynamoDB en cada test."""
    patterns.CorporateLogSingleton._instance = None
    patterns.CorporateDataSingleton._instance = None
    mock_resource = MagicMock()
    monkeypatch.setattr(
        patterns.boto3, "resource", MagicMock(return_value=mock_resource)
    )
    return mock_resource


def test_sanitize_decimals() -> None:
    """Comprueba la conversión recursiva de objetos Decimal a string."""
    raw = {"a": Decimal("10"), "b": [Decimal("20.5"), "ok"]}
    res = patterns.sanitize_decimals(raw)
    check(res == {"a": "10", "b": ["20.5", "ok"]})


def test_singleton_pattern_identity() -> None:
    """Comprueba que Data y Log implementen el patrón Singleton."""
    log1 = patterns.CorporateLogSingleton()
    log2 = patterns.CorporateLogSingleton()
    data1 = patterns.CorporateDataSingleton()
    data2 = patterns.CorporateDataSingleton()
    check(log1 is log2)
    check(data1 is data2)


def test_corporate_log_singleton_actions() -> None:
    """Comprueba el registro exitoso y fallido en CorporateLogSingleton."""
    log_s = patterns.CorporateLogSingleton()
    log_s.table = MagicMock()
    check(log_s.log_action("cpu1", "sess1", "get", "UADER-FCyT-IS2") is True)
    check(log_s.log_action("cpu1", "sess1", "list") is True)

    log_s.table.put_item.side_effect = make_client_error()
    check(log_s.log_action("cpu1", "sess1", "get") is False)


def test_corporate_data_singleton_crud() -> None:
    """Comprueba las operaciones get, list y set en CorporateDataSingleton."""
    data_s = patterns.CorporateDataSingleton()
    data_s.table = MagicMock()

    data_s.table.get_item.return_value = {
        "Item": {"id": "ID1", "idreq": Decimal("5")}
    }
    check(data_s.get_record("ID1") == {"id": "ID1", "idreq": "5"})

    data_s.table.get_item.return_value = {}
    check("Error" in data_s.get_record("NO_EXISTE"))

    data_s.table.get_item.side_effect = make_client_error()
    check("Error" in data_s.get_record("ID1"))
    data_s.table.get_item.side_effect = None

    data_s.table.scan.return_value = {"Items": [{"id": "ID1"}]}
    check(data_s.list_records() == [{"id": "ID1"}])
    data_s.table.scan.side_effect = make_client_error()
    check("Error" in data_s.list_records())

    data_s.table.get_item.return_value = {"Item": {"id": "ID1", "cp": "3260"}}
    updated = data_s.set_record("ID1", {"sede": "FCyT"})
    check(updated["cp"] == "3260" and updated["sede"] == "FCyT")

    data_s.table.get_item.return_value = {}
    created = data_s.set_record("ID2", {"cp": "3260"})
    check(created["id"] == "ID2" and created["cp"] == "3260")
    check(created["sede"] == "")

    data_s.table.get_item.side_effect = make_client_error()
    check("Error" in data_s.set_record("ID1", {}))


def test_observer_pattern_manager() -> None:
    """Comprueba la suscripción, notificación y limpieza en ObserverManager."""
    obs = patterns.ObserverManager()
    good_sock = MagicMock()
    bad_sock = MagicMock()
    bad_sock.sendall.side_effect = OSError("Broken pipe")

    obs.subscribe(good_sock)
    obs.subscribe(good_sock)
    obs.subscribe(bad_sock)
    check(len(obs.subscribers) == 2)

    obs.notify_all({"id": "UADER"})
    good_sock.sendall.assert_called_once()
    check(bad_sock not in obs.subscribers)

    obs.unsubscribe(good_sock)
    check(len(obs.subscribers) == 0)


def test_proxy_pattern_requests() -> None:
    """Comprueba el procesamiento de acciones y validaciones en el Proxy."""
    proxy = patterns.CorporateDataProxy()
    proxy.log_singleton.table = MagicMock()
    proxy.data_singleton.table = MagicMock()

    res_err = proxy.process_request({"UUID": ""})
    check(isinstance(res_err, dict) and "Error" in res_err)

    sock_mock = MagicMock()
    res_sub = proxy.process_request(
        {"UUID": "u1", "ACTION": "subscribe"}, sock_mock
    )
    check(isinstance(res_sub, dict) and res_sub.get("status") == "OK")
    check(sock_mock in proxy.observer.subscribers)

    res_get_no_id = proxy.process_request({"UUID": "u1", "ACTION": "get"})
    check(isinstance(res_get_no_id, dict) and "Error" in res_get_no_id)

    proxy.data_singleton.table.get_item.return_value = {"Item": {"id": "X"}}
    res_get = proxy.process_request({"UUID": "u1", "ACTION": "get", "ID": "X"})
    check(res_get == {"id": "X"})

    proxy.data_singleton.table.scan.return_value = {"Items": [{"id": "X"}]}
    res_list = proxy.process_request({"UUID": "u1", "ACTION": "list"})
    check(res_list == [{"id": "X"}])

    res_set_no_id = proxy.process_request({"UUID": "u1", "ACTION": "set"})
    check(isinstance(res_set_no_id, dict) and "Error" in res_set_no_id)

    proxy.data_singleton.table.get_item.return_value = {}
    res_set = proxy.process_request(
        {"UUID": "u1", "ACTION": "set", "ID": "X", "cp": "3260"}
    )
    check(isinstance(res_set, dict) and res_set.get("cp") == "3260")
    sock_mock.sendall.assert_called_once()

    res_unk = proxy.process_request({"UUID": "u1", "ACTION": "delete"})
    check(isinstance(res_unk, dict) and "Error" in res_unk)


def test_server_args_and_payload() -> None:
    """Comprueba el parseo de argumentos y JSON del servidor."""
    singletonproxyobserver.configure_logging(True)
    port, verb = singletonproxyobserver.parse_args(["-p=9090", "-v"])
    check(port == 9090 and verb is True)

    for bad_arg in (["-p=abc"], ["-p=70000"], ["-x"]):
        with pytest.raises(ValueError):
            singletonproxyobserver.parse_args(bad_arg)

    raw_http = 'POST / HTTP/1.1\r\n\r\n{"ACTION": "list"}'
    check(
        singletonproxyobserver.extract_json_payload(raw_http)
        == {"ACTION": "list"}
    )
    with pytest.raises(ValueError):
        singletonproxyobserver.extract_json_payload("[1, 2]")


def test_server_handle_client_and_lifecycle() -> None:
    """Comprueba la atención de clientes y detección de doble servidor."""
    srv = singletonproxyobserver.SingletonProxyObserverServer(port=0)
    srv.proxy.log_singleton.table = MagicMock()
    srv.proxy.data_singleton.table = MagicMock()
    srv.proxy.data_singleton.table.scan.return_value = {"Items": []}

    empty_sock = MagicMock()
    empty_sock.recv.return_value = b""
    srv.handle_client(empty_sock, ("127.0.0.1", 1000))
    empty_sock.close.assert_called_once()

    bad_sock = MagicMock()
    bad_sock.recv.return_value = b"not_json"
    srv.handle_client(bad_sock, ("127.0.0.1", 1001))
    bad_sock.close.assert_called_once()

    sub_sock = MagicMock()
    sub_sock.recv.return_value = b'{"UUID": "1", "ACTION": "subscribe"}'
    srv.handle_client(sub_sock, ("127.0.0.1", 1002))
    check(sub_sock in srv.observer.subscribers)

    list_sock = MagicMock()
    list_sock.recv.return_value = b'{"UUID": "1", "ACTION": "list"}'
    srv.handle_client(list_sock, ("127.0.0.1", 1003))
    list_sock.close.assert_called_once()

    check(singletonproxyobserver.main(["-bad"]) == 2)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        used_port = occupied.getsockname()[1]
        occupied.listen(1)
        dup_srv = singletonproxyobserver.SingletonProxyObserverServer(
            host="127.0.0.1", port=used_port
        )
        with pytest.raises(SystemExit):
            dup_srv.start()

    srv.stop()


def test_singleton_client_full(tmp_path: Path) -> None:
    """Comprueba argumentos, archivos, red y errores en SingletonClient."""
    singletonclient.configure_logging(False)
    in_f, out_f, host, port, verb = singletonclient.parse_args(
        ["-i=in.json", "-o=out.json", "-s=localhost", "-p=8080", "-v"]
    )
    check(in_f == "in.json" and out_f == "out.json" and verb is True)
    check(host == "localhost" and port == 8080)

    for bad in (
        [],
        ["-i=a", "-s="],
        ["-i=a", "-p=x"],
        ["-i=a", "-p=0"],
        ["-i=a", "-o="],
        ["-bad"],
    ):
        with pytest.raises(ValueError):
            singletonclient.parse_args(bad)

    cli = singletonclient.SingletonClient(host="127.0.0.1", port=9)
    with pytest.raises(FileNotFoundError):
        cli.load_request(str(tmp_path / "nope.json"))

    arr_file = tmp_path / "arr.json"
    arr_file.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError):
        cli.load_request(str(arr_file))

    no_act = tmp_path / "no_act.json"
    no_act.write_text('{"UUID": "1"}', encoding="utf-8")
    with pytest.raises(ValueError):
        cli.load_request(str(no_act))

    no_id = tmp_path / "no_id.json"
    no_id.write_text('{"ACTION": "get"}', encoding="utf-8")
    with pytest.raises(ValueError):
        cli.load_request(str(no_id))

    valid_in = tmp_path / "valid.json"
    valid_in.write_text('{"ACTION": "list"}', encoding="utf-8")
    loaded = cli.load_request(str(valid_in))
    check("UUID" in loaded)

    down_res = cli.send_request(loaded)
    check("Error" in down_res)

    out_path = tmp_path / "out.json"
    cli.emit_output({"ok": True}, str(out_path))
    cli.emit_output({"ok": True}, None)
    check(out_path.is_file())

    check(singletonclient.main(["-bad"]) == 2)
    check(singletonclient.main([f"-i={tmp_path / 'missing.json'}"]) == 1)

    with patch.object(
        singletonclient.SingletonClient,
        "send_request",
        return_value={"id": "UADER"},
    ):
        check(singletonclient.main([f"-i={valid_in}"]) == 0)


def test_observer_client_full(tmp_path: Path) -> None:
    """Comprueba argumentos, escucha y reconexión en ObserverClient."""
    observerclient.configure_logging(False)
    host, port, out_f, verb, ret = observerclient.parse_args(
        ["-s=localhost", "-p=8080", "-o=out.json", "-r=1", "-v"]
    )
    check(host == "localhost" and port == 8080 and out_f == "out.json")
    check(verb is True and ret == 1)

    for bad in (["-s="], ["-p=x"], ["-p=0"], ["-o="], ["-r=0"], ["-bad"]):
        with pytest.raises(ValueError):
            observerclient.parse_args(bad)

    out_file = tmp_path / "obs_out.json"
    obs = observerclient.ObserverClient(
        host="127.0.0.1",
        port=9,
        output_file=str(out_file),
        retry_interval=0,
    )
    obs.process_notification("")
    obs.process_notification('{"id": "UADER"}')
    obs.process_notification("texto_plano")
    check(out_file.is_file())

    check(obs.run(max_retries=1) == 1)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv_sock:
        srv_sock.bind(("127.0.0.1", 0))
        port_live = srv_sock.getsockname()[1]
        srv_sock.listen(1)

        def _server_worker() -> None:
            conn, _ = srv_sock.accept()
            _ = conn.recv(1024)
            conn.sendall(b'{"id": "UADER-UPDATE"}\n')
            conn.close()

        thread = threading.Thread(target=_server_worker, daemon=True)
        thread.start()

        obs_live = observerclient.ObserverClient(
            host="127.0.0.1", port=port_live, retry_interval=0
        )
        check(obs_live.run(max_messages=1) == 0)
        thread.join(timeout=2)

    check(observerclient.main(["-bad"]) == 2)
