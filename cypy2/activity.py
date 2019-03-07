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
        raw_data=None, 
        db_data=None, 
        strava_metadata=None, 
        manual_metadata=None):

        '''
        Processing methods for a single activity
        
        Parameters
        ----------
        source : whether the data is parsed from a local file or retrieved from a database
        raw_data : parsed raw data, as a dict of dataframes keyed by message name,
                   corresponding to a single FIT file
        db_data : raw data retrieved from a cypy2 database
        strava_metadata : optional strava-related metadata
        manual_metadata : optional manually-defined metadata

        TODO: decide on format/structure of db_data

        '''

        if raw_data is None and db_data is None:
            raise ValueError('Either raw_data or db_data must be provided')

        assert(source in ['local', 'db'])
        self.source = source

        self._raw_data = raw_data
        self._db_data = db_data

        if source=='local':
            self._validate_raw_data()
            self._generate_metadata()


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
        metadata = data.pop('strava_metadata')
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


    def _validate_raw_data(self):
        '''
        Check the integrity of raw (FIT-file) data
        
        - check that 'core' message types are present
        - 
        '''

        pass


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

        assert(isinstance(file_id, pd.DataFrame))
        assert(file_id.shape[0]==1)

        timestamp = file_id.iloc[0].time_created
        activity_id = timestamp.strftime('%Y%m%d%H%M%S')
        return activity_id


    def _generate_metadata(self):
        '''
        Generate metadata from the raw (FIT-file) data
        '''
        
        metadata = {}
        d = self._raw_data

        metadata['activity_id'] = self.id_from_fit(file_id=d['file_id'])

        return metadata



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
