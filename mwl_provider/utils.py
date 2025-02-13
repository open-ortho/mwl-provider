import os

class TopsRequirementsValidationError(ValueError):
    """Raised when a DICOM dataset does not meet the required standards for processing."""
    pass

def generate_new_flask_secret_key():
    return os.urandom(24).hex()

