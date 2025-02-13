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
            procedure_type_prefix=os.getenv('TD_PROCEDURE_TYPE_PREFIX', None),

            # The limit of search results when a query is run. The system is not too efficient, so keeping this limit below 100 is important.
            limit=os.getenv('TD_LIMIT', 100),

            # If set to True, this will also save to local .dcm file the produced MWL.
            save_mwl=bool(strtobool(os.getenv('TD_SAVE_MWL', 'False'))),

            # When importing with topsdcmimport, setting to True will keep the existing procedures. False will wipe everything and start fresh.
            keep_procedures=bool(
                strtobool(os.getenv('TD_KEEP_PROCEDURES', 'True'))),

            # The path of the SQLite DB file for the local mapping.
            database_file=os.getenv('TD_DATABASE_FILE', SQLITE3_DB),

            # Needs to be set to True for the /admin web server (configurator UI) to run.
            configurator_ui=bool(
                strtobool(os.getenv('TD_CONFIGURATOR_UI', 'False'))),

            # The secret key required for Flask to run properly (used for configurator UI)
            flask_secret_key=os.getenv('TD_FLASK_SECRET_KEY', None),

            # IP and port for the Flask configurator UI server.
            web_listen=os.getenv('TD_WEB_LISTEN', '0.0.0.0'),
            web_port=os.getenv('TD_WEB_PORT', '5000'),

            # The credentials used to connect with topsServer DB
            topsserver_username=os.getenv(
                'TD_TOPSSERVER_USERNAME', DEFAULT_TOPSSERVER_USERNAME),
            topsserver_password=os.getenv('TD_TOPSSERVER_PASSWORD', ''),
            topsserver_ip=os.getenv('TD_TOPSSERVER_IP', '127.0.0.1'),
            topsserver_port=os.getenv('TD_TOPSSERVER_PORT', '5432'),


            # The credentials used to connect with topsServer SFTP 
            topsserver_sftp_username=os.getenv(
                'TD_TOPSSERVER_SFTP_USERNAME', DEFAULT_TOPSSERVER_SFTP_USERNAME),
            topsserver_sftp_host=os.getenv(
                'TD_TOPSSERVER_SFTP_HOST', DEFAULT_TOPSSERVER_SFTP_HOST),
            topsserver_sftp_port=os.getenv(
                'TD_TOPSSERVER_SFTP_PORT', DEFAULT_TOPSSERVER_SFTP_PORT),
            topsserver_sftp_key_type=os.getenv('TD_TOPSSERVER_SFTP_KEY_TYPE', 'rsa'),
            topsserver_sftp_key=os.getenv('TD_TOPSSERVER_SFTP_KEY', None),
            topsserver_sftp_key_filename=os.getenv('TD_TOPSSERVER_SFTP_KEY_FILENAME', None),

            # Needs to be set to True for the DICOM SCP (server) to run and listen for MWLs.
            dicom_scp=bool(strtobool(os.getenv('TD_DICOM_SCP', 'False'))),

            # DICOM SCP Network paramenters for the SCP server.
            listen=os.getenv('TD_LISTEN', DEFAULT_LISTEN),
            port=os.getenv('TD_PORT', DEFAULT_PORT),
            aet=os.getenv('TD_AET', DEFAULT_AET),

            terminology_server_url=os.getenv(
                'TD_TERMINOLOGY_SERVER_URL', DEFAULT_TERMINOLOGY_SERVER_URL),
                
            terminology_target_system_root_url=os.getenv(
                'TD_TERMINOLOGY_TARGET_SYSTEM_ROOT_URL', DEFAULT_TERMINOLOGY_TARGET_SYSTEM_ROOT_URL),

            # Verbosity level: 0=WARNING, 1=INFO, 2=DEBUG
            verbose=int(os.getenv('TD_VERBOSE', 0))
        )
        
        # Debug print what we're returning
        logger.debug(f"ArgsCache loaded with SFTP settings: host={args.topsserver_sftp_host}, "
                    f"port={args.topsserver_sftp_port}, user={args.topsserver_sftp_username}")
        
        return args
