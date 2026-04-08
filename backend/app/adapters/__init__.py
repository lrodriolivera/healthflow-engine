"""Protocol adapters: MLLP, SOAP, REST, FHIR."""

from .mllp import MLLPListener, MLLPSender, MLLPListenerConfig, MLLPSenderConfig
from .soap import SOAPClient, SOAPConfig, SOAPError
from .rest import RESTSender, RESTSenderConfig, AuthType
from .file import FileWatcher, FileWatcherConfig, FileSender, FileSenderConfig
from .handler import create_nats_handler
from .registry import AdapterRegistry

__all__ = [
    "MLLPListener",
    "MLLPSender",
    "MLLPListenerConfig",
    "MLLPSenderConfig",
    "SOAPClient",
    "SOAPConfig",
    "SOAPError",
    "create_nats_handler",
    "AdapterRegistry",
]
