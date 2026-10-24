"""Servidor de aplicaciones SingletonProxyObserver para el TPFI IS2."""

import json
import logging
import socket
import sys
from typing import Any

from patterns import CorporateDataProxy, ObserverManager

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
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


def parse_args(argv: list[str] | None = None) -> tuple[int, bool]:
    """Analiza y valida los argumentos de línea de comandos del servidor."""
    args = sys.argv[1:] if argv is None else argv
    port = DEFAULT_PORT
    verbose = False

    for arg in args:
        if arg == "-v":
            verbose = True
        elif arg.startswith("-p="):
            port_str = arg.split("=", 1)[1]
            if not port_str.isdigit():
                raise ValueError(f"Puerto inválido: '{port_str}'.")
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError(f"Puerto fuera de rango: {port}.")
        else:
            raise ValueError(f"Argumento malformado o desconocido: '{arg}'.")

    return port, verbose


def extract_json_payload(raw_text: str) -> dict[str, Any]:
    """Extrae y decodifica el objeto JSON desde el mensaje recibido."""
    text = raw_text.strip()
    if "\r\n\r\n" in text:
        text = text.split("\r\n\r\n", 1)[1].strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("El requerimiento JSON debe ser un objeto.")
    return parsed


class SingletonProxyObserverServer:
    """Servidor TCP que integra los patrones Singleton, Proxy y Observer."""

    def __init__(
        self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT
    ) -> None:
        """Inicializa el servidor TCP con su Proxy y ObserverManager."""
        self.host = host
        self.port = port
        self.observer = ObserverManager()
        self.proxy = CorporateDataProxy(observer=self.observer)
        self.server_socket: socket.socket | None = None
        self.running = False

    def handle_client(
        self, client_socket: socket.socket, addr: tuple[str, int]
    ) -> None:
        """Atiende la petición de un cliente conectado por socket TCP."""
        logging.debug("Conexión recibida desde %s:%s", addr[0], addr[1])
        try:
            data = client_socket.recv(BUFFER_SIZE)
            if not data:
                client_socket.close()
                return

            raw_text = data.decode("utf-8")
            logging.debug("Payload recibido: %s", raw_text.strip())
            request = extract_json_payload(raw_text)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            logging.error("Error en formato de requerimiento: %s", exc)
            err_msg = {"Error": f"Requerimiento JSON malformado: {exc}"}
            client_socket.sendall((json.dumps(err_msg) + "\n").encode("utf-8"))
            client_socket.close()
            return

        action = str(request.get("ACTION", "")).strip().lower()
        response = self.proxy.process_request(request, client_socket)

        if action == "subscribe" and isinstance(response, dict):
            if "Error" not in response:
                logging.debug(
                    "Cliente %s suscripto. Socket mantenido abierto.", addr
                )
                return

        payload = (json.dumps(response) + "\n").encode("utf-8")
        try:
            client_socket.sendall(payload)
        except OSError as exc:
            logging.error("Error enviando respuesta a %s: %s", addr, exc)
        finally:
            client_socket.close()
            logging.debug("Conexión cerrada con %s:%s", addr[0], addr[1])

    def start(self) -> None:
        """Inicia la escucha del servidor TCP y procesa conexiones."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)
        except OSError as exc:
            self.server_socket.close()
            err = {
                "Error": (
                    f"No se pudo abrir el puerto {self.port}. "
                    f"El servidor ya se encuentra en ejecución ({exc})."
                )
            }
            print(json.dumps(err))
            raise SystemExit(1) from exc

        self.running = True
        logging.info(
            "Servidor SingletonProxyObserver escuchando en %s:%s",
            self.host,
            self.port,
        )

        try:
            while self.running:
                try:
                    client_sock, addr = self.server_socket.accept()
                except TimeoutError:
                    continue
                except OSError:
                    if not self.running:
                        break
                    raise
                self.handle_client(client_sock, addr)
        except KeyboardInterrupt:
            logging.info("Servidor detenido manualmente por el usuario.")
        finally:
            self.stop()

    def stop(self) -> None:
        """Detiene el servidor y cierra todos los sockets abiertos."""
        self.running = False
        for sub_sock in list(self.observer.subscribers):
            try:
                sub_sock.close()
            except OSError as exc:
                logging.debug("Error cerrando suscriptor: %s", exc)
            self.observer.unsubscribe(sub_sock)

        if self.server_socket is not None:
            try:
                self.server_socket.close()
            except OSError as exc:
                logging.debug("Error cerrando socket servidor: %s", exc)
            self.server_socket = None


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada principal del servidor SingletonProxyObserver."""
    try:
        port, verbose = parse_args(argv)
    except ValueError as exc:
        print(json.dumps({"Error": str(exc)}))
        return 2

    configure_logging(verbose)
    server = SingletonProxyObserverServer(port=port)
    server.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
