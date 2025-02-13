import os
import unittest
from mwl_provider.args_cache import ArgsCache
from mwl_provider.model import database_exists_and_valid, init_database, get_session
import logging

from tests import test_args, get_full_path_of_database_file

class TestConfigurator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ArgsCache._args = ArgsCache.get_arguments(test_args=test_args)

        if not database_exists_and_valid():
            init_database()
            logging.info("Database created for testing")

    @classmethod
    def tearDownClass(cls):
        if ":memory:" not in get_full_path_of_database_file:
            os.remove(get_full_path_of_database_file)

    def setUp(self):
        # Start a session for each test
        self.session = get_session()

    def tearDown(self):
        # Rollback changes after each test
        self.session.rollback()
        self.session.close()

    def test_import_module(self):
        from mwl_provider.view_flask_admin import flask_app
