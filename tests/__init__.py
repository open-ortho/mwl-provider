import os
from datetime import datetime
from pydicom.uid import generate_uid
from pydicom.dataset import Dataset
from pynetdicom.sop_class import ModalityWorklistInformationFind
import logging

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s: %(message)s')
logger = logging.getLogger(__name__)

# database_file = ':memory:'
_database_file = './tests/_test.db'

def get_full_path_of_database_file():
    return os.path.abspath(_database_file)

test_args = {
    'save_mwl': False,
    'limit': 10,
    'database_file': get_full_path_of_database_file(),
    'listen': '127.0.0.1',
    'port': '11112',
    'aet': 'TEST_AET',
    'verbose': 2,
}

def make_sample_MWL():
    # Create the main dataset
    ds = Dataset()

    # Specific Character Set for ISO 8859-1 (Latin alphabet No. 1)
    ds.SpecificCharacterSet = 'ISO_IR 100'

    # Sample accession number
    ds.AccessionNumber = "TOPS-123456"

    # Sample patient data
    ds.PatientName = "Doe^John^^Mr"
    ds.PatientID = "123456789"
    ds.PatientBirthDate = "19800101"  # January 1st, 1980
    ds.PatientSex = "M"

    # Study instance UID
    ds.StudyInstanceUID = generate_uid()

    # Requested procedure info
    ds.RequestedProcedureID = "PROC-98765"
    ds.RequestedProcedureComments = "Patient has been experiencing mild chest pain."
    ds.RequestedProcedureDescription = "Chest X-ray"

    # Scheduled Procedure Step Sequence
    ds.ScheduledProcedureStepSequence = [Dataset()]
    sps = ds.ScheduledProcedureStepSequence[0]

    # Modality for the procedure (X-ray in this case)
    sps.Modality = "CR"  # CR stands for Computed Radiography

    # Scheduled Procedure Step Start Date/Time (e.g., scheduled for today)
    appointment_date = datetime.today().strftime('%Y%m%d')  # Today's date
    appointment_start_time = datetime.now().strftime('%H%M%S.%f')  # Current time

    sps.ScheduledProcedureStepStartDate = appointment_date
    sps.ScheduledProcedureStepStartTime = appointment_start_time

    # Scheduled physician information
    sps.ScheduledPerformingPhysicianName = "Smith^Robert^^Dr"

    # Procedure step details
    sps.ScheduledProcedureStepID = "STEP-001"
    sps.ScheduledProcedureStepDescription = "X-ray of the chest"

    # Location of the procedure (e.g., specific room and chair) max 16 characters
    sps.ScheduledProcedureStepLocation = "Room 101-Chair A"

    # Requesting physician details
    ds.RequestingPhysician = "Brown^Emily^^Dr"

    # SOP Class and Instance UID
    ds.SOPClassUID = ModalityWorklistInformationFind
    ds.SOPInstanceUID = generate_uid()

    # File Meta information (if necessary)
    from pydicom.filewriter import FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, PYDICOM_IMPLEMENTATION_UID
    ds.is_little_endian = True
    ds.is_implicit_VR = True
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = generate_uid()
    file_meta.MediaStorageSOPInstanceUID = ds.StudyInstanceUID
    file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian if not ds.is_implicit_VR else ImplicitVRLittleEndian

    ds.file_meta = file_meta

    return ds
