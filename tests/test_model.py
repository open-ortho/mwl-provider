import os
import unittest

from tops_dicom.model import RequestedProcedure, ScheduledProcedureStep, ScheduledProtocol, ExternalProcedure, Base, get_session, init_database, database_exists_and_valid
from tops_dicom.constants import verbosity_mapping
from tops_dicom.args_cache import ArgsCache
from tops_dicom import logger

from tests import test_args, get_full_path_of_database_file

class TestModel(unittest.TestCase):
    """ Test the model classes 
    
    The new model will have not much here. I had to remove the old tests because they were too specific to the old model.
    """
    @classmethod
    def setUpClass(cls):
        ArgsCache._args = ArgsCache.get_arguments(test_args=test_args)

        if not database_exists_and_valid():
            init_database()
            logger.info("Database created for testing")

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

    def test_model(self):
        pass


if __name__ == '__main__':
    unittest.main()
