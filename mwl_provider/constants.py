"""Constants used throughout the tops_dicom package"""

from enum import IntEnum

# Defaults for args_cache.py
DEFAULT_USER_TO_RUN_AS = ""
DEFAULT_STARTINTERVAL = ""
DEFAULT_LISTEN = "127.0.0.1"
DEFAULT_PORT = 11112
DEFAULT_AET = "TOPS-DICOM"
DEFAULT_TERMINOLOGY_SERVER_URL = "http://terminology"
DEFAULT_TERMINOLOGY_TARGET_SYSTEM_ROOT_URL = "http://topsortho.com/fhir"
SQLITE3_DB = "/var/lib/tops-dicom/tops-dicom.db"

# Define the prefix used for the procedures to filter for as the ones to generate MWL from
MWL_PREFIX = u'\U0001F4F7'

# Mapping of DICOM Coding Scheme Designators to FHIR system URLs
CODING_SCHEME_TO_FHIR_SYSTEM = {
    'SCT': 'http://snomed.info/sct',           # SNOMED CT
    'DCM': 'http://dicom.nema.org/resources/ontology/DCM',  # DICOM
    # '99OPOR': 'http://terminology.open-ortho.org/fhir',  # Open-Ortho
    '99OPOR': 'http://terminology.open-ortho.org/fhir/extraoral-2d-photographic-scheduled-protocol',  # Open-Ortho
    'LN': 'http://loinc.org',                  # LOINC
    'RFC3066': 'urn:ietf:bcp:47',             # Language codes
    'UCUM': 'http://unitsofmeasure.org',      # Units of measure
}

# Define C-FIND statuses as constants
class CFindStatus(IntEnum):
    STATUS_INVALID_OBJECT_INSTANCE = 0x0117
    STATUS_SOP_CLASS_NOT_SUPPORTED = 0x0122
    STATUS_NOT_AUTHORISED = 0x0124
    STATUS_DUPLICATE_INVOCATION = 0x0210
    STATUS_UNRECOGNISED_OPERATION = 0x0211
    STATUS_MISTYPED_ARGUMENT = 0x0212
    STATUS_PENDING = 0xFF00
    STATUS_FAILURE = 0xC000
    STATUS_SUCCESS = 0x0000

# Map verbosity levels to standard Python logging levels
# WARNING = 30, INFO = 20, DEBUG = 10
verbosity_mapping = {
    0: 30,  # Default to WARNING if -v is not provided
    1: 20,  # INFO
    2: 10   # DEBUG
}

# UIDs. See ./open-ortho/uid-registry.txt github repo for more information
UID_BASE = '1.3.6.1.4.1.61741.11.7'