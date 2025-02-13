"""
Test moved from topsserver_db, and still depends on it for the database setup. Should be moved to the tops_dicom tests.
"""
import tempfile
import os
from typing import cast
import unittest
from zoneinfo import ZoneInfo
from topsserver_db_tests import *
from sqlalchemy.orm import sessionmaker
from tops_dicom.dicom.mwl_converter import MWLConverter
from pydicom.dataset import Dataset
from pydicom import dcmwrite

class TestMWLConverter(unittest.TestCase):
    UTC_ZoneInfo = ZoneInfo(key='UTC')

    @classmethod
    def setUpClass(cls) -> None:
        try:
            create_test_db()
            cls.engine = create_engine(SQLALCHEMY_URL_TESTDB)
            # Create the session factory using the engine
            cls.session = scoped_session(sessionmaker(bind=cls.engine))
            # Create all tables in the engine
            setup_data(cls.engine, cls.session)
        except Exception as e:
            drop_test_db()
            raise e

    @classmethod
    def tearDownClass(cls) -> None:
        drop_test_db()

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        self.session.close()

    def test_mwl_converter(self):
        mwl_converter = MWLConverter(session=self.session)
        appointments = mwl_converter.get_appointments_by_date()

        self.assertEqual(appointments.count(),3)

        mwl = mwl_converter.convert(appointments[0])

        mwl = cast(Dataset,mwl)
        print(mwl)
        self.assertEqual(mwl.RequestedProcedureID,'TOPS-1-5173')
        self.assertEqual(mwl.AccessionNumber,'TOPS-1')
        self.assertEqual(mwl.PatientSex,'F')
        spss = mwl.ScheduledProcedureStepSequence[0]
        spss_date = spss.ScheduledProcedureStepStartDate
        self.assertEqual(spss_date,'20230710')
        self.assertEqual(spss.Modality,'')
        self.assertEqual(spss.ScheduledProcedureStepID,'')

        # Save to a temporary file
        with tempfile.NamedTemporaryFile(delete=True) as tmpfile:
            dcmwrite(tmpfile.name, mwl)

            # Ensure file exists and has content
            self.assertTrue(os.path.exists(tmpfile.name))
            self.assertGreater(os.path.getsize(tmpfile.name), 0)
