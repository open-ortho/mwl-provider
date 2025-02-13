from logging import DEBUG
from tops_dicom import logger
from tops_dicom.args_cache import ArgsCache
from tops_dicom.constants import CFindStatus
from tops_dicom.model import populate_dataset

from mwl_provider.dicom.mwl_converter import MWLConverter
from mwl_provider.dicom.utils import dataset_to_str, find_start_end_datetimes, find_modalities


class C_Find():

    def __init__(self) -> None:
        self.args = ArgsCache.get_arguments()
        self.db_config = {}
        self.db_config['postgresql'] = {
            'username': self.args.topsserver_username,
            'password': self.args.topsserver_password,
            'host': self.args.topsserver_ip,
            'port': int(self.args.topsserver_port),
        }
        logger.debug(self.db_config)

    def handler(self, event):
        """Handle a C-FIND request event."""
        # Extract the query Dataset
        scu_aet = event.assoc.requestor.ae_title
        scu_ip = event.assoc.requestor.address
        logger.debug(f"Generic C-FIND arrived from {scu_aet}:{scu_ip}.")
        ds = event.identifier

        # Check for the type of find request based on QueryRetrieveLevel or other criteria
        if hasattr(ds, 'QueryRetrieveLevel'):
            if ds.QueryRetrieveLevel == 'WORKLIST':
                logger.debug("Calling MWL C-FIND.")
                yield from self.handle_mwl_find(ds)
                logger.debug("Called MWL C-FIND.")
            elif ds.QueryRetrieveLevel in ['STUDY', 'SERIES', 'IMAGE']:
                logger.debug("Calling IOD C-FIND.")
                yield from self.handle_iod_find(ds)
            else:
                logger.warning("Unsupported QueryRetrieveLevel")
                # Return a failure status if the level is unsupported
                yield (CFindStatus.STATUS_FAILURE, None)
        else:
            logger.debug("No QueryRetrieveLevel. Retrieveing everything.")
            # Return everything if QueryRetrieveLevel is not provided
            yield from self.handle_mwl_find(ds)

    def handle_mwl_find(self, ds):
        """Handle a C-FIND request event.

        This function is called when a C-FIND request is received with QueryRetrieveLevel = 'WORKLIST'.

        If AccessionNumber is present in the dataset, it will be used to generate a MWL for that specific appointment. Any character in the AccessionNumber that is not a digit will be removed.

        If AccessionNumber is not present, the ScheduledProcedureStepStartDate and ScheduledProcedureStepStartTime will be used to generate a MWL for all appointments that match the date and time range. 
        """
        logger.debug("MWL C-FIND has arrived.")
        logger.debug(dataset_to_str(ds))
        if self.args.limit:
            limit = int(self.args.limit)
        else:
            limit = None

        accession_number = None
        search_datetimes = None
        # return [] if none present in the requesting MWL.
        modalities = find_modalities(ds)
        if 'AccessionNumber' in ds and ds.AccessionNumber:
            accession_number = ds.AccessionNumber
        else:
            search_datetimes = find_start_end_datetimes(ds)

        # Create a converter instance and fetch appointments for the given date
        try:
            mwl_converter = MWLConverter(config=self.db_config)
            if accession_number:
                logger.debug(
                    f"Searching for MWLs of appointment_id {accession_number}")
                appointment_id = int(
                    ''.join(filter(str.isdigit, accession_number)))
                appointments = mwl_converter.get_appointments_by_appointment_id(
                    appointment_id=appointment_id).limit(limit)
            else:
                logger.debug(
                    f"Searching for MWLs of date {search_datetimes} for modalities {modalities}")
                appointments = mwl_converter.get_checked_in_appointments_by_date_time_range(
                    date_range=search_datetimes[0],
                    time_range=search_datetimes[1]).limit(limit)

            logger.debug(f"Found {appointments.count()} candidates.")
            for appointment in appointments:
                dicom_mwl = mwl_converter.convert(appointment=appointment)
                logger.debug(
                    f"Appointment {appointment.appointment_id} Converted to MWL")
                dicom_mwl = populate_dataset(dicom_mwl, modalities)
                if dicom_mwl:
                    if self.args.save_mwl:
                        filename = f"{dicom_mwl.SOPInstanceUID}.mwl.dcm"
                        dicom_mwl.save_as(filename)
                        logger.info(f"MWL saved to {filename}")

                    logger.debug(dataset_to_str(dicom_mwl))
                    yield (CFindStatus.STATUS_PENDING, dicom_mwl)
                else:
                    logger.info(
                        f"Nothing to do for appointment with procedure_id {appointment.procedure_id}.")

            # Final yield: success or failure
            # No dataset to send for the final success status
            yield (CFindStatus.STATUS_SUCCESS, None)
        except Exception as e:
            if logger.isEnabledFor(DEBUG):
                logger.exception(e)
            logger.error(e)
            yield (CFindStatus.STATUS_FAILURE, None)
