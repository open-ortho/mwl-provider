""" Configuration and variables.

Class to get options from env variables.

Argparse support was purposely removed, because it was creating too much trouble with unittests, and too much overhead. Arguments can be just as easily passed as env vars, and since this is a server, not a tool to be used every day, arguments should not be necessary anyways.

"""
import os
from distutils.util import strtobool
from mwl_provider import logger
from mwl_provider.constants import (
    SQLITE3_DB,
    DEFAULT_LISTEN,
    DEFAULT_PORT,
    DEFAULT_AET,
    DEFAULT_TERMINOLOGY_SERVER_URL,
    DEFAULT_TERMINOLOGY_TARGET_SYSTEM_ROOT_URL,
)


class Namespace:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class ArgsCache:
    _args = None

    @staticmethod
    def get_arguments(test_args=None):
        if test_args is not None:
            return Namespace(**test_args)
        if ArgsCache._args is None:
            ArgsCache._args = ArgsCache.load_arguments()
        return ArgsCache._args

    @staticmethod
    def load_arguments():
        args = Namespace(
            # The prefix to use when searching for and importing procedure_types from topsdb. Can be something like the camera emoji.
            procedure_type_prefix=os.getenv('MP_PROCEDURE_TYPE_PREFIX', None),

            # The limit of search results when a query is run. The system is not too efficient, so keeping this limit below 100 is important.
            limit=os.getenv('MP_LIMIT', 100),

            # If set to True, this will also save to local .dcm file the produced MWL.
            save_mwl=bool(strtobool(os.getenv('MP_SAVE_MWL', 'False'))),

            # When importing with topsdcmimport, setting to True will keep the existing procedures. False will wipe everything and start fresh.
            keep_procedures=bool(
                strtobool(os.getenv('MP_KEEP_PROCEDURES', 'True'))),

            # The path of the SQLite DB file for the local mapping.
            database_file=os.getenv('MP_DATABASE_FILE', SQLITE3_DB),

            # Needs to be set to True for the /admin web server (configurator UI) to run.
            configurator_ui=bool(
                strtobool(os.getenv('MP_CONFIGURATOR_UI', 'False'))),

            # The secret key required for Flask to run properly (used for configurator UI)
            flask_secret_key=os.getenv('MP_FLASK_SECRET_KEY', None),

            # IP and port for the Flask configurator UI server.
            web_listen=os.getenv('MP_WEB_LISTEN', '0.0.0.0'),
            web_port=os.getenv('MP_WEB_PORT', '5000'),

            # Needs to be set to True for the DICOM SCP (server) to run and listen for MWLs.
            dicom_scp=bool(strtobool(os.getenv('MP_DICOM_SCP', 'False'))),

            # DICOM SCP Network paramenters for the SCP server.
            listen=os.getenv('MP_LISTEN', DEFAULT_LISTEN),
            port=os.getenv('MP_PORT', DEFAULT_PORT),
            aet=os.getenv('MP_AET', DEFAULT_AET),

            terminology_server_url=os.getenv(
                'MP_TERMINOLOGY_SERVER_URL', DEFAULT_TERMINOLOGY_SERVER_URL),
                
            terminology_target_system_root_url=os.getenv(
                'MP_TERMINOLOGY_TARGET_SYSTEM_ROOT_URL', DEFAULT_TERMINOLOGY_TARGET_SYSTEM_ROOT_URL),

            # Verbosity level: 0=WARNING, 1=INFO, 2=DEBUG
            verbose=int(os.getenv('MP_VERBOSE', 0))
        )
        
        # Debug print what we're returning
        logger.debug(f"ArgsCache loaded with SFTP settings: host={args.topsserver_sftp_host}, "
                    f"port={args.topsserver_sftp_port}, user={args.topsserver_sftp_username}")
        
        return args
