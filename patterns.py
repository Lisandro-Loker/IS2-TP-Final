"""Módulo de patrones Singleton, Observer y Proxy para el TPFI IS2."""

import json
import logging
import socket
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

CORPORATE_FIELDS: tuple[str, ...] = (
    "cp",
    "CUIT",
    "domicilio",
    "idreq",
    "idSeq",
    "localidad",
    "provincia",
    "sede",
    "seqID",
    "telefono",
    "web",
)


def sanitize_decimals(obj: Any) -> Any:
    """Convierte objetos Decimal de DynamoDB a str recursivamente."""
    if isinstance(obj, list):
        return [sanitize_decimals(item) for item in obj]
    if isinstance(obj, dict):
        return {key: sanitize_decimals(val) for key, val in obj.items()}
    if isinstance(obj, Decimal):
        return str(obj)
    return obj


class CorporateLogSingleton:
    """Implementa el patrón Singleton para el acceso a CorporateLog."""

    _instance: Optional["CorporateLogSingleton"] = None
    table: Any = None

    def __new__(cls) -> "CorporateLogSingleton":
        """Garantiza una única instancia de conexión a CorporateLog."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            dynamodb: Any = boto3.resource("dynamodb")
            cls._instance.table = dynamodb.Table("CorporateLog")
            logging.debug("Instancia Singleton creada para CorporateLog.")
        return cls._instance

    def log_action(
        self,
        client_uuid: str,
        session_id: str,
        action: str,
        record_id: str = "",
    ) -> bool:
        """Registra una pista de auditoría en la tabla CorporateLog."""
        log_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item: dict[str, Any] = {
            "id": log_id,
            "CPUid": str(client_uuid),
            "sessionid": str(session_id),
            "action": str(action),
            "timestamp": timestamp,
        }
        if record_id:
            item["record_id"] = str(record_id)

        try:
            self.table.put_item(Item=item)
            logging.debug("Auditoría registrada en CorporateLog: %s", item)
            return True
        except (BotoCoreError, ClientError) as exc:
            logging.error("Error grabando en CorporateLog: %s", exc)
            return False


class CorporateDataSingleton:
    """Implementa el patrón Singleton para el acceso a CorporateData."""

    _instance: Optional["CorporateDataSingleton"] = None
    table: Any = None

    def __new__(cls) -> "CorporateDataSingleton":
        """Garantiza una única instancia de conexión a CorporateData."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            dynamodb: Any = boto3.resource("dynamodb")
            cls._instance.table = dynamodb.Table("CorporateData")
            logging.debug("Instancia Singleton creada para CorporateData.")
        return cls._instance

    def get_record(self, record_id: str) -> dict[str, Any]:
        """Recupera un registro específico de CorporateData por su ID."""
        try:
            response = self.table.get_item(Key={"id": record_id})
            if "Item" in response:
                result: dict[str, Any] = sanitize_decimals(response["Item"])
                return result
            return {"Error": f"Registro '{record_id}' no encontrado."}
        except (BotoCoreError, ClientError) as exc:
            logging.error("Error en get_record de CorporateData: %s", exc)
            return {"Error": f"Error de base de datos: {exc}"}

    def list_records(self) -> list[dict[str, Any]] | dict[str, str]:
        """Lista todos los registros disponibles en CorporateData."""
        try:
            response = self.table.scan()
            items = response.get("Items", [])
            result: list[dict[str, Any]] = sanitize_decimals(items)
            return result
        except (BotoCoreError, ClientError) as exc:
            logging.error("Error en list_records de CorporateData: %s", exc)
            return {"Error": f"Error de base de datos: {exc}"}

    def set_record(
        self, record_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Crea o actualiza un registro en la tabla CorporateData."""
        try:
            response = self.table.get_item(Key={"id": record_id})
            existing = response.get("Item")

            if existing is not None:
                record: dict[str, Any] = sanitize_decimals(existing)
                for field in CORPORATE_FIELDS:
                    if field in data and data[field] is not None:
                        record[field] = str(data[field])
            else:
                record = {"id": record_id}
                for field in CORPORATE_FIELDS:
                    val = data.get(field)
                    record[field] = str(val) if val is not None else ""

            self.table.put_item(Item=record)
            logging.debug("Registro actualizado en CorporateData: %s", record)
            return record
        except (BotoCoreError, ClientError) as exc:
            logging.error("Error en set_record de CorporateData: %s", exc)
            return {"Error": f"Error de base de datos: {exc}"}


class ObserverManager:
    """Implementa el patrón Observer para gestionar clientes suscriptos."""

    def __init__(self) -> None:
        """Inicializa la lista de sockets suscriptos."""
        self._subscribers: list[socket.socket] = []

    @property
    def subscribers(self) -> list[socket.socket]:
        """Devuelve la lista actual de sockets suscriptos."""
        return self._subscribers

    def subscribe(self, client_socket: socket.socket) -> None:
        """Registra un nuevo socket en la lista de observadores."""
        if client_socket not in self._subscribers:
            self._subscribers.append(client_socket)
            logging.debug("Nuevo cliente suscripto al Observer.")

    def unsubscribe(self, client_socket: socket.socket) -> None:
        """Elimina un socket de la lista de observadores."""
        if client_socket in self._subscribers:
            self._subscribers.remove(client_socket)
            logging.debug("Cliente eliminado del Observer.")

    def notify_all(self, data: dict[str, Any]) -> None:
        """Envía una notificación JSON a todos los clientes suscriptos."""
        payload = (json.dumps(data) + "\n").encode("utf-8")
        disconnected: list[socket.socket] = []

        for sub_socket in list(self._subscribers):
            try:
                sub_socket.sendall(payload)
            except OSError as exc:
                logging.warning("Suscriptor desconectado: %s", exc)
                disconnected.append(sub_socket)

        for dead_socket in disconnected:
            self.unsubscribe(dead_socket)


class CorporateDataProxy:
    """Implementa el patrón Proxy para coordinar auditoría, datos y avisos."""

    def __init__(self, observer: ObserverManager | None = None) -> None:
        """Inicializa el Proxy con las instancias Singleton y el Observer."""
        self.data_singleton = CorporateDataSingleton()
        self.log_singleton = CorporateLogSingleton()
        self.observer = observer if observer is not None else ObserverManager()
        self.session_id = str(uuid.uuid4())

    def process_request(
        self,
        request: dict[str, Any],
        client_socket: socket.socket | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Procesa un requerimiento JSON aplicando auditoría y reglas."""
        client_uuid = str(request.get("UUID", "")).strip()
        action = str(request.get("ACTION", "")).strip().lower()
        record_id = str(request.get("ID", request.get("id", ""))).strip()

        if not client_uuid or not action:
            return {"Error": "Faltan datos mínimos necesarios (UUID, ACTION)."}

        if action == "subscribe":
            self.log_singleton.log_action(
                client_uuid, self.session_id, "subscribe"
            )
            if client_socket is not None:
                self.observer.subscribe(client_socket)
            return {"status": "OK", "message": "Subscribed successfully"}

        if action == "get":
            if not record_id:
                return {"Error": "Falta el campo ID para la acción get."}
            self.log_singleton.log_action(
                client_uuid, self.session_id, "get", record_id
            )
            return self.data_singleton.get_record(record_id)

        if action == "list":
            self.log_singleton.log_action(client_uuid, self.session_id, "list")
            return self.data_singleton.list_records()

        if action == "set":
            if not record_id:
                return {"Error": "Falta el campo ID para la acción set."}
            self.log_singleton.log_action(
                client_uuid, self.session_id, "set", record_id
            )
            result = self.data_singleton.set_record(record_id, request)
            if "Error" not in result:
                self.observer.notify_all(result)
            return result

        return {"Error": f"Acción '{action}' desconocida o no soportada."}
