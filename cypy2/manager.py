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
from .import file_settings


class ActivityManager(object):

    def __init__(self, strava_dirpath, from_cache=False):
        
        self.strava_dirpath = strava_dirpath
        self.strava_dirname = strava_dirpath.split(os.sep)[-1]

        self.cache_dirpath = os.path.join(os.getenv('HOME'), self.strava_dirname)
        os.makedirs(self.cache_dirpath, exist_ok=True)

        self.strava_metadata = pd.read_csv(os.path.join(strava_dirpath, 'activities.csv'))

        if from_cache:
            self._load_cache()


    def _load_cache(self):

        filepaths = glob.glob(os.path.join(self.cache_dirpath, '*.p'))
        filepath = sorted(filepaths)[-1]

        if len(filepaths) > 1:
            print('Warning: multiple pickle files found; loading %s' % filepath.split(os.sep)[-1])

        with open(filepath, 'rb') as file:
            self.parsed_data = pickle.load(file)


    def generate_cache_filename(self):

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d')
        return os.path.join(self.cache_dirpath, '%s_all-parsed-fit-files.p' % timestamp)


    def parse_all(self):

        data = []
        errors = []
        for ind, row in self.strava_metadata.iterrows():    
            sys.stdout.write('\r%s: %s' % (row.date, row.filename))

            if pd.isna(row.filename) or 'gpx' in row.filename.split('.'):
                continue

            try:
                d = file_utils.parse_fit(os.path.join(self.strava_dirpath, row.filename))
            except:
                errors.append(row)
                continue
            
            # use a dataframe here for consistency with message dataframes
            d['strava_metadata'] = pd.DataFrame([row])
            data.append(d)

        self.parsed_data = data
        self.parse_errors = errors


    def to_cache(self):

        with open(self.generate_cache_filename(), 'wb') as file:
            pickle.dump(self.parsed_data, file)

