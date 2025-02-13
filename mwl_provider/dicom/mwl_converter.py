""" A helper module to generate DICOM MWL.

This module will NOT generate the actual MWL.

"""
from typing import cast
from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian
from pynetdicom.sop_class import ModalityWorklistInformationFind

from sqlalchemy.orm import aliased
from terminology.resources import Code
from topsserver_db.models.topsdb import Appointment, ProcedureType, Patient, StaffMember, Chair, Columns
from topsserver_db.clinical import AppointmentManager
from topsserver_db import add_seconds_to_date
from topsserver_db import logger, generate_uid, UID_SOP_INSTANCE, UID_STUDY_INSTANCE, UID_IMPLEMENTATION_CLASS

from tops_dicom.constants import TOPS_CODING_SCHEME_DESIGNATOR

def make_code_sequence(code: Code):
    if code:
        ds = Dataset()
        ds.CodeValue = code.code
        ds.CodingSchemeDesignator = code.prefix
        ds.CodeMeaning = code.display[:64]
        return ds


class MWLConverter(AppointmentManager):
    """ 
    Converts ``topsdb.Appointment`` to a bundle of Appointment and Provenance.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._type = Appointment

    def convert(self, appointment: Appointment) -> Dataset:
        """ Convert a topsdb Appointment to a DICOM MWL.

        returns a DICOM Dataset.

        Will convert any appointment passed, also those without checked_in_time. Refer to https://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_K.6.html for the required fields that need to be here. I have added all the Type 1 and Type 2 fields, empty if unknown, or if they need to be set later.

        Acession Number:

            The appointment_id is used, prefixed with 'TOPS-'.

        Requesting Physician:

            orthodontist

        Requested Procedure: 

            This is used to identify the appointment type and procedure name. Will be set to whatever is in tops. The user is then advised to perform a lookup and replace with appropriate values according to standards.

            RequestedProcedureID: 

                This is the actual instance ID of the reqeust, which tops does not keep track of. It could be similar to the Accession number, but it is tied to the procedure. For this reason, I have chosen the format TOPS-<appointment_id>-<procedure_id>

            appointment.procedure_id

            RequestedProcedureDescription: appointment.procedure.type_label

        Scheduled Procedure Step:

            Creating a single step with:

            PerformingPhysicianName: seating_staff. Useful if the MWL is queried and generated after the patient has been seated.
            StartDate: appointment date
            StartTime: appointment start time
            ID: left empty. The user should populate this.
            Description: left empty. 
            Location: column_label - chair_label

        """
        def add_scheduled_procedure_step(ds):
            """ Scheduled Procedure Step """
            sps = Dataset()

            sps.ScheduledStationAETitle = ''
            sps.ScheduledProcedureStepStartDate = appointment.date.strftime(
                '%Y%m%d')
            sps.ScheduledProcedureStepStartTime = appointment_start_datetime.strftime(
                '%H%M%S.%f')
            # Modality is a required Type 1 fields but unknown at this stage. Depends on procedure type.
            sps.Modality = ""
            sps.ScheduledPerformingPhysicianName = ""
            if seating_staff:
                sps.ScheduledPerformingPhysicianName = f'{seating_staff.last_name or ""}^{seating_staff.first_name or ""}^{seating_staff.middle_initial or ""}^{seating_staff.title or ""}^'
            sps.ScheduledProcedureStepDescription = ""
            sps.ScheduledStationName = ""

            column_label = column.label if column else ""
            chair_label = chair.label if chair else ""
            sps.ScheduledProcedureStepLocation = f"{column_label} - {chair_label}"[
                :16]

            sps.ScheduledProcedureStepID = ""
            ds.ScheduledProcedureStepSequence = [sps]

        def add_requested_procedure(ds) -> None:
            # Requested Procedure

            ds.RequestedProcedureComments = (
                appointment.grid_notes + "\n" if appointment.grid_notes and appointment.notes else "") + (appointment.notes or "")
            ds.RequestedProcedureComments = ds.RequestedProcedureComments[:10240]
            ds.RequestedProcedureID = f"TOPS-{appointment.appointment_id}-{appointment.procedure_id}"[
                :16]
            ds.RequestedProcedureDescription = procedure_type.type_label
            ds.RequestedProcedureCodeSequence = [
                make_code_sequence(Code(
                    prefix=TOPS_CODING_SCHEME_DESIGNATOR,
                    system="", # Ignored by make_code_sequence anyway.
                    code=str(appointment.procedure_id),
                    display=procedure_type.type_label))
            ]
            ds.StudyInstanceUID = generate_uid(UID_STUDY_INSTANCE)

        def add_imaging_service_request(ds):
            # Imaging Service Request

            ds.AccessionNumber = f"TOPS-{appointment.appointment_id}"[:16]
            ds.RequestingPhysician = f"{orthodontist.last_name or ''}^{orthodontist.first_name or ''}^{orthodontist.middle_initial or ''}^{orthodontist.title or ''}^"
            ds.ReferringPhysicianName = "^^^^"

        def add_visit_identification(ds):
            # Visit Identification

            ds.AdmissionID = ""

        def add_patient_medical(ds):
            # Patient Medical

            ds.PatientState = ""
            ds.PregnancyStatus = ""
            alerts = patient.medical_hx or ""
            ds.MedicalAlerts = alerts[:64]
            # In tops medical alerts and allergies are both stored in the same field.
            ds.Allergies = alerts[:64]
            ds.PatientWeight = ""
            ds.SpecialNeeds = ""

        def add_patient_identification(ds):
            # Patient Identification
            ds.PatientName = f'{patient.last_name or ""}^{patient.first_name or ""}^{patient.middle_initial or ""}^{patient.title or ""}^'
            ds.PatientID = f"{patient.custom_identifier}"

        def add_patient_demographics(ds):
            # Patient Demographics
            ds.PatientBirthDate = ""
            if patient.dob:
                ds.PatientBirthDate = patient.dob.strftime("%Y%m%d")
            # "O" as a default for Other/Unknown
            ds.PatientSex = gender_map.get(patient.gender_id, "O")
            # ds.PatientPrimaryLanguageCodeSequence = [] # Language is supported by tops, however it is not implemented here yet.

        logger.debug(f"Converting appt {appointment.appointment_id} to a MWL.")
        # Create aliases for StaffMember for different roles
        Orthodontist = aliased(StaffMember)
        SeatingStaff = aliased(StaffMember)

        # Perform the query
        patient, procedure_type, orthodontist, seating_staff, column, chair = (
            self.query(Patient, ProcedureType, Orthodontist,
                       SeatingStaff, Columns, Chair)
            .select_from(Appointment)  # Start from 'Appointment'
            .outerjoin(Patient, Patient.person_id == Appointment.patient_id)
            .outerjoin(ProcedureType, ProcedureType.type_id == Appointment.procedure_id)
            .outerjoin(Orthodontist, Orthodontist.person_id == Appointment.orthodontist_id)
            .outerjoin(SeatingStaff, SeatingStaff.person_id == Appointment.seating_staff_member_id)
            .outerjoin(Columns, Columns.column_id == Appointment.column_number)
            .outerjoin(Chair, Chair.chair_id == Columns.chair_number)
            .filter(Appointment.appointment_id == appointment.appointment_id)
            .one()
        )
        patient = cast(Patient, patient)
        procedure_type = cast(ProcedureType, procedure_type)
        orthodontist = cast(StaffMember, orthodontist)
        seating_staff = cast(StaffMember, seating_staff)
        chair = cast(Chair, chair)
        column = cast(Columns, column)

        # Define a mapping from gender_id to PatientSex
        gender_map = {1: 'F', 2: 'M'}
        appointment_start_datetime = add_seconds_to_date(
            appointment.date, appointment.start_time)

        # Create a dataset and add required MWL elements, as specified and in the order as they appear in https://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_K.6.html

        ds = Dataset()

        add_scheduled_procedure_step(ds)
        add_requested_procedure(ds)
        add_imaging_service_request(ds)
        add_visit_identification(ds)

        # Visit Status
        ds.CurrentPatientLocation = ""

        # Visit Relationship
        ds.ReferencedPatientSequence = []

        # Visit Admission: nothing
        # Patient Relationship: nothing

        add_patient_identification(ds)
        add_patient_demographics(ds)
        add_patient_medical(ds)
        ds.ConfidentialityConstraintOnPatientDataDescription = ""

        ds.SpecificCharacterSet = "ISO_IR 100"
        # Add file meta information required for DICOM files
        ds.file_meta = Dataset()
        ds.file_meta.MediaStorageSOPClassUID = ModalityWorklistInformationFind
        ds.file_meta.MediaStorageSOPInstanceUID = generate_uid(
            UID_SOP_INSTANCE)
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        ds.file_meta.ImplementationClassUID = generate_uid(
            UID_IMPLEMENTATION_CLASS)

        # Set SOP Class and Instance UID in the main dataset
        ds.SOPClassUID = ModalityWorklistInformationFind
        ds.SOPInstanceUID = ds.file_meta.MediaStorageSOPInstanceUID
        return ds
