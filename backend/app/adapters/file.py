"""
File/sFTP Adapter — lee y escribe mensajes HL7 desde filesystem y sFTP.

Común en hospitales para:
  - Recibir resultados de lab via sFTP drop folder
  - Exportar mensajes a carpetas compartidas
  - Batch processing de archivos HL7

Soporta:
  - FileWatcher: polling de directorio local
  - FileSender: escribir a directorio local
  - SFTPWatcher: polling de directorio sFTP remoto
  - SFTPSender: upload a sFTP remoto
"""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable, Optional

import structlog

logger = structlog.get_logger()

FileHandler = Callable[[str, str], Awaitable[None]]
"""Callback: async def handler(raw_content: str, filename: str) -> None"""


@dataclass
class FileWatcherConfig:
    """Configuración de un file watcher (inbound)."""
    watch_dir: str
    name: str = ""
    pattern: str = "*.hl7"
    poll_interval: int = 5  # seconds
    archive_dir: Optional[str] = None  # Move processed files here
    error_dir: Optional[str] = None  # Move failed files here
    delete_after: bool = False  # Delete file after processing

    def __post_init__(self):
        if not self.name:
            self.name = f"FILE_IN_{Path(self.watch_dir).name}"


class FileWatcher:
    """Watcher que monitorea un directorio por archivos HL7 nuevos.

    Equivalente a EnsLib.File.InboundAdapter en IRIS.
    """

    def __init__(self, config: FileWatcherConfig, handler: FileHandler):
        self.config = config
        self.handler = handler
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._processed: set[str] = set()

    async def start(self) -> None:
        """Iniciar polling."""
        self._running = True

        # Create directories
        os.makedirs(self.config.watch_dir, exist_ok=True)
        if self.config.archive_dir:
            os.makedirs(self.config.archive_dir, exist_ok=True)
        if self.config.error_dir:
            os.makedirs(self.config.error_dir, exist_ok=True)

        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "file_watcher_started",
            name=self.config.name,
            dir=self.config.watch_dir,
            pattern=self.config.pattern,
        )

    async def stop(self) -> None:
        """Detener polling."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("file_watcher_stopped", name=self.config.name)

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._scan_directory()
            except Exception as e:
                logger.error("file_watcher_error", name=self.config.name, error=str(e))
            await asyncio.sleep(self.config.poll_interval)

    async def _scan_directory(self) -> None:
        """Escanear directorio por archivos nuevos."""
        watch_path = Path(self.config.watch_dir)
        if not watch_path.exists():
            return

        for filepath in sorted(watch_path.glob(self.config.pattern)):
            if not filepath.is_file():
                continue
            if str(filepath) in self._processed:
                continue

            await self._process_file(filepath)

    async def _process_file(self, filepath: Path) -> None:
        """Procesar un archivo individual."""
        filename = filepath.name
        log = logger.bind(watcher=self.config.name, file=filename)

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            if not content.strip():
                return

            log.info("file_processing", size=len(content))
            await self.handler(content, filename)

            # Success: archive or delete
            self._processed.add(str(filepath))
            if self.config.archive_dir:
                dest = Path(self.config.archive_dir) / f"{datetime.now():%Y%m%d%H%M%S}_{filename}"
                shutil.move(str(filepath), str(dest))
                log.info("file_archived", dest=str(dest))
            elif self.config.delete_after:
                filepath.unlink()
                log.info("file_deleted")

        except Exception as e:
            log.error("file_process_error", error=str(e))
            if self.config.error_dir:
                dest = Path(self.config.error_dir) / f"{datetime.now():%Y%m%d%H%M%S}_{filename}"
                shutil.move(str(filepath), str(dest))


@dataclass
class FileSenderConfig:
    """Configuración de un file sender (outbound)."""
    output_dir: str
    name: str = ""
    filename_template: str = "{msg_type}_{msg_id}_{timestamp}.hl7"

    def __post_init__(self):
        if not self.name:
            self.name = f"FILE_OUT_{Path(self.output_dir).name}"


class FileSender:
    """Sender que escribe mensajes a archivos.

    Equivalente a EnsLib.File.OutboundAdapter en IRIS.
    """

    def __init__(self, config: FileSenderConfig):
        self.config = config

    async def connect(self) -> None:
        os.makedirs(self.config.output_dir, exist_ok=True)
        logger.info("file_sender_ready", name=self.config.name, dir=self.config.output_dir)

    async def disconnect(self) -> None:
        pass

    async def send(self, message: str) -> Optional[str]:
        """Escribir mensaje a archivo. Returns filename."""
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        filename = self.config.filename_template.format(
            msg_type="HL7",
            msg_id=timestamp,
            timestamp=timestamp,
        )

        filepath = Path(self.config.output_dir) / filename
        filepath.write_text(message, encoding="utf-8")

        logger.info(
            "file_written",
            name=self.config.name,
            file=str(filepath),
            size=len(message),
        )
        return str(filepath)


@dataclass
class SFTPConfig:
    """Configuración para conexiones sFTP."""
    host: str
    port: int = 22
    username: str = ""
    password: Optional[str] = None
    key_file: Optional[str] = None
    remote_dir: str = "/"
    name: str = ""
    poll_interval: int = 30
    pattern: str = "*.hl7"
    local_temp_dir: str = "/tmp/healthflow_sftp"

    def __post_init__(self):
        if not self.name:
            self.name = f"SFTP_{self.host}:{self.port}"


class SFTPClient:
    """Cliente sFTP async para descarga/upload de archivos.

    Usa asyncssh internamente (lazy import para no requerir la dependencia
    si no se usa sFTP).
    """

    def __init__(self, config: SFTPConfig):
        self.config = config
        self._conn = None

    async def connect(self) -> None:
        """Conectar al servidor sFTP."""
        try:
            import asyncssh
        except ImportError:
            raise RuntimeError("asyncssh required for SFTP. Install: pip install asyncssh")

        kwargs = {
            "host": self.config.host,
            "port": self.config.port,
            "username": self.config.username,
            "known_hosts": None,
        }
        if self.config.password:
            kwargs["password"] = self.config.password
        if self.config.key_file:
            kwargs["client_keys"] = [self.config.key_file]

        self._conn = await asyncssh.connect(**kwargs)
        logger.info("sftp_connected", name=self.config.name, host=self.config.host)

    async def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    async def list_files(self, pattern: Optional[str] = None) -> list[str]:
        """Listar archivos en el directorio remoto."""
        if not self._conn:
            await self.connect()
        sftp = await self._conn.start_sftp_client()
        files = await sftp.listdir(self.config.remote_dir)
        if pattern:
            from fnmatch import fnmatch
            files = [f for f in files if fnmatch(f, pattern)]
        return sorted(files)

    async def download(self, remote_filename: str) -> str:
        """Descargar archivo y retornar contenido."""
        if not self._conn:
            await self.connect()
        sftp = await self._conn.start_sftp_client()
        remote_path = f"{self.config.remote_dir}/{remote_filename}"
        content = await sftp.open(remote_path).read()
        return content.decode("utf-8", errors="replace")

    async def upload(self, content: str, remote_filename: str) -> None:
        """Subir contenido como archivo."""
        if not self._conn:
            await self.connect()
        sftp = await self._conn.start_sftp_client()
        remote_path = f"{self.config.remote_dir}/{remote_filename}"
        async with sftp.open(remote_path, "w") as f:
            await f.write(content)
        logger.info("sftp_uploaded", name=self.config.name, file=remote_path)

    async def delete(self, remote_filename: str) -> None:
        """Eliminar archivo remoto."""
        if not self._conn:
            await self.connect()
        sftp = await self._conn.start_sftp_client()
        await sftp.remove(f"{self.config.remote_dir}/{remote_filename}")
