import os
import re
import sys
import glob
import time
import shutil
import pickle
import datetime
import psycopg2
import numpy as np
import pandas as pd

from . import file_utils
from . import file_settings

try:
    import pgutils
except ModuleNotFoundError:
    sys.path.append('../../../_projects-gh/pgutils/')
    import pgutils


class Activity(object):

    # message types required in raw FIT data
    required_message_names = ['file_id', 'device_info', 'session', 'event', 'record']


    def __init__(
        self, 
        source, 
        db_data=None, 
        fit_data=None, 
        db_metadata=None,
        strava_metadata=None, 
        manual_metadata=None):

        '''
        Processing methods for a single activity
        
        Parameters
        ----------
        source : 'local' or 'db'
        fit_data : the parsed data from a single FIT file
                   as a dict of dataframes keyed by message name
        db_data : raw data retrieved from a cypy2 database
        strava_metadata : optional strava-related metadata
        manual_metadata : optional manually-defined metadata (currently unused)

        TODO: decide on format/structure of db_data

        TODO: decide on what the 'core' raw and processed data consists of,
        regardless of whether we start from raw FIT-file data or data from the database

        Public API
        ----------
        # generated/organized metadata
        self.metadata
        
        # summary statistics - either calculated or from the 'session' message     
        self.summary(type='device|calculated')
        
        # pauses either inferred from the timeseries or derived from device event data
        self.pauses(dtype='device|inferred')

        # time-series data from FIT file record messages
        self.timeseries(dtype='raw|processed')
        
        '''

        if fit_data is None and db_data is None:
            raise ValueError('Either fit_data or db_data must be provided')

        assert(source in ['local', 'db'])
        self.source = source

        # only one of db_data and raw_metadata should be not None
        self._db_data = db_data
        self._fit_data = fit_data

        # only one 'type' of metadata here should be not None
        self._db_metadata = db_metadata
        self._strava_metadata = strava_metadata
        self._manual_metadata = manual_metadata

        # initialize from raw FIT-file data
        if source=='local':

            # generate/infer/organize metadata
            self.metadata = self._generate_metadata()

            # various consistency checks
            self._validate_fit_data()

            # organize the raw data by summary, pauses, and timeseries
            self._parse_fit_data(fit_data)

        # initialize from raw database data
        # TODO: is there a need for data validation here?
        # TODO: can we assume db_metadata is identical to self.metadata?
        if source=='db':
            self._load_db_data(db_metadata, db_data)


    @classmethod
    def from_fit(cls, filepath):
        '''
        Initialize directly from a FIT file

        **intended for testing only**
        note that fit_data will not have a 'strava_metadata' key

        '''
        data = file_utils.parse_fit(filepath)
        activity = cls(source='local', fit_data=data)
        return activity


    @classmethod
    def from_strava_export(cls, data):
        '''
        Initialize from the parsed data cached by managers.StravaExportManager
        
        Usage: 
            manager = StravaExportManager(root, from_cache=True)
            activity = Activity.from_strava_export(data=manager.parsed_data[ind])

        '''
        metadata = data['strava_metadata']
        activity = cls(source='local', fit_data=data, strava_metadata=metadata)
        return activity


    @classmethod
    def from_db(cls, conn, activity_id, load=None):
        '''
        Initialize from the raw and maybe processed data from a cypy2 database

        TODO: decide whether the data can include previously-processed data
        
        load : 'raw', 'processed', or 'all'
        '''
        activity = cls(source='db', db_data=data)
        return activity


    def to_db(self, conn):
        '''
        Insert the activity's data into a cypy2 database
        
        conn : psycopg2 connection to the database

        '''

        activity_id = self.metadata['activity_id']

        # ------------------------------------------------------------------------------------
        #
        #  metadata
        #
        # ------------------------------------------------------------------------------------
        metadata_column_map = {
            'power_flag': 'power_meter_flag', 
            'speed_flag': 'speed_sensor_flag', 
            'heart_rate_flag': 'heart_rate_monitor_flag'
        }

        # metadata as a (one-row) DataFrame so we can use pgutils.dataframe_to_table
        # TODO: decide how to handle database errors
        metadata = pd.DataFrame(data=[self.metadata]).rename(columns=metadata_column_map)
        try:
            pgutils.dataframe_to_table(conn, 'metadata', metadata, raise_errors=True)
            conn.commit()
        except psycopg2.Error as error:
            print('Error inserting metadata: %s' % error)
            return

        # ------------------------------------------------------------------------------------
        #
        #  events
        #
        # ------------------------------------------------------------------------------------
        events = self.events()
        pgutils.dataframe_to_table(conn, 'events', events, raise_errors=False)
        conn.commit()


        # ------------------------------------------------------------------------------------
        #
        #  summary
        #
        # ------------------------------------------------------------------------------------

        # device summary (i.e., the 'session' message)
        # summary = self.summary(summary_type='device')


        # ------------------------------------------------------------------------------------
        #
        #  records
        #
        # ------------------------------------------------------------------------------------
        # create new row in timepoints with activity_id
        pgutils.insert_value(conn, 'timepoints', 'activity_id', activity_id)
        conn.commit()

        columns = pgutils.get_column_names(conn, 'timepoints')
        record = self._fit_data['record'].rename(columns={'timestamp': 'timepoint'})

        # note that update_value will overwrite any existing values
        for column in columns:
            if column in record.columns:
                pgutils.update_value(
                    conn,
                    table='timepoints', 
                    column=column,
                    value=record[column], 
                    selector=('activity_id', activity_id))

        conn.commit()



    @staticmethod
    def id_from_fit(filepath=None, file_id=None):
        '''
        Generate a unique activity_id from a FIT file,
        using the timestamp in the FIT file's file_id message

        Parameters
        ----------
        filepath : path to a FIT file
        file_id : file_id message as a pandas DataFrame (with a single row) or Series
        
        '''
        if filepath is not None:
            fitfile = file_utils.open_fit(filepath)
            fields = {f.name: f.value for f in next(fitfile.get_messages('file_id')).fields}
            file_id = pd.DataFrame([fields])

        if isinstance(file_id, pd.DataFrame):
            assert(file_id.shape[0]==1)
            file_id = file_id.iloc[0]
        elif isinstance(file_id, pd.Series):
            pass
        else:
            raise ValueError('file_id must be a series or a dataframe')

        timestamp = file_id.time_created
        activity_id = timestamp.strftime('%Y%m%d%H%M%S')
        return activity_id


    def _generate_metadata(self):
        '''
        Generate metadata from the raw data
        For now, we assume the raw data is from a parsed FIT file

        Columns:        
            - activity_id
            - activity type
            - cycling type (indoor/road)
            - FIT file timestamp
            - strava timestamp, title, gear
            - GPS device make/model
            - HRM, power meter, and speed sensor flags

        '''

        # map from FIT-like activity types to strava-like activity types
        activity_type_map = {
            'hiking': 'hike',
            'running': 'run',
            'cycling': 'ride',
            'indoor_cycling': 'indoor',
        }

        def _df_to_series(df):
            if df is None: return None
            assert(df.shape[0]==1)
            return df.iloc[0]

        def _clean_string(val):
            if pd.isna(val): return None
            return str(val).lower().replace(' ', '-')


        # message types we need (we can assume all exist, except for 'sport')
        d = self._fit_data
        file_id, device_info, session, sport = \
            d.get('file_id'), d.get('device_info'), d.get('session'), d.get('sport')

        # column renaming in device_info
        device_info.rename(columns={'garmin_product': 'product_name'}, inplace=True)

        # column renaming in file_id
        # nb this is a bit dangerous, because we are assuming that the 'product' column
        # only appears in Wahoo (e.g., non-Garmin) file_id messages;
        file_id.rename(columns={'garmin_product': 'product_name', 'product': 'product_name'}, inplace=True)

        # there should always be only one message (row) for these message types
        file_id, session = _df_to_series(file_id), _df_to_series(session)

        # strava metadata as a series for convenience (it always has one row by definition)
        strava_metadata = _df_to_series(self._strava_metadata)

        # ------------------------------------------------------------------------------------
        #
        # initialize metadata with activity_id and file_id timestamp
        #
        # ------------------------------------------------------------------------------------
        metadata = {
            'activity_id': self.id_from_fit(file_id=file_id),
            'file_date': str(file_id.time_created),
        }

        # copy some fields directly from strava metadata
        if strava_metadata is not None:
            metadata.update({
                'strava_date': strava_metadata['date'],
                'strava_title': strava_metadata['name'],
                'filename': strava_metadata['filename'],
            })

        # ------------------------------------------------------------------------------------
        #
        # activity type from either strava metadata or 'sport' field of 'session' message
        # (session.sport is always 'cycling', 'running', or 'hiking')
        #
        # ------------------------------------------------------------------------------------
        if strava_metadata is not None:
            activity_type = strava_metadata.type.lower()
        else:
            activity_type = activity_type_map[session.sport.lower()]
        metadata['activity_type'] = activity_type


        # ------------------------------------------------------------------------------------
        #
        # cycling type from 'sport' message and bike name from strava metadata
        #
        # Note that 'sport' messages *can* have more than one row, ergo the defensive .iloc[0]
        # (so far, this is the case only for 'hiking' activities)
        #
        # ------------------------------------------------------------------------------------ 
        cycling_type, bike_name = None, None
        if activity_type=='ride':
            cycling_type = 'road'
            if sport is not None and sport.iloc[0].sub_sport=='indoor_cycling':
                cycling_type = 'indoor'

            if strava_metadata is not None:
                bike_name = _clean_string(strava_metadata['gear'])

        metadata['cycling_type'] = cycling_type
        metadata['bike_name'] = bike_name


        # ------------------------------------------------------------------------------------
        #
        # device manufacturer and model from file_id
        #
        # ------------------------------------------------------------------------------------
        device_manufacturer = file_id.manufacturer
        if device_manufacturer not in ['garmin', 'wahoo_fitness']:
            print('Warning: unexpected device manufacturer %s' % device_manufacturer)

        if device_manufacturer=='garmin':
            device_model = file_id.product_name

        # hard-coded device model for Wahoo
        if device_manufacturer=='wahoo_fitness':
            device_model = 'elemnt'

        # simplify names
        device_model = 'fenix3' if device_model=='fenix3_hr' else device_model
        device_manufacturer = 'wahoo' if device_manufacturer=='wahoo_fitness' else device_manufacturer

        # check device model
        if device_model not in ['elemnt', 'fr220', 'edge520', 'fenix3']:
            print('Warning: unexpected device model %s' % device_model)

        metadata['device_model'] = device_model
        metadata['device_manufacturer'] = device_manufacturer


        # ------------------------------------------------------------------------------------
        #
        # sensor flags (true when the sensor is present) from device_info
        #
        # Note that using the 'antplus_device_type' column is likely the most robust way
        # of determining which sensors where present, since its values appear to be
        # device-independent. 
        #
        # Notably, the names appearing in the 'product_name' column are not reliable;
        # for example, between 2016-04-23 and 2016-06-17, files from the Edge 520 
        # have no HRM-like value in that column, despite having a row with 'heart_rate'
        # in 'antplus_device_type' as well as a 'heart_rate' column in the record messages.
        #
        # ------------------------------------------------------------------------------------
        hrm_flag, power_flag, speed_flag = False, False, False

        if 'antplus_device_type' in device_info.columns:
            device_types = [s.lower() for s in device_info.antplus_device_type.apply(str).unique()]
            hrm_flag = 'heart_rate' in device_types
            power_flag = 'bike_power' in device_types
            speed_flag = 'bike_speed' in device_types

        metadata.update({
            'heart_rate_flag': hrm_flag, 
            'power_flag': power_flag, 
            'speed_flag': speed_flag
        })
        

        return metadata



    def _validate_fit_data(self):
        '''
        Check the integrity of raw (FIT-file) data
        
        - check that 'core' message types are present
        - 
        '''

        activity_id = self.metadata['activity_id']

        # check that we have timeseries data for the expected sensors
        # (there is always speed data, with or without a sensor)
        for sensor in ['heart_rate', 'power']:

            # skip fenix3 because it has a built-in HRM
            if sensor=='heart_rate' and self.metadata['device_model']=='fenix3':
                continue

            flag = sensor in self._fit_data['record'].columns
            if self.metadata['%s_flag' % sensor] and not flag:
                print('Warning: activity %s has %s sensor but no records' % (activity_id, sensor))
            if not self.metadata['%s_flag' % sensor] and flag:
                print('Warning: activity %s has %s records but no sensor' % (activity_id, sensor))
        


    def _parse_fit_data(self, fit_data):
        '''
        Parse/organize raw data when self.source=='local'

        '''
        pass


    def data(self, dtype=None, columns=None):
        '''
        '''
        pass


    def process(self):
        '''
        '''
        pass



    def summary(self):
        '''
        Summary statistics
        '''
        pass


    def events(self):

        events = self._fit_data['event'].copy()

        # for now, keep only the event_type and time columns for 'timer' events (starts and stops)
        events = events.loc[events.event=='timer'][['event_type', 'timestamp']]

        # column names for database
        events = events.rename(columns={'timestamp': 'event_time'})

        events['activity_id'] = self.metadata['activity_id']

        # 'stop_all' to 'stop', etc
        events.replace(to_replace=re.compile('stop(.*)$'), value='stop', inplace=True)
        events.replace(to_replace=re.compile('start(.*)$'), value='start', inplace=True)

        return events