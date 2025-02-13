"""The MWL Provider DICOM Listener"""

import sys
import signal
import threading
import logging

from mwl_provider.dicom.dicom_scp import SCP
from mwl_provider.args_cache import ArgsCache
from mwl_provider.constants import verbosity_mapping
from mwl_provider import logger

PROGRAM_VERSION_MESSAGE = "MWL Provider v0.1.0"

def setup_logging(level):
    """Configure root logger for the application"""
    # Configure format for all handlers
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s.%(funcName)s: %(message)s')
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configure the package logger
    logger.setLevel(level)
    logger.addHandler(console_handler)
    
    # Prevent log propagation to prevent duplicate messages
    logger.propagate = False

def run_flask():
    logger.info(f"{PROGRAM_VERSION_MESSAGE}: Request to start Web Configurator.")
    args = ArgsCache.get_arguments()
    from mwl_provider.view_flask_admin import flask_app
    debug = False
    if args.verbose == 2:
        debug = True
    flask_app.run(host=args.web_listen, port=int(args.web_port), debug=debug, use_reloader=False)

def run_pynetdicom():
    logger.info(f"{PROGRAM_VERSION_MESSAGE}: Request to start DICOM SCP.")
    scp = SCP()
    scp.start()


def main():  # IGNORE:C0111
    args = ArgsCache.get_arguments()
    level = verbosity_mapping.get(args.verbose, logging.DEBUG)
    
    setup_logging(level)

    logger.debug(("Logging Level is {}".format(
        logger.getEffectiveLevel())))

    if args.dicom_scp and args.configurator_ui:
        # Thread for Flask
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.start()

        # Thread for pynetdicom
        dicom_thread = threading.Thread(target=run_pynetdicom)
        dicom_thread.start()

        flask_thread.join()
        dicom_thread.join()
    elif args.dicom_scp:
        run_pynetdicom()
    elif args.configurator_ui:
        run_flask()


def sigint_signal_handler(signal, frame):
    '''This will catch a SIGINT or ctrl-C and print what was done so far.'''
    sys.exit(0)


signal.signal(signal.SIGINT, sigint_signal_handler)


class CLIError(Exception):
    '''Generic exception to raise and log different fatal errors.'''

    def __init__(self, msg):
        super(CLIError).__init__(type(self))
        self.msg = "E: %s" % msg

    def __str__(self):
        return self.msg

    def __unicode__(self):
        return self.msg


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
