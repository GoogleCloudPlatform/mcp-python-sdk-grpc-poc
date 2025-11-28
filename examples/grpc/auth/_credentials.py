"""Loading SSL credentials for gRPC Python authentication example."""

import os


def _load_credential_from_file(filepath):
    current_dir = os.path.dirname(__file__)
    full_path = os.path.join(current_dir, filepath)
    with open(full_path, "rb") as f:
        return f.read()


SERVER_CERTIFICATE = _load_credential_from_file("localhost.crt")
SERVER_CERTIFICATE_KEY = _load_credential_from_file("localhost.key")
ROOT_CERTIFICATE = _load_credential_from_file("root.crt")
