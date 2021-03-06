
import os
import re
import sys
import glob
import pickle
import datetime
import numpy as np
import pandas as pd

from cypy2 import (file_utils, file_settings)


class StravaExportManager(object):
    '''
    Methods to organize and parse the FIT files in a Strava data export

    Currently (as of April 2019), Strava data exports include original FIT files for each activity;
    these appear in the activities/ subdirectory, with corresponding metadata in activities.csv.
    
    Note that this organization is hard-coded in the methods below;
    if the organization of the exports changes, these methods will need to be updated.
 
    Parameters
    ----------
    root_dirpath : path to the strava export directory
    from_cache : whether to load previously-parsed FIT-file data from a cache
                 (created by self.to_cache)

    '''

    def __init__(self, root_dirpath, from_cache=False):
        
        self.root_dirpath = root_dirpath
        self.root_dirname = root_dirpath.split(os.sep)[-1]

        # where to cache the parsed data
        self.cache_dirpath = os.path.join(
            os.getenv('HOME'), 
            'parsed-strava-exports', 
            self.root_dirname)
        os.makedirs(self.cache_dirpath, exist_ok=True)

        # load the CSV activity metadata
        self.metadata = pd.read_csv(os.path.join(self.root_dirpath, 'activities.csv'))

        if from_cache:
            self.activity_data = self._load_from_cache(self.cache_dirpath)
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
        Parse all of the FIT files that appear in the Strava export's activity metadata

        **Note that this method ignores activities in other formats (e.g., GPX format)**

        Returns
        -------
        self.activity_data : list of dicts of dataframes, keyed by message name
        self.parsing_errors : list of metadata rows on which file_utils.parse_fit failed

        '''
        activity_data = []
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
            activity_data.append(data)

        if len(errors):
            print('Warning: some errors occured; inspect parsing_errors for details')

        self.activity_data = activity_data
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
            pickle.dump(self.activity_data, file)

