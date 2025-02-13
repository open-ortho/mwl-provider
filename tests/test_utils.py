import unittest
from datetime import date, time, timezone, timedelta
from pydicom.dataset import Dataset
from mwl_provider.dicom.utils import find_modalities, find_start_end_datetimes
from mwl_provider import logger

from tests import make_sample_MWL

class TestUtils(unittest.TestCase):

    def test_find_start_end_datetimes(self):
        # 1. Test with valid date and time (start and end)
        ds = Dataset()
        sds = Dataset()
        sds.ScheduledProcedureStepStartDate = '20230724-20230725'
        sds.ScheduledProcedureStepStartTime = '110000-120000'
        ds.ScheduledProcedureStepSequence = [] 
        ds.ScheduledProcedureStepSequence.append(sds)
        found_dates = find_start_end_datetimes(ds)
        self.assertEqual(found_dates, 
                         ((date(2023, 7, 24), date(2023, 7, 25)), 
                          (time(11, 0, 0, tzinfo=timezone.utc), time(12, 0, 0, tzinfo=timezone.utc))))

        # 2. Test with valid start date and time but no end
        ds.ScheduledProcedureStepStartDate = '20230724'
        ds.ScheduledProcedureStepStartTime = '110000'
        found_dates = find_start_end_datetimes(ds)
        self.assertEqual(found_dates, 
                         ((date(2023, 7, 24), date(2023, 7, 24)), 
                          (time(11, 0, 0, tzinfo=timezone.utc), time(11, 0, 0, tzinfo=timezone.utc))))

        # 3. Test with valid date range but full-day time (no specific time)
        ds.ScheduledProcedureStepStartDate = '20230724-20230725'
        ds.ScheduledProcedureStepStartTime = None
        found_dates = find_start_end_datetimes(ds)
        self.assertEqual(found_dates, 
                         ((date(2023, 7, 24), date(2023, 7, 25)), 
                          (None, None)))

        # 4. Test with only start date (no time)
        ds.ScheduledProcedureStepStartDate = '20230724'
        ds.ScheduledProcedureStepStartTime = None
        found_dates = find_start_end_datetimes(ds)
        self.assertEqual(found_dates, 
                         ((date(2023, 7, 24), date(2023, 7, 24)), 
                          (None, None)))

        # 5. Test with no start date and only start time (should return today with provided time)
        ds = Dataset()
        ds.ScheduledProcedureStepStartDate = ''
        ds.ScheduledProcedureStepStartTime = '110000'
        found_dates = find_start_end_datetimes(ds)
        self.assertEqual(found_dates, 
                         ((None, None), 
                          (time(11, 0, 0, tzinfo=timezone.utc), time(11, 0, 0, tzinfo=timezone.utc))))

        # 6. Test with no start date or time (should return today with full-day time range)
        ds = Dataset()
        # del ds.ScheduledProcedureStepStartDate = None
        # del ds.ScheduledProcedureStepStartTime = None
        found_dates = find_start_end_datetimes(ds)
        self.assertEqual(found_dates, 
                         ((None, None), 
                          (None, None)))

        # 7. Test with start date range but no time (default to full-day time range)
        ds = Dataset()
        ds.ScheduledProcedureStepStartDate = '20230724-20230730'
        ds.ScheduledProcedureStepStartTime = None
        found_dates = find_start_end_datetimes(ds)
        self.assertEqual(found_dates, 
                         ((date(2023, 7, 24), date(2023, 7, 30)), 
                          (None, None)))

        # 8. Test with no date, but valid time range (should return today with valid time range)
        ds = Dataset()
        ds.ScheduledProcedureStepStartDate = ''
        ds.ScheduledProcedureStepStartTime = '110000-140000'
        found_dates = find_start_end_datetimes(ds)
        self.assertEqual(found_dates, 
                         ((None, None), 
                          (time(11, 0, 0, tzinfo=timezone.utc), time(14, 0, 0, tzinfo=timezone.utc))))

        # 9. Test with valid date range and time range with open-ended time ('110000-' means from 11 AM onward)
        ds.ScheduledProcedureStepStartDate = '20230724-20230725'
        ds.ScheduledProcedureStepStartTime = '110000-'
        found_dates = find_start_end_datetimes(ds)
        self.assertEqual(found_dates, 
                         ((date(2023, 7, 24), date(2023, 7, 25)), 
                          (time(11, 0, 0, tzinfo=timezone.utc), None)))

        # 10. Test with valid date range and time range with open-ended date ('-20230725' means all prior dates)
        ds.ScheduledProcedureStepStartDate = '-20230725'
        ds.ScheduledProcedureStepStartTime = '110000'
        found_dates = find_start_end_datetimes(ds)
        self.assertEqual(found_dates, 
                         ((None, date(2023, 7, 25)), 
                          (time(11, 0, 0, tzinfo=timezone.utc), time(11, 0, 0, tzinfo=timezone.utc))))

        # 11. Test with valid date range and time range ('-' for both date and time should return the entire range)
        ds.ScheduledProcedureStepStartDate = '20230724-'
        ds.ScheduledProcedureStepStartTime = '110000-'
        found_dates = find_start_end_datetimes(ds)
        self.assertEqual(found_dates, 
                         ((date(2023, 7, 24), None), 
                          (time(11, 0, 0, tzinfo=timezone.utc), None)))

        # 12. Test with invalid date (ensure it raises ValueError)
        ds = Dataset()
        ds.ScheduledProcedureStepStartDate = 'invalid_date'
        ds.ScheduledProcedureStepStartTime = '110000'

        # Ensure ValueError is raised when an invalid date is encountered
        with self.assertRaises(ValueError):
            found_dates = find_start_end_datetimes(ds)

        # 13. Test with timezone offset
        ds = Dataset()
        ds.ScheduledProcedureStepStartDate = '20230724'
        ds.ScheduledProcedureStepStartTime = '110000'
        ds.TimezoneOffsetFromUTC = '+0200'
        found_dates = find_start_end_datetimes(ds)
        self.assertEqual(found_dates, 
                         ((date(2023, 7, 24), date(2023, 7, 24)), 
                          (time(11, 0, 0, tzinfo=timezone(timedelta(hours=2))), 
                           time(11, 0, 0, tzinfo=timezone(timedelta(hours=2))))))


    def test_find_modalities(self):
        ds = make_sample_MWL()
        modalities = find_modalities(ds)
        self.assertEqual(modalities,['CR'])
