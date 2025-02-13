import io
import re
import numpy as np
from datetime import date, datetime, time, timezone, timedelta
from pydicom.dataset import Dataset
from pydicom.pixel_data_handlers.util import apply_voi_lut
from PIL import Image as PILImage

from topsserver_db.binary_files import Image as TopsImage

from tops_dicom.terminology import get_image_type_from_dataset
from tops_dicom import logger

class TopsRequirementsValidationError(ValueError):
    """Raised when a DICOM dataset does not meet the required standards for processing."""
    pass

def dataset_to_str(ds, indent=""):
    # why not just print(ds)? Or return str(ds)?
    str_ds = ""
    if ds:
        for elem in ds:
            if elem.VR == "SQ":
                indent += 4 * " "
                for item in elem:
                    str_ds += dataset_to_str(item, indent)
                indent = indent[4:]
            str_ds += indent + str(elem) + '\n'

    return str_ds


def find_start_end_datetimes(ds: Dataset) -> tuple[tuple[date, date], tuple[time, time]]:
    """
    Look for ScheduledProcedureStepStartDate in Sequence or outside of sequence and return a tuple of (start_date, end_date) and (start_time, end_time).

    The function supports DICOM-style date and time ranges, as follows:

    # If startdate-enddate: The date range is interpreted as a start date and end date. For example, '20230724-20230730' results in (start_date=2023-07-24, end_date=2023-07-30).
    # If startdate-: If only the start date is provided and no end date (e.g., '20230724-'), the function assumes the range starts on that date and extends indefinitely into the future, returning (start_date=2023-07-24, end_date=None).
    # If -enddate: If only the end date is provided (e.g., '-20230730'), the function returns a range that covers all dates up to and including the end date, returning (start_date=None, end_date=2023-07-30).
    # If date: If a single date is provided (e.g., '20230724'), both the start and end date will be the same, returning (start_date=2023-07-24, end_date=2023-07-24).

    The same logic applies for times:
    # If time1-time2: The time range is interpreted as a start time and end time. For example, '110000-140000' results in (start_time=11:00:00, end_time=14:00:00).
    # If time1-: If only the start time is provided (e.g., '110000-'), the function assumes the range starts at the given time and continues through the rest of the day, returning (start_time=11:00:00, end_time=23:59:59).
    # If -time2: If only the end time is provided (e.g., '-140000'), the function assumes all times up to and including the end time, returning (start_time=00:00:00, end_time=14:00:00).
    # If time: If a single time is provided (e.g., '110000'), both the start and end time will be the same, returning (start_time=11:00:00, end_time=11:00:00).

    If the start date or time in the DICOM dataset doesn't have a '-' character or if there is nothing after the '-' character, the function handles it as a single date/time.

    If no TimezoneOffsetFromUTC is found in the dataset, the function defaults to UTC.

    If no date is found in the dataset, the function defaults to today's date for the start date.

    Args:
        ds (Dataset): The DICOM dataset containing dates and times.

    Returns:
        tuple: A tuple of ((from_date, to_date), (from_time, to_time)) for appointments, mapping the DICOM date/time range to Python's `date` and timezone aware `time` objects.
    """

    sps_start_date = None
    sps_start_time = None
    start_date_str = None
    end_date_str = None
    start_time_str = None
    end_time_str = None
    from_date = None
    to_date = None
    from_time = None
    to_time = None

    # Check for start date and time outside the sequence
    if 'ScheduledProcedureStepStartDate' in ds:
        logger.warning(
            "Found ScheduledProcedureStepStartDate outside of ScheduledProcedureStepSequence")
        sps_start_date = ds.ScheduledProcedureStepStartDate
    if 'ScheduledProcedureStepStartTime' in ds:
        logger.warning(
            "Found ScheduledProcedureStepStartTime outside of ScheduledProcedureStepSequence")
        sps_start_time = ds.ScheduledProcedureStepStartTime

    # Check for start date and time inside the sequence
    elif 'ScheduledProcedureStepSequence' in ds:
        step_sequence = ds.ScheduledProcedureStepSequence
        if step_sequence and hasattr(step_sequence[0], 'ScheduledProcedureStepStartDate'):
            logger.debug(
                "Found ScheduledProcedureStepStartDate inside of sequence")
            sps_start_date = step_sequence[0].ScheduledProcedureStepStartDate
        if step_sequence and hasattr(step_sequence[0], 'ScheduledProcedureStepStartTime'):
            logger.debug(
                "Found ScheduledProcedureStepStartTime inside of sequence")
            sps_start_time = step_sequence[0].ScheduledProcedureStepStartTime

    if sps_start_date:
        dates = sps_start_date.split('-')
        if len(dates) == 2:
            start_date_str, end_date_str = dates
        elif len(dates) == 1:
            start_date_str, end_date_str = dates[0], dates[0]

    if start_date_str:
        from_date = datetime.strptime(start_date_str, '%Y%m%d').date()
    if end_date_str:
        to_date = datetime.strptime(end_date_str, '%Y%m%d').date()

    if sps_start_time:
        times = sps_start_time.split('-')
        if len(times) == 2:
            start_time_str, end_time_str = times
        elif len(times) == 1:
            start_time_str, end_time_str = times[0], times[0]

    if start_time_str:
        from_time = datetime.strptime(start_time_str, '%H%M%S').time()
    if end_time_str:
        to_time = datetime.strptime(end_time_str, '%H%M%S').time()

    # Check if there is a timezone in the dataset and use it to make the returned time timezone aware.
    if 'TimezoneOffsetFromUTC' in ds:
        logger.debug("Found TimezoneOffsetFromUTC in the dataset.")
        offset_str = ds.TimezoneOffsetFromUTC
        # Check if the offset is in the correct format ±HHMM
        if re.match(r'^[+-]\d{4}$', offset_str):
            offset_hours = int(offset_str[:3])
            # Keep the sign for minutes
            offset_minutes = int(offset_str[0] + offset_str[3:])
            offset = timezone(
                timedelta(hours=offset_hours, minutes=offset_minutes))
        else:
            logger.warning(
                "TimezoneOffsetFromUTC tag present but not in the correct format ±HHMM: %s. Defaulting to UTC", offset_str)
            offset = timezone.utc
    else:
        logger.debug(
            "No TimezoneOffsetFromUTC in the dataset, defaulting to UTC.")
        offset = timezone.utc

    if from_time:
        from_time = from_time.replace(tzinfo=offset)
    if to_time:
        to_time = to_time.replace(tzinfo=offset)

    return ((from_date, to_date), (from_time, to_time))


def find_modalities(ds: Dataset) -> list:
    """
    Return all the modalities found in the various ScheduledProcedureSteps 
    of this MWL in a list of strings.
    """
    modalities = []

    # Check if the dataset contains the ScheduledProcedureStepSequence
    if 'ScheduledProcedureStepSequence' in ds:
        # Iterate over each ScheduledProcedureStep in the sequence
        for step in ds.ScheduledProcedureStepSequence:
            # Check if 'Modality' exists in the current ScheduledProcedureStep
            if 'Modality' in step:
                modality = step.Modality
                # Add the modality to the list if not already present
                if modality not in modalities:
                    modalities.append(modality)

    return modalities


def make_code_sequence(**code) -> Dataset:
    """
    Generate a DICOM Code Sequence Dataset.

    Parameters:
    - code (dict): Dictionary containing the code information with keys:
        - 'code' (str): The actual code value.
        - 'prefix' (str): Coding scheme designator (e.g., SCT, DCM).
        - 'display' (str): Code meaning, will be truncated to 64 characters if longer.

    Returns:
    Dataset: A DICOM dataset containing the code sequence.

    Example:
    >>> ds = make_code_sequence(code='1234', prefix='DCM', display='Example Code')
    >>> print(ds)
    """
    # Initialize a new Dataset object
    ds = Dataset()

    # Safely extract values from the code dictionary, ensuring no KeyError or TypeError
    ds.CodeValue = code.get('code', '')
    ds.CodingSchemeDesignator = code.get('prefix', '')

    # Truncate the display value to 64 characters to meet DICOM standards
    display_value = code.get('display', '')
    ds.CodeMeaning = display_value[:64] if display_value is not None else ''

    return ds


def make_tops_image_from_dataset(ds: Dataset, config: dict) -> TopsImage:
    """
    Create a TopsImage object from a DICOM dataset and save it to the database.

    Args:
        ds (Dataset): The DICOM dataset containing the image information.
        config (dict): The configuration dictionary containing the topsdb database connection information.

    Raises:
        DicomValidationError: When required DICOM attributes are missing or invalid
    """

    # Extract pixel data and convert to a PIL image
    pixel_array = ds.pixel_array
    pixel_array = apply_voi_lut(pixel_array, ds)
    if ds.PhotometricInterpretation == "MONOCHROME1":
        pixel_array = np.amax(pixel_array) - pixel_array

    image = PILImage.fromarray(pixel_array)

    tops_image = TopsImage(config=config)

    # The AccessionNumber is used to identify the appointment_id, which defines the Progress date.
    if 'AccessionNumber' not in ds:
        raise TopsRequirementsValidationError("DICOM dataset is missing the AccessionNumber tag: Cannot determine appointment_id, which is required to save the image in topsdb. Expected format: 'TOPS-<appointment_id>'.")
    if not ds.AccessionNumber.startswith('TOPS-'):
        raise TopsRequirementsValidationError(f"Invalid AccessionNumber: {ds.AccessionNumber}. Expected format: 'TOPS-<appointment_id>'.")
    tops_image.appointment_id = int(
        ''.join(filter(str.isdigit, ds.AccessionNumber)))

    # Leave None to default to current time
    tops_image.image_created_datetime = None

    # Convert ContentDate (YYYYMMDD) and ContentTime (HHMMSS.FFFFFF) to datetime
    if 'ContentDate' in ds and 'ContentTime' in ds:
        content_date = ds.ContentDate
        content_time = ds.ContentTime.split('.')[0]  # Remove fractional seconds
    elif 'AcquisitionDateTime' in ds:
        content_date = ds.AcquisitionDateTime[:8]
        content_time = ds.AcquisitionDateTime[8:]
    elif 'AcquisitionDate' in ds and 'AcquisitionTime' in ds:
        content_date = ds.AcquisitionDate
        content_time = ds.AcquisitionTime.split('.')[0]
    else:
        raise TopsRequirementsValidationError("DICOM dataset is missing the ContentDate/ContentTime and AcquisitionDateTime and AcquisitionDate/AcquisitionTime tags: Cannot determine the image acquisition datetime.")
    tops_image.image_acquisition_datetime = datetime.strptime(
        content_date + content_time, '%Y%m%d%H%M%S')

    # @TODO Image Type is missing here. This is where i have the DICOM object, so this is where i should take care of it.
    tops_image.image_label_type_id = get_image_type_from_dataset(ds, tops_image.TOPSDB_UUID)
    if tops_image.image_label_type_id is None:
        raise TopsRequirementsValidationError("Failed to determine the image label type ID: the DICOM Dataset probably does contain a ScheduledProtocolCode, but it is in a scheme that is not compatible with this database. Cannot Import.")

    # Convert the image as a JPEG2000 lossless into a bytes stream required by tops-server-db
    with io.BytesIO() as output:
        image.save(output, format='JPEG2000', quality_mode='lossless')
        tops_image.file_data = output.getvalue()

    return tops_image

