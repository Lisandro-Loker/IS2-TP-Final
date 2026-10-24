"""Cliente ObserverClient para suscribirse a cambios en CorporateData."""

import json
import logging
import socket
import sys
import time
import uuid
from pathlib import Path
from typing import Any

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080
DEFAULT_RETRY_SECONDS = 30
BUFFER_SIZE = 65536


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
) -> tuple[str, int, str | None, bool, int]:
    """Analiza y valida los argumentos de consola de ObserverClient."""
    args = sys.argv[1:] if argv is None else argv
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    output_file: str | None = None
    verbose = False
    retry_seconds = DEFAULT_RETRY_SECONDS

    for arg in args:
        if arg == "-v":
            verbose = True
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
        elif arg.startswith("-o="):
            output_file = arg.split("=", 1)[1].strip()
            if not output_file:
                raise ValueError(
                    "El archivo de salida (-o) no puede estar vacío."
                )
        elif arg.startswith("-r="):
            retry_str = arg.split("=", 1)[1].strip()
            if not retry_str.isdigit() or int(retry_str) < 1:
                raise ValueError(
                    f"Intervalo de reintento inválido: '{retry_str}'."
                )
            retry_seconds = int(retry_str)
        else:
            raise ValueError(f"Argumento malformado o desconocido: '{arg}'.")

    return host, port, output_file, verbose, retry_seconds


class ObserverClient:
    """Cliente TCP suscriptor que recibe notificaciones del servidor."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        output_file: str | None = None,
        retry_interval: int = DEFAULT_RETRY_SECONDS,
    ) -> None:
        """Inicializa el cliente observador con sus parámetros de red."""
        self.host = host
        self.port = port
        self.output_file = output_file
        self.retry_interval = retry_interval

    @staticmethod
    def build_subscribe_request() -> dict[str, str]:
        """Construye el requerimiento JSON de suscripción con UUID local."""
        return {
            "UUID": str(uuid.getnode()),
            "ACTION": "subscribe",
        }

    def process_notification(self, raw_message: str) -> None:
        """Procesa la notificación JSON, la imprime y la guarda si aplica."""
        text = raw_message.strip()
        if not text:
            return

        try:
            parsed: Any = json.loads(text)
            formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            formatted = text

        print(formatted, flush=True)
        if self.output_file:
            path = Path(self.output_file)
            with path.open("a", encoding="utf-8") as file_obj:
                file_obj.write(formatted + "\n")
            logging.debug("Guardado en '%s'.", self.output_file)

    def _listen_socket(
        self,
        sock: socket.socket,
        count: int,
        max_messages: int | None,
    ) -> int:
        """Escucha notificaciones entrantes en un socket activo."""
        while True:
            data = sock.recv(BUFFER_SIZE)
            if not data:
                raise ConnectionResetError(
                    "El servidor cerró la conexión TCP."
                )
            decoded = data.decode("utf-8")
            for line in decoded.splitlines():
                if not line.strip():
                    continue
                self.process_notification(line)
                count += 1
                if max_messages is not None and count >= max_messages:
                    return count

    def run(
        self,
        max_messages: int | None = None,
        max_retries: int | None = None,
    ) -> int:
        """Ejecuta el ciclo de suscripción, escucha y reconexión."""
        count = 0
        retries = 0

        try:
            while True:
                try:
                    logging.debug(
                        "Conectando al servidor %s:%s...",
                        self.host,
                        self.port,
                    )
                    with socket.create_connection(
                        (self.host, self.port)
                    ) as sock:
                        req = self.build_subscribe_request()
                        payload = (json.dumps(req) + "\n").encode("utf-8")
                        sock.sendall(payload)
                        logging.info(
                            "Suscripción enviada a %s:%s",
                            self.host,
                            self.port,
                        )
                        count = self._listen_socket(sock, count, max_messages)
                        if max_messages is not None and count >= max_messages:
                            return 0
                except OSError as exc:
                    retries += 1
                    logging.warning(
                        "Conexión interrumpida (%s). "
                        "Reintentando en %s segundos...",
                        exc,
                        self.retry_interval,
                    )
                    if max_retries is not None and retries >= max_retries:
                        err = {
                            "Error": (
                                f"Servidor no disponible en "
                                f"{self.host}:{self.port} ({exc})."
                            )
                        }
                        print(json.dumps(err, ensure_ascii=False))
                        return 1
                    time.sleep(self.retry_interval)
        except KeyboardInterrupt:
            logging.info("ObserverClient detenido manualmente.")
            return 0


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada principal de ObserverClient."""
    try:
        host, port, output_file, verbose, retry_sec = parse_args(argv)
    except ValueError as exc:
        print(json.dumps({"Error": str(exc)}, ensure_ascii=False))
        return 2

    configure_logging(verbose)
    client = ObserverClient(
        host=host,
        port=port,
        output_file=output_file,
        retry_interval=retry_sec,
    )
    return client.run()


if __name__ == "__main__":
    sys.exit(main())
