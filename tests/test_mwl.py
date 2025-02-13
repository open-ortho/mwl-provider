# Configure logging to output to the console at debug level
# Set up logging with the custom formatter
import logging
logging.basicConfig(level=logging.DEBUG)
from tops_dicom import logger
logger = logging.getLogger(__name__)
from tests.dtx_core import DTXCoreMWL
# logger.setLevel(logging.DEBUG)

import os
import unittest
import threading
from pydicom.dataset import Dataset
from pynetdicom import AE
from pynetdicom.sop_class import ModalityWorklistInformationFind

from topsserver_db.models.topsdb import Appointment

# Import your module here
from tops_dicom.args_cache import ArgsCache
import tops_dicom
from tops_dicom.dicom.dicom_scp import SCP
from tops_dicom.dicom.dicom_c_find import C_Find
from tops_dicom.dicom.dicom_utils import dataset_to_str
from tops_dicom.model import database_exists_and_valid, init_database, populate_dataset, get_session, ExternalProcedure, RequestedProcedure, ScheduledProcedureStep
from tops_dicom.constants import CFindStatus

from tests import get_full_path_of_database_file, test_args, make_sample_MWL

# debug_logger()

def make_empty_MWL_with_required_tags():
    """Create a minimal MWL entry with only the required tags according to IHE RAD Tech."""
    ds = Dataset()
    ds.ScheduledProcedureStepSequence = [Dataset()]
    ds.ScheduledProcedureStepSequence[0].ScheduledStationAETitle = ''
    ds.ScheduledProcedureStepSequence[0].ScheduledProcedureStepStartDate = ''
    ds.ScheduledProcedureStepSequence[0].Modality = ''
    ds.RequestedProcedureID = ''
    ds.AccessionNumber = ''
    ds.PatientName = ''
    ds.PatientID = ''
    return ds

def _simulate_mwl_response():
    """Generate MWL entries based on the query (this is just a simulation)."""
    # Here we respond with one entry regardless of the input query
    # In a real scenario, you would query a database or another data source.
    mwl = Dataset()
    mwl.PatientName = 'Doe^Jane'
    mwl.ScheduledProcedureStepStartDate = '20200915'
    mwl.ScheduledProcedureStepStartTime = '130000'
    mwl.Modality = 'MR'
    mwl.ScheduledPerformingPhysicianName = 'Dr. Smith'
    mwl.AccessionNumber = '0000001'
    mwl.StudyInstanceUID = '1.2.840.113619.2.1.2411.1031152382.365'
    mwl.RequestedProcedureID = 'RP123456'
    mwl.RequestedProcedureDescription = 'Brain MRI'
    return mwl

def create_sample_data(session):
    sps = ScheduledProcedureStep()
    sps.modality = 'CR'
    sps.code_meaning = 'Scheduled Procedure Step Meaning'
    sps.code_scheme = 'TEST'
    sps.code_value = '1000'

    reqp = RequestedProcedure()
    reqp.comments = 'Requested Procedure 1'
    reqp.description = 'Description 1'
    reqp.scheduled_procedure_steps.append(sps)
    reqp.code_meaning = 'Requested Procedure Meaning'
    reqp.code_scheme = 'TEST'
    reqp.code_value = '2000'

    extp1 = ExternalProcedure()
    extp1.requested_procedure = reqp
    extp1.code = 'PROC-98765'
    session.add(extp1)
    extp2 = ExternalProcedure()
    extp2.requested_procedure = reqp
    extp2.code = '5018'
    session.add(extp2)
    extp3 = ExternalProcedure()
    extp3.requested_procedure = reqp
    extp3.code = '5036'
    session.add(extp3)
    extp4 = ExternalProcedure()
    extp4.requested_procedure = reqp
    extp4.code = '5010'
    session.add(extp4)
    session.commit()

class TestDICOMServer(unittest.TestCase):
    """ These are a series of tests which will run against the running tops-dicom SCP server.

    Starts the server first, then runs queries against it.
    
    Some tests require a running tops-server-mock container, see tests/__init__.py for connection details. Port might be on 15432.
    """
    @classmethod
    def setUpClass(cls):
        logger.setLevel(logging.DEBUG)
        logger.debug(f"Logger level is: {logger.getEffectiveLevel()}")
        logger.propagate = True
        ArgsCache._args = ArgsCache.get_arguments(test_args=test_args)
        ArgsCache._args.verbose = 2

        if not database_exists_and_valid():
            init_database()
            logging.info("Database created for testing")
        create_sample_data(get_session())

        # Start the DICOM server in a separate thread to not block the test execution
        cls.server = SCP()
        cls.server_thread = threading.Thread(
            target=cls.server.start, daemon=True)
        cls.server_thread.start()
        logging.info("Server started for testing")

    @classmethod
    def tearDownClass(cls):
        # Shutdown the server after tests complete
        cls.server.stop()
        cls.server_thread.join()
        logging.info("topsDicom Server stopped after testing")
        os.remove(get_full_path_of_database_file())
        logging.info(f"Database {get_full_path_of_database_file()} deleted after testing")

    def test_populate_dataset(self):
        """ Test populate dataset.
        topsserver-mock not required.
        """
        modalities = ['CR']
        dicom_mwl = make_sample_MWL()
        dicom_mwl = populate_dataset(dicom_mwl, modalities)
        print(dataset_to_str(dicom_mwl))
        self.assertIsNotNone(dicom_mwl)
        self.assertEqual(len(dicom_mwl.ScheduledProcedureStepSequence),1)

    def test_handle_mwl_find(self):
        """
        topsserver-mock required.
        """
        c_find = C_Find()
        # Create a Dataset to use as the C-FIND query parameters
        ds = Dataset()
        ds.QueryRetrieveLevel = 'WORKLIST'
        ds.ScheduledProcedureStepSequence = [Dataset()]
        ds.ScheduledProcedureStepSequence[0].ScheduledProcedureStepStartDate = '20230712'
        ds.ScheduledProcedureStepSequence[0].Modality = 'CR'
        print(dataset_to_str(ds))

        res = list(c_find.handle_mwl_find(ds))
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0][0], CFindStatus.STATUS_PENDING)

    def test_dtx_core_mwl(self):
        ae = AE(ae_title='TEST-AE')
        ae.add_requested_context(ModalityWorklistInformationFind)
        
        ds = DTXCoreMWL(modality='CR', startdate='20230712-', starttime='030000-')
        print(dataset_to_str(ds))

        # Perform the C-FIND request
        assoc = ae.associate('localhost', tops_dicom.DEFAULT_PORT)
        self.assertTrue(assoc.is_established)

        # Send the C-FIND request
        responses = assoc.send_c_find(ds, ModalityWorklistInformationFind)
        response_list = [resp for resp in responses]

        # Check that the response is valid
        self.assertTrue(response_list, "No responses received")
        self.assertEqual(len(response_list), 2)
        response = response_list[0][0]
        self.assertEqual(response.Status, 0xFF00,
                         f"Not all responses were pending status: {hex(response.Status)}")

        # Check contents of one of the responses
        if response_list:
            mwl_response = response_list[0][1]
            self.assertEqual(mwl_response.PatientName,
                             'Chauvet^Patricia^Z^Sig.na^', "Patient Name does not match")
            self.assertEqual(mwl_response.ScheduledProcedureStepSequence[0].Modality, 'CR',
                             "Modality does not match")
            self.assertEqual(mwl_response.AccessionNumber,
                             'TOPS-9992', "Accession Number does not match")

        # Release the association
        assoc.release()
        self.assertFalse(assoc.is_established)

    def test_modality_worklist_find(self):
        """
        topsserver-mock required.
        """
        # Create AE title and configure for sending C-FIND
        ae = AE(ae_title='TEST-AE')
        ae.add_requested_context(ModalityWorklistInformationFind)

        # TEST 1 ************** Test for a specific date and modality
        # Create a Dataset to use as the C-FIND query by start date and modality
        ds = make_empty_MWL_with_required_tags()
        ds.QueryRetrieveLevel = 'WORKLIST'
        ds.ScheduledProcedureStepSequence[0].ScheduledProcedureStepStartDate = '20230712'
        ds.ScheduledProcedureStepSequence[0].Modality = 'CR'

        # Perform the C-FIND request
        assoc = ae.associate('localhost', tops_dicom.DEFAULT_PORT)
        self.assertTrue(assoc.is_established)

        # Send the C-FIND request
        responses = assoc.send_c_find(ds, ModalityWorklistInformationFind)
        response_list = [resp for resp in responses]

        # Check that the response is valid
        self.assertTrue(response_list, "No responses received")
        self.assertEqual(len(response_list), 2)
        response = response_list[0][0]
        self.assertEqual(response.Status, 0xFF00,
                         f"Not all responses were pending status: {hex(response.Status)}")

        # Check contents of one of the responses
        if response_list:
            mwl_response = response_list[0][1]
            self.assertEqual(mwl_response.PatientName,
                             'Chauvet^Patricia^Z^Sig.na^', "Patient Name does not match")
            self.assertEqual(mwl_response.ScheduledProcedureStepSequence[0].Modality, 'CR',
                             "Modality does not match")
            self.assertEqual(mwl_response.AccessionNumber,
                             'TOPS-9992', "Accession Number does not match")

        # Release the association
        assoc.release()
        self.assertFalse(assoc.is_established)


        # TEST 2 ************** Now test for a specific accession number
        ds = make_empty_MWL_with_required_tags()
        ds.QueryRetrieveLevel = 'WORKLIST'
        ds.AccessionNumber = 'TOPS-823'

        # Perform the C-FIND request
        assoc = ae.associate('localhost', tops_dicom.DEFAULT_PORT)
        self.assertTrue(assoc.is_established)

        # Send the C-FIND request
        responses = assoc.send_c_find(ds, ModalityWorklistInformationFind)
        response_list = [resp for resp in responses]

        # Check that the response is valid
        self.assertTrue(response_list, "No responses received")
        self.assertEqual(len(response_list), 2)
        response = response_list[0][0]
        self.assertEqual(response.Status, 0xFF00,
                         f"Not all responses were pending status: {hex(response.Status)}")

        # Check contents of one of the responses
        if response_list:
            mwl_response = response_list[0][1]
            self.assertEqual(mwl_response.PatientName,
                             'Davies^Jessica^L^Ms.^', "Patient Name does not match")
            self.assertEqual(mwl_response.ScheduledProcedureStepSequence[0].Modality, 'CR',
                             "Modality does not match")
            self.assertEqual(mwl_response.AccessionNumber,
                             'TOPS-823', "Accession Number does not match")

        # Release the association
        assoc.release()
        self.assertFalse(assoc.is_established)

if __name__ == '__main__':
    unittest.main()
