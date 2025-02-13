import os
import logging
import unittest
from unittest.mock import patch
from datetime import datetime

from tops_dicom.args_cache import ArgsCache
from tops_dicom.model import init_database, database_exists_and_valid, get_session, ScheduledProtocol, ScheduledProcedureStep, RequestedProcedure
from tops_dicom.entry_points.data_import import import_terminology
from tops_dicom.dicom.dicom_utils import make_tops_image_from_dataset

from tests import test_args, get_full_path_of_database_file
from tests import logger

class TestCStoreImage(unittest.TestCase):
    """ Test the DICOM C-Store for importing images. """
    @classmethod
    def setUpClass(cls):
        logger.setLevel(logging.DEBUG)
        logger.debug(f"Logger level is: {logger.getEffectiveLevel()}")
        logger.propagate = True
        ArgsCache._args = ArgsCache.get_arguments(test_args=test_args)
        ArgsCache._args.verbose = 2


    def setUp(self):
        self.test_args = {}
        self.test_args['sftp'] = {
            'host': ArgsCache._args.topsserver_sftp_host,
            'username': ArgsCache._args.topsserver_sftp_username,
            'port': ArgsCache._args.topsserver_sftp_port,
        }
        self.test_args['postgresql'] = {
            'username': ArgsCache._args.topsserver_username,
            'password': ArgsCache._args.topsserver_password,
            'host': ArgsCache._args.topsserver_ip,
            'port': int(ArgsCache._args.topsserver_port),
        }
        # Add mock patcher for translate function so we don't need to rely on a running terminology server
        self.translate_patcher = patch('tops_dicom.terminology.translate')
        self.mock_translate = self.translate_patcher.start()
        # You can set the return value in your test
        self.mock_translate.return_value = 42  # or whatever valid image type ID you need

    def tearDown(self):
        self.translate_patcher.stop()

    def test_make_tops_image_from_dataset(self):
        import pydicom
        from pathlib import Path
        test_args = ArgsCache._args
        # Load test DICOM file
        test_file = Path(__file__).parent / 'test_photo.dcm'
        ds = pydicom.dcmread(test_file)

        # Create TopsImage
        tops_image = make_tops_image_from_dataset(ds=ds, config=self.test_args)
        # we must mock translate() to return a valid image type ID, otherwise the test will not continue.

        # Verify attributes
        self.assertEqual(tops_image.appointment_id, 123456)
        self.assertEqual(
            tops_image.image_acquisition_datetime,
            datetime(2022, 11, 18, 17, 13, 29)
        )
        self.assertIsNotNone(tops_image.file_data)
        self.assertTrue(len(tops_image.file_data) > 0)

class TestTerminologyImport(unittest.TestCase):
    """ Should be deprecated: terminology should come from terminology server. """
    @classmethod
    def setUpClass(cls):
        ArgsCache._args = ArgsCache.get_arguments(test_args=test_args)

        if not database_exists_and_valid():
            init_database()
            logging.info("Database created for testing")

    @classmethod
    def tearDownClass(cls):
        if ":memory:" not in get_full_path_of_database_file():
            os.remove(get_full_path_of_database_file())

    def setUp(self):
        # Start a session for each test
        self.session = get_session()

    def tearDown(self):
        # Rollback changes after each test
        self.session.rollback()
        self.session.close()

    def test_import_terminology(self):
        import_terminology(self.session)

        all_protocols = self.session.query(ScheduledProtocol)
        self.assertEqual(all_protocols.count(), 199)
        self.assertEqual(self.session.query(ScheduledProcedureStep).count(), 0)
        self.assertEqual(self.session.query(RequestedProcedure).count(), 0)

        protocol_iv01 = self.session.query(ScheduledProtocol).filter_by(code_value="IV01").one()
        self.assertIsNotNone(protocol_iv01)
        self.assertEqual(protocol_iv01.code_value, "IV01")
        self.assertEqual(protocol_iv01.code_scheme, "99OPOR")
        self.assertEqual(protocol_iv01.code_meaning, "Intraoral photo, right buccal, centric occlusion")

        protocol_ir9 = self.session.query(ScheduledProtocol).filter_by(code_value="ir9").one()
        self.assertIsNotNone(protocol_ir9)
        self.assertEqual(protocol_ir9.code_value, "ir9")
        self.assertEqual(protocol_ir9.code_scheme, "99DEYE")
        self.assertEqual(protocol_ir9.code_meaning, "incisors right from 90°")
