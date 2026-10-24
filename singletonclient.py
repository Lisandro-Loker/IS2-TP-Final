"""Cliente SingletonClient para consultar o modificar CorporateData."""

import json
import logging
import socket
import sys
import uuid
from pathlib import Path
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
BUFFER_SIZE = 65536
SOCKET_TIMEOUT = 10.0


def configure_logging(verbose: bool) -> None:
    """Configura el nivel de logging hacia salida estándar según -v."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
        force=True,
    )
    for noisy in ("boto3", "botocore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def parse_args(
    argv: list[str] | None = None,
) -> tuple[str, str | None, str, int, bool]:
    """Analiza y valida los argumentos de consola de SingletonClient."""
    args = sys.argv[1:] if argv is None else argv
    input_file: str | None = None
    output_file: str | None = None
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    verbose = False

    for arg in args:
        if arg == "-v":
            verbose = True
        elif arg.startswith("-i="):
            input_file = arg.split("=", 1)[1].strip()
        elif arg.startswith("-o="):
            output_file = arg.split("=", 1)[1].strip()
        elif arg.startswith("-s="):
            host = arg.split("=", 1)[1].strip()
            if not host:
                raise ValueError("El hostname (-s) no puede estar vacío.")
        elif arg.startswith("-p="):
            port_str = arg.split("=", 1)[1].strip()
            if not port_str.isdigit():
                raise ValueError(f"Puerto inválido: '{port_str}'.")
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError(f"Puerto fuera de rango: {port}.")
        else:
            raise ValueError(f"Argumento malformado o desconocido: '{arg}'.")

    if not input_file:
        raise ValueError(
            "El argumento de entrada '-i=input.json' es obligatorio."
        )
    if output_file is not None and not output_file:
        raise ValueError("El archivo de salida (-o) no puede estar vacío.")

    return input_file, output_file, host, port, verbose


class SingletonClient:
    """Cliente TCP para ejecutar acciones get, set y list en el servidor."""

    def __init__(
        self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT
    ) -> None:
        """Inicializa el cliente con el host y puerto del servidor destino."""
        self.host = host
        self.port = port

    def load_request(self, input_path: str) -> dict[str, Any]:
        """Carga y valida el archivo JSON de entrada."""
        path = Path(input_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"No existe el archivo de entrada: '{input_path}'."
            )

        raw_content = path.read_text(encoding="utf-8")
        data = json.loads(raw_content)
        if not isinstance(data, dict):
            raise ValueError("El contenido del JSON debe ser un objeto.")

        if "UUID" not in data:
            data["UUID"] = str(uuid.getnode())

        client_uuid = str(data.get("UUID", "")).strip()
        action = str(data.get("ACTION", "")).strip().lower()
        record_id = str(data.get("ID", data.get("id", ""))).strip()

        if not client_uuid or not action:
            raise ValueError(
                "Faltan datos mínimos necesarios en el JSON (UUID, ACTION)."
            )
        if action in ("get", "set") and not record_id:
            raise ValueError(
                f"Faltan datos mínimos necesarios: 'ID' para '{action}'."
            )

        return data

    def send_request(self, payload: dict[str, Any]) -> Any:
        """Envía el requerimiento JSON al servidor y retorna la respuesta."""
        logging.debug(
            "Conectando con servidor %s:%s para enviar: %s",
            self.host,
            self.port,
            payload,
        )
        try:
            with socket.create_connection(
                (self.host, self.port), timeout=SOCKET_TIMEOUT
            ) as sock:
                message = (json.dumps(payload) + "\n").encode("utf-8")
                sock.sendall(message)

                chunks: list[bytes] = []
                while True:
                    chunk = sock.recv(BUFFER_SIZE)
                    if not chunk:
                        break
                    chunks.append(chunk)
        except OSError as exc:
            logging.error("Error de comunicación con el servidor: %s", exc)
            return {
                "Error": (
                    f"No se pudo conectar al servidor en "
                    f"{self.host}:{self.port} ({exc})."
                )
            }

        raw_response = b"".join(chunks).decode("utf-8").strip()
        logging.debug(
            "Respuesta recibida (%d bytes): %.120s...",
            len(raw_response),
            raw_response,
        )

        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as exc:
            return {"Error": f"Respuesta inválida del servidor: {exc}"}

    @staticmethod
    def emit_output(response: Any, output_path: str | None = None) -> None:
        """Genera la salida JSON en el archivo indicado o por consola."""
        formatted = json.dumps(response, indent=2, ensure_ascii=False)
        if output_path:
            Path(output_path).write_text(formatted + "\n", encoding="utf-8")
            logging.debug("Respuesta guardada en '%s'.", output_path)
        else:
            print(formatted)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada principal de SingletonClient."""
    try:
        input_file, output_file, host, port, verbose = parse_args(argv)
    except ValueError as exc:
        print(json.dumps({"Error": str(exc)}, ensure_ascii=False))
        return 2

    configure_logging(verbose)
    client = SingletonClient(host=host, port=port)

    try:
        request_data = client.load_request(input_file)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        err_resp = {"Error": str(exc)}
        client.emit_output(err_resp, output_file)
        return 1

    response = client.send_request(request_data)
    client.emit_output(response, output_file)

    if isinstance(response, dict) and "Error" in response:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
