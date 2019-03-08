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
from io import StringIO

from . import file_utils
from . import file_settings
from . activity import Activity



class ActivityManager(object):

    def __init__(self, activities):

        self._metadata = pd.DataFrame([a.metadata for a in activities])
        self._activities = activities


    @classmethod
    def from_strava_export(cls, strava_export_manager):

        activities = []
        for ind, d in enumerate(strava_export_manager.parsed_data):
            try:
                activity = Activity.from_strava_export(d)
            except:
                print('Warning: error parsing data at index %s' % ind)

            activities.append(activity)

        return cls(activities)


    @classmethod
    def from_db(cls, conn):
        '''
        load all activities from a cypy2 database
        
        something like this:

        activity_ids = get_all_activity_ids(conn)
        for activity_id in activity_ids:
            activity = Activity.from_db(conn, activity_id)
        
        '''
        pass



    def activities(self, activity_id=None, **kwargs):
        '''
        Filter activities
        '''

        _activities = self._activities
        if activity_id:
            _activities = [a for a in _activities if a.metadata['activity_id'].startswith(activity_id)]

        for key, val in kwargs.items():
            _activities = [a for a in _activities if a.metadata[key]==val]
        return _activities


    def metadata(self, activity_id=None, **kwargs):
        '''
        Filter metadata
        '''

        metadata = self._metadata.copy()
        if activity_id:
            metadata = metadata.loc[metadata.activity_id.apply(str.startswith(activity_id))]

        for key, val in kwargs.items():
            if key in metadata.columns:
                metadata = metadata.loc[metadata[key]==val]

        return metadata






class StravaExportManager(object):

    def __init__(self, root_dirpath, from_cache=False):
        
        self.root_dirpath = root_dirpath
        self.root_dirname = root_dirpath.split(os.sep)[-1]

        # where to cache the parsed data
        self.cache_dirpath = os.path.join(
            os.getenv('HOME'), 
            'parsed-strava-exports', 
            self.root_dirname)

        os.makedirs(self.cache_dirpath, exist_ok=True)

        self.metadata = pd.read_csv(os.path.join(self.root_dirpath, 'activities.csv'))

        if from_cache:
            self.parsed_data = self._load_from_cache(self.cache_dirpath)
        else:
            # for now, we will leave it to the user to call self.parse_all manually
            pass


    @staticmethod
    def _load_from_cache(cache_dirpath):
        '''
        Unpickle cached parsed data
        '''
        filepaths = glob.glob(os.path.join(cache_dirpath, '*.p'))
        filepath = sorted(filepaths)[-1]

        if len(filepaths) > 1:
            print('Warning: multiple pickle files found; loading %s' % filepath.split(os.sep)[-1])

        with open(filepath, 'rb') as file:
            data = pickle.load(file)
        return data


    def parse_all(self):
        '''
        Parse all of the FIT files appearing in the Strava export

        Returns
        -------
        self.parsed_data : list of dicts of dataframes, keyed by message name
        self.parse_errors : list of metadata rows on which file_utils.parse_fit failed

        '''
        data = []
        errors = []
        for ind, row in self.metadata.iterrows():    
            sys.stdout.write('\r%s: %s' % (row.date, row.filename))

            if pd.isna(row.filename) or 'gpx' in row.filename.split('.'):
                continue

            try:
                d = file_utils.parse_fit(os.path.join(self.root_dirpath, row.filename))
            except:
                errors.append(row)
                continue
            
            # use a dataframe here for consistency with message dataframes
            d['strava_metadata'] = pd.DataFrame([row])
            data.append(d)

        self.parsed_data = data
        self.parsing_errors = errors


    def to_cache(self):
        '''
        Pickle and cache the parsed data
        '''
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d')
        filepath = os.path.join(self.cache_dirpath, '%s_all-parsed-fit-files.p' % timestamp)

        if os.path.isfile(filepath):
            print('Warning: cached data already exists')
            return

        with open(filepath, 'wb') as file:
            pickle.dump(self.parsed_data, file)

