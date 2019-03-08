import os
import re
import sys
import glob
import time
import shutil
import pickle
import datetime
import numpy as np
import pandas as pd

from . import file_utils
from . import file_settings


class Activity(object):

    # message types required in raw FIT data
    required_message_names = ['file_id', 'device_info', 'session', 'event', 'record']


    def __init__(
        self, 
        source, 
        db_data=None, 
        raw_data=None, 
        db_metadata=None,
        strava_metadata=None, 
        manual_metadata=None):

        '''
        Processing methods for a single activity
        
        Parameters
        ----------
        source : 'local' or 'db'
        raw_data : parsed raw data, as a dict of dataframes keyed by message name,
                   corresponding to a single FIT file (if source=='local')
        db_data : raw data retrieved from a cypy2 database (if source=='db')
        strava_metadata : optional strava-related metadata
        manual_metadata : optional manually-defined metadata

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

        if raw_data is None and db_data is None:
            raise ValueError('Either raw_data or db_data must be provided')

        assert(source in ['local', 'db'])
        self.source = source

        # only one of db_data and raw_metadata should be not None
        self._db_data = db_data
        self._raw_data = raw_data

        # only one 'type' of metadata here should be not None
        self._db_metadata = db_metadata
        self._strava_metadata = strava_metadata
        self._manual_metadata = manual_metadata

        # initialize from raw FIT-file data
        if source=='local':
            self._validate_raw_data()

            # generate/infer/organize metadata
            self.metadata = self._generate_metadata()

            # organize the raw data by summary, pauses, and timeseries
            self._parse_raw_data(raw_data)

        # initialize from raw database data
        # TODO: is there a need for data validation here?
        # TODO: can we assume db_metadata is identical to self.metadata?
        if source=='db':
            self._load_db_data(db_metadata, db_data)


    @classmethod
    def from_fit(cls, filepath, metadata=None):
        '''
        Initialize directly from a FIT file

        Intended for testing only;
        note that raw_data will not have a 'strava_metadata' key

        '''
        data = file_utils.parse_fit(filepath)
        activity = cls(source='local', raw_data=data, manual_metadata=metadata)
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
        activity = cls(source='local', raw_data=data, strava_metadata=metadata)
        return activity


    @classmethod
    def from_db(cls, data):
        '''
        Initialize from raw and maybe processed data from cypy2 database

        TODO: decide whether the data can include previously-processed data

        '''
        activity = cls(source='db', db_data=data)
        return activity



    @staticmethod
    def id_from_fit(filepath=None, file_id=None):
        '''
        Generate a unique activity_id from a FIT file

        Uses the timestamp in the FIT file's file_id message

        Parameters
        ----------
        filepath : path to a FIT file
        file_id : file_id message as a pandas dataframe
        
        '''
        if filepath is not None:
            fitfile = file_utils.open_fit(filepath)
            file_id = next(fitfile.get_messages('file_id'))
            file_id = pd.DataFrame([{f.name: f.value for f in file_id.fields}])

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
            - FIT file timestamp
            - strava timestamp, title, gear
            - cycling type (indoor/road)
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
        d = self._raw_data
        file_id, device_info, session, sport = \
            d.get('file_id'), d.get('device_info'), d.get('session'), d.get('sport')

        # column renaming in device_info
        device_info.rename(columns={'garmin_product': 'product_name'}, inplace=True)

        # column renaming in file_id
        # nb this is a bit dangerous, because we are assuming that the 'product' column
        # only appears in Wahoo (e.g., non-Garmin) file_id messages;
        file_id.rename(columns={'garmin_product': 'product_name', 'product': 'product_name'}, inplace=True)

        # there should always be only one message of these types
        file_id, session = _df_to_series(file_id), _df_to_series(session)

        # strava metadata as a series for convenience
        strava_metadata = _df_to_series(self._strava_metadata)

        # ------------------------------------------------------------------------------------
        #
        # initialize metadata with activity_id and the file_id timestamp
        #
        # ------------------------------------------------------------------------------------
        metadata = {}
        metadata['activity_id'] = self.id_from_fit(file_id=file_id)
        metadata['file_date'] = str(file_id.time_created)


        # ------------------------------------------------------------------------------------
        #
        # from strava metadata, if we have it,
        # we get the activity type and then keep the name/date/filename/gear
        #
        # ------------------------------------------------------------------------------------
        if strava_metadata is not None:
            activity_type = strava_metadata.type.lower()

            strava_metadata = {
                'date': strava_metadata['date'],
                'title': strava_metadata['name'],
                'filename': strava_metadata['filename'],
                'gear': _clean_string(strava_metadata['gear']),
            }

        # without strava, we get activity type from session.sport, 
        # which is always 'cycling', 'running', or 'hiking'
        else:
            activity_type = activity_type_map[session.sport.lower()]


        # ------------------------------------------------------------------------------------
        #
        # cycling type from 'sport' message, if it exists
        # 
        # Note that sport *can* have more than one row, ergo the defensive .iloc[0]
        # (so far, this is the case only for 'hiking' activities)
        #
        # ------------------------------------------------------------------------------------ 
        cycling_type = None
        if activity_type=='ride':
            cycling_type = 'road'
            if sport is not None and sport.iloc[0].sub_sport=='indoor_cycling':
                cycling_type = 'indoor'


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


        # ------------------------------------------------------------------------------------
        #
        # sensor flags from device_info
        #
        # ------------------------------------------------------------------------------------
        # defensive lowercase
        manufacturers = [s.lower() for s in device_info.manufacturer.unique() if isinstance(s, str)]
        product_names = [s.lower() for s in device_info.product_name.unique() if isinstance(s, str)]

        power_flag, speed_flag, hrm_flag = False, False, False

        # garmin (note that power meter is only indicated by '4iiii' in manufacturers)
        if device_manufacturer=='garmin' and 'hrm3ss' in product_names:
                hrm_flag = True
        if device_manufacturer=='garmin' and 'bsm' in product_names:
                speed_flag = True
        if device_manufacturer=='garmin' and '4iiiis' in manufacturers:
                power_flag = True

        # wahoo
        if device_manufacturer=='wahoo' and 'heartrate' in product_names:
                hrm_flag = True
        if device_manufacturer=='wahoo' and 'power' in product_names:
                power_flag = True
        if device_manufacturer=='wahoo' and 'speed' in product_names:
                speed_flag = True  

        
        flags = {'hrm': hrm_flag, 'power': power_flag, 'speed': speed_flag}
        values = activity_type, cycling_type, device_manufacturer, device_model, flags, strava_metadata
        attrs = 'activity_type', 'cycling_type', 'device_manufacturer', 'device_model', 'flags', 'strava'

        for attr, value in zip(attrs, values):
            metadata[attr] = value

        return metadata



    def _validate_raw_data(self):
        '''
        Check the integrity of raw (FIT-file) data
        
        - check that 'core' message types are present
        - 
        '''

        pass


    def _parse_raw_data(self, raw_data):
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
