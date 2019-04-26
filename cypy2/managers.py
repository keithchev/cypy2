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

from cypy2 import (file_utils, file_settings, dbutils)
from cypy2.activity import (Activity, LocalActivity)



class ActivityManager(object):

    def __init__(self, metadata):

        self._metadata = metadata


    @classmethod
    def from_strava_export(cls, strava_export_manager, raise_errors=False):

        activities = []
        for ind, data in enumerate(strava_export_manager.parsed_data):
            try:
                activity = LocalActivity.from_strava_export(data)
                sys.stdout.write('\r%s' % activity.metadata.activity_id)
                activities.append(activity)
            except Exception as err:
                if raise_errors:
                    raise
                else:
                    print('Warning: error parsing data at index %s:\n%s' % (ind, err))

        metadata = pd.DataFrame([a.metadata for a in activities])
        metadata['activity'] = activities
        return cls(metadata)


    @classmethod
    def from_db(cls, conn, kind=None):
        '''
        Load activity metadata from a cypy2 database, 
        and instantiate activities (if kind='raw' or kind='processed')

        Parameters
        ----------
        kind : None, 'raw', 'processed', or 'all';
            if None, only activity metadata is loaded

        '''

        metadata = dbutils.get_rows(conn, 'metadata')

        metadata['activity'] = None
        for ind, row in metadata.iterrows():

            # attempt to load the activity's data
            if kind is not None:
                sys.stdout.write('\r%s' % row.activity_id)
                try:
                    activity = Activity.from_db(conn, row.activity_id, kind=kind)
                except Exception as error:
                    print('Error loading activity_id %s:\n%s' % (row.activity_id, error))

            # instantiate from the metadata alone
            else:
                activity = Activity(row)

            metadata.at[ind, 'activity'] = activity

        return cls(metadata)


    def activities(self, activity_id=None, func=None, **kwargs):
        '''
        Filter activities
        '''

        metadata = self.metadata(activity_id, **kwargs)
        activities = metadata.activity.values

        if func:
            activities = [a for a in activities if func(a)]

        return list(activities)


    def metadata(self, activity_id=None, **kwargs):
        '''
        Filter metadata
        '''

        metadata = self._metadata.copy()
        if activity_id:
            metadata = metadata.loc[metadata.activity_id.apply(lambda s: s.startswith(activity_id))]

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
        parsed_data = []
        errors = []
        for ind, row in self.metadata.iterrows():    
            sys.stdout.write('\r%s: %s' % (row.date, row.filename))

            if pd.isna(row.filename) or 'gpx' in row.filename.split('.'):
                continue

            try:
                data = file_utils.parse_fit(os.path.join(self.root_dirpath, row.filename))
            except Exception as error:
                errors.append([row, error])
                continue

            # use a dataframe here for consistency with message dataframes
            data['strava_metadata'] = pd.DataFrame([row])
            parsed_data.append(data)

        if len(errors):
            print('Warning: some errors occured; inspect parsing_errors for details')

        self.parsed_data = parsed_data
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

