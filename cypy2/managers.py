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
    def from_strava_export(cls, strava_activity_data, raise_errors=False):
        '''
        Instantiate from parsed FIT files exported from Strava

        Usually, strava_activity_data corresponds to StravaExportManager.activity_data.
        The resulting activities have non-null raw_data (equivalent to Activity.from_db(kind='raw')),
        but Activity.process() must be called to generate the processed data. 

        '''
        activities = []
        for ind, data in enumerate(strava_activity_data):
            try:
                activity = LocalActivity(data, strava_metadata=data['strava_metadata'])
                activities.append(activity)
                sys.stdout.write('\r%s' % activity.metadata.activity_id)
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
        summary = dbutils.get_rows(conn, 'raw_summary')
        metadata = pd.merge(metadata, summary, how='inner', on='activity_id')

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


