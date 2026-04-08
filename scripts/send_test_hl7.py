#!/usr/bin/env python3
"""
Enviar mensajes HL7 de prueba via MLLP.

Uso:
    python scripts/send_test_hl7.py --port 2575 --file test_data/adt_a01.hl7
    python scripts/send_test_hl7.py --port 2575 --message "MSH|^~\\&|..."
"""

import argparse
import socket
import sys

VT = b"\x0b"
FS = b"\x1c"
CR = b"\x0d"


def send_mllp(host: str, port: int, message: str, timeout: int = 30) -> str:
    """Enviar mensaje HL7 via MLLP y retornar ACK."""
    # Normalize line endings
    message = message.replace("\r\n", "\r").replace("\n", "\r").strip()

    frame = VT + message.encode("utf-8") + FS + CR

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.sendall(frame)

        # Read ACK
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if FS in response:
                break

    # Extract message from MLLP frame
    if VT in response:
        start = response.index(VT) + 1
        end = response.index(FS) if FS in response else len(response)
        return response[start:end].decode("utf-8", errors="replace")
    return response.decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="Send HL7 test message via MLLP")
    parser.add_argument("--host", default="localhost", help="Target host")
    parser.add_argument("--port", type=int, default=2575, help="Target port")
    parser.add_argument("--file", help="HL7 message file")
    parser.add_argument("--message", help="HL7 message string")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")

    args = parser.parse_args()

    if args.file:
        with open(args.file, "r") as f:
            message = f.read()
    elif args.message:
        message = args.message
    else:
        print("Error: provide --file or --message", file=sys.stderr)
        sys.exit(1)

    print(f"Sending to {args.host}:{args.port}...")
    try:
        ack = send_mllp(args.host, args.port, message, args.timeout)
        print(f"ACK received:")
        print(ack)

        # Check ACK code
        for line in ack.split("\r"):
            if line.startswith("MSA"):
                code = line.split("|")[1]
                if code == "AA":
                    print("\n✓ Message accepted (AA)")
                elif code == "AE":
                    print("\n✗ Application error (AE)")
                elif code == "AR":
                    print("\n✗ Application reject (AR)")
                break

    except ConnectionRefusedError:
        print(f"Error: Connection refused to {args.host}:{args.port}", file=sys.stderr)
        sys.exit(1)
    except socket.timeout:
        print(f"Error: Timeout waiting for ACK", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
