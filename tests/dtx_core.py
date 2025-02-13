from pydicom.dataset import Dataset
from pydicom.filewriter import FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import generate_uid, ExplicitVRLittleEndian, ImplicitVRLittleEndian, PYDICOM_IMPLEMENTATION_UID
from datetime import datetime, timedelta

class DTXCoreMWL(Dataset):
    """ A Requesting DICOM MWL as created by DTX Core.
    """
    def __init__(self, modality='DX', startdate=None, starttime=None):
        super().__init__()
        self.StudyTime = ''
        self.AccessionNumber = ''
        self.InstitutionName = ''
        self.ReferringPhysicianName = ''
        self.StudyDescription = ''
        self.ProcedureCodeSequence = Sequence([])
        self.AdmittingDiagnosesDescription = ''
        self.ReferencedStudySequence = Sequence([])
        self.PatientName = ''
        self.PatientID = ''
        self.IssuerOfPatientID = ''
        self.PatientBirthDate = ''
        self.PatientSex = ''
        self.PatientWeight = None
        self.MedicalAlerts = ''
        self.Allergies = ''
        self.PregnancyStatus = None
        self.PatientComments = ''
        self.StudyInstanceUID = ''
        self.StudyID = ''
        self.RequestingPhysician = ''
        self.RequestedProcedureDescription = ''
        self.RequestedProcedureCodeSequence = Sequence([])
        self.AdmissionID = ''
        self.SpecialNeeds = ''
        self.CurrentPatientLocation = ''
        self.PatientState = ''
        
        # Set default startdate to today if not provided
        if startdate is None:
            startdate = datetime.now().strftime('%Y%m%d-')
        
        # Set default starttime to 1 hour before now if not provided
        if starttime is None:
            starttime = (datetime.now() - timedelta(hours=1)).strftime('%H%M%S-')
        
        # Create the ScheduledProcedureStepSequence
        scheduled_procedure_step = Dataset()
        scheduled_procedure_step.Modality = modality
        scheduled_procedure_step.AnatomicalOrientationType = ''
        scheduled_procedure_step.RequestedContrastAgent = ''
        scheduled_procedure_step.ScheduledStationAETitle = ''
        scheduled_procedure_step.ScheduledProcedureStepStartDate = startdate
        scheduled_procedure_step.ScheduledProcedureStepStartTime = starttime
        scheduled_procedure_step.ScheduledPerformingPhysicianName = ''
        scheduled_procedure_step.ScheduledProcedureStepDescription = ''
        scheduled_procedure_step.ScheduledProtocolCodeSequence = Sequence([])
        scheduled_procedure_step.ScheduledProcedureStepID = ''
        scheduled_procedure_step.ScheduledStationName = ''
        scheduled_procedure_step.ScheduledProcedureStepLocation = ''
        scheduled_procedure_step.PreMedication = ''
        
        self.ScheduledProcedureStepSequence = Sequence([scheduled_procedure_step])
        self.RequestedProcedureID = ''
        self.ReasonForTheRequestedProcedure = ''
        self.RequestedProcedurePriority = ''
       
    def save_as(self, filename, write_like_original=True):
        """Override save_as to prepare the dataset for saving."""
        self.prepare_for_saving()
        super().save_as(filename, write_like_original)

    def prepare_for_saving(self):
        """Prepare the dataset for saving by adding file_meta and other required tags."""
        self.is_little_endian = True
        self.is_implicit_VR = True
        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = generate_uid()
        file_meta.MediaStorageSOPInstanceUID = self.StudyInstanceUID
        file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
        file_meta.TransferSyntaxUID = ExplicitVRLittleEndian if not self.is_implicit_VR else ImplicitVRLittleEndian

        self.file_meta = file_meta
def main():
    # Generate three different MWL instances
    mwl_CT = DTXCoreMWL(modality='CT', startdate='20241208', starttime='080000')
    mwl_VL = DTXCoreMWL(modality='VL', startdate='20241209', starttime='090000')
    mwl_DX = DTXCoreMWL(modality='DX', startdate='20241210', starttime='100000')

    # Save them to files
    mwl_CT.save_as('test_output_mwl_CT.dcm', write_like_original=False)
    mwl_VL.save_as('test_output_mwl_VL.dcm', write_like_original=False)
    mwl_DX.save_as('test_output_mwl_DX.dcm', write_like_original=False)

if __name__ == "__main__":
    main()
