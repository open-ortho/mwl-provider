"""The DICOM server
"""
from pynetdicom import AE, evt, debug_logger, ALL_TRANSFER_SYNTAXES
from pynetdicom.sop_class import ModalityWorklistInformationFind, VLPhotographicImageStorage,Verification

from mwl_provider import DEFAULT_AET, DEFAULT_PORT, DEFAULT_LISTEN, logger
from mwl_provider.dicom.dicom_c_find import C_Find
from mwl_provider.args_cache import ArgsCache

from mwl_provider import logger
# debug_logger()

class SCP():
    """ docstring
    """

    _application_entity = None

    def __init__(self):
        self.args = ArgsCache.get_arguments()
        self._application_entity = AE(ae_title=DEFAULT_AET)
        self._application_entity.add_supported_context(
            abstract_syntax=ModalityWorklistInformationFind
        )
        # Add support for Verification SOP Class
        self._application_entity.add_supported_context(Verification)
 
        c_find = C_Find()
        self._handlers = [
            (evt.EVT_C_FIND, c_find.handler),
            (evt.EVT_C_ECHO, self.handle_echo)
        ]

    def handle_echo(self, event):
        """Handle a C-ECHO request."""
        scu_aet = event.assoc.requestor.ae_title
        scu_ip = event.assoc.requestor.address
        logger.debug(f"C-ECHO request from AET: {scu_aet}, IP: {scu_ip}")
        return 0x0000  # Success Status


    def start(self):
        logger.info("Starting DICOM server on %s:%s", self.args.listen, self.args.port)
        if self.args.listen == '*':
            self.args.listen = ''
        try:
            self._application_entity.start_server(
                (str(self.args.listen), int(self.args.port)),
                block=True,
                evt_handlers=self._handlers)
        except Exception as e:
            logger.error(e)

    def stop(self):
        self._application_entity.shutdown()
