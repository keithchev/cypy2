import os
import re
import sys
import git
import glob
import time
import shutil
import pickle
import datetime
import psycopg2
import subprocess
import numpy as np
import pandas as pd
import seaborn as sns

from scipy import interpolate
from matplotlib import pyplot as plt

from cypy2 import (utils, constants, file_utils, file_settings, constants)

try:
    import pgutils
except ModuleNotFoundError:
    sys.path.append('../../../_projects-gh/pgutils/')
    import pgutils


class Activity(object):
    '''
    Processing and database-related methods for a single activity
    
    Parameters
    ----------
    source : 'local' or 'db'
    data : parsed data from either a single FIT file or a database query,
           always as a dict of 'events', 'summary', and 'records' dataframes
    metadata : activity metadata as a pd.Series 


    Usage
    --------
    activity = Activity.from_db(conn, activity_id)


    Public API
    ----------
    from_db
    to_db

    # generate processed/derived record data
    process_records

    # metadata as a pd.Series; generated by LocalActivity._generate_metadata
    metadata

    # summary statistics from the FIT file's 'session' message or generated by self.summarize
    summary(kind='raw|processed')
    
    # events (e.g. starts/stops) from the FIT file's event messages or inferred from the records
    events(kind='raw|processed')

    # time-series data from FIT file record messages
    records(kind='raw|processed')


    TODO
    ----
     - implement _validate_metadata    
     - implement processing and summary

    '''


    def __init__(self, metadata, raw_data, processed_data=None, source='db'):


        # self._validate_metadata(metadata)
        self.metadata = metadata

        required_raw_data = ['events', 'summary', 'records']
        if set(required_raw_data).difference(raw_data.keys()):
            raise ValueError('Some raw data types are missing')
        self._raw_data = raw_data

        assert(source in ['local', 'db'])
        self.source = source
        
        if processed_data is not None:
            self._processed_data = process_data
        else:
            self._processed_data = {}
            self._processed_data['records'] = self.process_records()


    @classmethod
    def from_db(cls, conn, activity_id, load='raw'):
        '''
        Initialize from the raw and maybe processed data from a cypy2 database

        TODO: implement load='all' (raw plus derived data)
        '''

        selector = {'activity_id': activity_id}

        metadata = pgutils.get_rows(conn, 'metadata', selector)
        events = pgutils.get_rows(conn, 'raw_events', selector)
        records = pgutils.get_rows(conn, 'raw_records', selector)

        # records from a one-row dataframe of lists to a dataframe of timepoints
        records = pd.DataFrame(records.to_dict(orient='records').pop())

        # drop activity_id columns
        events.drop('activity_id', axis=1, inplace=True)
        records.drop('activity_id', axis=1, inplace=True)

        # drop record fields with no data
        records.dropna(axis=1, how='all', inplace=True)

        # for now, skip loading the raw summary
        summary = None

        # metadata as a pd.Series
        metadata = metadata.iloc[0]

        data = {'events': events, 'records': records, 'summary': summary}
        activity = cls(metadata, data, source='db')
        return activity



    def to_db(self, conn, kind=None, verbose=True):
        '''
        Insert an activity's raw or processed data into a cypy2 database instance

        Parameters
        ----------
        conn : a psycopg2 connection to the database
        kind : the kind of data to insert; either 'raw' or 'processed'

        '''
        assert(kind in ['raw', 'processed'])

        sys.stdout.write('\rInserting %s data for activity %s' % \
            (kind, self.metadata.activity_id))

        if kind=='raw':
            if self.source=='local':
                self._raw_data_to_db(conn, verbose)
            else:
                raise ValueError(
                    'Cannot insert raw data unless the activity was loaded from a local file')

        if kind=='processed':
            self._processed_data_to_db(conn, verbose)


    def _processed_data_to_db(self, conn, verbose):
        '''
        Insert an activity's *processed* (that is, derived) data

        Currently, this method always creates a new row in proc_records
        with the latest processed records data, even if the data is unchanged
        (since the table is keyed by (activity_id, date_created)). 

        conn : psycopg2 connection to the database

        '''

        table = 'proc_records'
        activity_id = self.metadata.activity_id

        # the current commit
        repo = git.Repo('../')
        current_commit = repo.commit().hexsha

        # warn if there are uncommitted changes in activity.py
        if verbose and 'cypy2/activity.py' in [d.a_path for d in repo.index.diff(None)]:
            print('Warning in Activity.to_db: uncommitted local changes in cypy2/activity.py')

        # create a new row in the proc_records table
        pgutils.insert_value(conn, table, {'activity_id': activity_id, 'commit_hash': current_commit})
        conn.commit()

        # get the new row (assumes we're the only user currently inserting rows)
        row = pd.read_sql(
            'select activity_id, date_created from proc_records order by date_created desc limit 1', conn)
        row = row.iloc[0]

        # sanity check
        assert(row.activity_id==activity_id)

        # update the data columns
        records = self.records(kind='processed')
        columns = pgutils.get_column_names(conn, table)
        for column in columns:
            if column in records.columns:
                pgutils.update_value(
                    conn,
                    table=table, 
                    column=column,
                    value=records[column], 
                    selector={'activity_id': activity_id, 'date_created': row.date_created})

        conn.commit()



    def process_records(self):
        '''
        Generate processed records from raw records
        
        Does the following:
         - renames/drops some columns
         - calculates elapsed time in seconds
         - interpolates the raw records to a constant sampling rate
         - generates a pause mask
         - calculates VAM from altitude
         - various unit conversions

        TODO: calculate additional columns (grade, vert, kJ)

        '''

        records = self.records('raw').reset_index()

        # ----------------------------------------------------------------------------------------
        #
        # temporary hack to correct fitparse bug
        #
        if 'speed' in records.columns:
            speed = records.speed.values
            speed[speed > 30] /= 1000
            records['speed'] = speed

        if 'altitude' in records.columns:
            alt = records.altitude.values
            records['altitude'] = (alt - 2500)/5.
        #
        # ---------------------------------------------------------------------------------------- 

        # column renaming for convenience
        records.rename(columns={'position_lat': 'lat', 'position_long': 'lon'}, inplace=True)

        # drop the enhanced speed and altitude columns, 
        # since they seem to be identical to the 'normal' speed and altitude columns
        # TODO: determine whether this is always true
        dropped_columns = ['enhanced_speed', 'enhanced_altitude']
        for column in dropped_columns:
            if column in records.columns:
                records.drop([column], axis=1, inplace=True)


        # ----------------------------------------------------------------------------------------
        #
        # calculate elapsed time in seconds and drop the timepoint column
        #
        # ----------------------------------------------------------------------------------------
        timestamps = records.timepoint.apply(pd.to_datetime)
        records['elapsed_time'] = [dt.seconds for dt in (timestamps - timestamps[0])]
        records.drop(['timepoint'], axis=1, inplace=True)


        # ----------------------------------------------------------------------------------------
        #
        # interpolate the raw records and calculate the pause mask and VAM
        #
        # ----------------------------------------------------------------------------------------
        records = self._interpolate_records(records, constants.interpolation_timestep)
        records['pause_mask'] = self._calculate_pause_mask(records)

        if 'altitude' in records.columns:
            records['vam'] = self._calculate_vam(records.altitude)


        # ----------------------------------------------------------------------------------------
        #
        # unit conversions
        #
        # ----------------------------------------------------------------------------------------

        # lat/lon coordinates from semicircles to degrees 
        # (note that indoor rides don't have these columns)
        if 'lat' in records.columns:
            records['lat'] *= constants.semicircles_to_degrees
            records['lon'] *= constants.semicircles_to_degrees

        # m/s to mph
        if 'speed' in records.columns:
            records['speed'] *= (constants.miles_per_meter * constants.seconds_per_hour)

        # meters to feet
        if 'altitude' in records.columns:
            records['altitude'] *= constants.feet_per_meter

        # meters to miles
        if 'distance' in records.columns:
            records['distance'] *= constants.miles_per_meter

        return records


    @staticmethod
    def _interpolate_records(records, timestep):
        '''
        Interpolate records

        Note that this is not always necessary, since for many activities,
        the sampling rate is constant (rather than variable/dynamic). 

        TODO: drop *internal* NAs prior to interpolating
              (but retain initial or trailing NAs)

        '''

        timepoints = records.elapsed_time.values
        new_timepoints = np.arange(0, timepoints[-1], timestep)

        new_records = pd.DataFrame()
        for column in set(records.columns).difference(['elapsed_time']):
            values, mask = records[column].values, records[column].isna().values
            interpolator = interpolate.interp1d(timepoints, values, kind='linear')
            new_records[column] = interpolator(new_timepoints)

        new_records['elapsed_time'] = new_timepoints
        return new_records


    def _calculate_pause_mask(self, records):
        '''
        Generate a pause mask from the pauses implied by in-activity start and stop events 

        Parameters
        ----------
        records : interpolated records

        '''

        # timestamp of the first record 
        # (i.e., the timestamp corresponding to records.elapsed_time==0)
        t0 = pd.to_datetime(self.metadata.records_timestamp)

        # remove initial start time and final stop time
        events = self.events('raw').iloc[1:-1]

        starts = events.loc[events.event_type=='start'].event_time
        stops = events.loc[events.event_type=='stop'].event_time

        elapsed_time = records.elapsed_time.values
        mask =  np.zeros(*elapsed_time.shape)

        for start, stop in zip(starts, stops):
            pause_start, pause_stop = (stop - t0).seconds, (start - t0).seconds
            mask += (elapsed_time > pause_start) & (elapsed_time < pause_stop)

        mask = mask.astype(bool)
        return mask


    def _infer_pauses(self):
        '''
        Infer pauses from the raw records data

        ** currently unused **
        '''

        d = self.records('raw')
        timestamps = d.timepoint.apply(pd.to_datetime)
        elapsed_time = [t.seconds for t in (timestamps - timestamps[0])]

        counts = np.bincount(np.diff(elapsed_time))
        x = np.argwhere(counts).flatten()
        counts = counts[counts > 0]

        pauses = pd.DataFrame(data=list(zip(x, counts)), columns=['timestep', 'frequency'])
        return pauses


    @staticmethod
    def _calculate_vam(altitude):
        '''
        Calculate VAM (vertical ascent velocity in meters per hour)

        **assumes records have been interpolated with a constant timestep**

        Parameters
        ----------
        altitude : pd.Series of raw altitude values (in meters)
                   ** must be interpolated to constant one-second timestep **

        '''

        assert set(np.diff(altitude.index.values))==set([1])

        # hard-coded half life in seconds
        # (half life of 7s corresponds to a decay rate of 10s)
        halflife = 7
        window_sz = 3*halflife
        alpha = (1 - np.exp(np.log(.5)/halflife))

        weights = (1 - alpha)**(np.arange(0, window_sz, 1))
        weights /= weights.sum()
        weights = weights[::-1]

        y = altitude.values
        x_window = np.arange(window_sz)
        y_windows = utils.sliding_window(y, window_sz, 1)

        slopes, resids = [], []
        for y_window in y_windows:
            slope, offset, res = utils.weighted_linregress(x_window, y_window, weights)
            slopes.append(slope)
            resids.append(res)

        vam, resids = np.array(slopes), np.array(resids)

        # add back the missing initial values
        vam = np.concatenate(([np.nan] * (window_sz - 1), vam))

        # meters per sec to meters per hour
        vam *= constants.seconds_per_hour

        return vam


    def summary(self, kind='raw'):
        '''
        Summary statistics
        '''
        assert(kind in ['raw', 'derived'])
        return None



    def events(self, kind='raw'):
        '''
        '''
        assert(kind in ['raw', 'derived'])

        if kind=='raw':
            return self._raw_data['events'].copy()

        if kind=='derived':
            return self._derive_events()


    def records(self, kind='raw', cached=True):

        if kind=='raw':
            records = self._raw_data['records'].copy()

        if kind.startswith('proc'):
            if cached:
                records = self._processed_data['records'].copy()
            else:
                records = self.process_records()
        return records


    def plot(self, columns=None, overlay=False, xmode='hours', xrange=None, halflife=None):

        colors = sns.color_palette()

        xlabels = {
            'seconds': 'Elapsed time (seconds)', 
            'minutes': 'Elapsed time (minutes)',
            'hours': 'Elapsed time (hours)',
            'distance': 'Distance (miles)',
        }

        def _style_axis(ax):
            ax.yaxis.grid(b=False)
            ax.xaxis.grid(linestyle='dotted', color=tuple(np.ones(3)*.7))
    
        records = self.records('processed')

        if xmode=='seconds':
            x = records.elapsed_time.values
        if xmode=='minutes':
            x = records.elapsed_time.values/60
        if xmode=='hours':
            x = records.elapsed_time.values/3600
        if xmode=='miles':
            x = records.distance.values

        if xrange:
            mask = (x > min(xrange)) & (x < max(xrange))
        else:
            mask = np.ones(x.shape).astype(bool)

        if isinstance(columns, str):
            columns = [columns]
        
        if overlay:
            fig, left_ax = plt.subplots(1, 1, figsize=(12, 2))
            right_ax = left_ax.twinx()
            axs = [left_ax, right_ax]
        else:
            fig, axs = plt.subplots(len(columns), 1, figsize=(12, 2*len(columns)))
            if not isinstance(axs, np.ndarray):
                axs = [axs]
        
        for column, ax, color in zip(columns, axs, colors[:len(axs)]):
            y = records[column]
            if halflife:
                y = y.ewm(halflife=halflife).mean()

            ax.plot(x[mask], y[mask], color=color, label=column)
            ax.set_ylabel(column)

        for ind, ax in enumerate(axs):
            _style_axis(ax)
            if ind < len(axs) - 1:
                ax.get_xaxis().set_ticklabels([])
        axs[-1].set_xlabel(xlabels[xmode])



class LocalActivity(Activity):
    '''
    An activity loaded from local (non-database) data
    Subclasses Activity and contains FIT-file-specific parsing methods

    Public methods
    --------------
    from_fit_file
    from_strava_export

    Examples
    --------
    # from a local FIT file
    activity = LocalActivity.from_fit_file('/path/to/fit/file')

    # from a Strava export manager
    manager = StravaExportManager('/path/to/export/', from_cache=True)
    activity = LocalActivity.from_strava_export(data=manager.parsed_data[ind])


    Parameters
    ----------
    fit_data : parsed data from a single FIT file as a dict of dataframes keyed by message name
               must have: 'file_id', 'device_info', 'event', 'session', and 'record'

    strava_metadata : optional one-row dataframe of metadata from a Strava export's activity.csv

    '''

    def __init__(self, fit_data, strava_metadata=None):

        self._fit_data = fit_data
        self._strava_metadata = strava_metadata

        # message types required in raw FIT data
        required_message_names = ['file_id', 'device_info', 'session', 'event', 'record']
        if set(required_message_names).difference(fit_data.keys()):
            raise ValueError('Some message types are missing in fit_data')

        # generate/infer/organize metadata
        metadata = self._generate_metadata(fit_data, strava_metadata)

        # parse/organize the raw data 
        events, summary, records = self._parse_fit_data(fit_data, metadata.activity_id)

        # various consistency checks
        self._validate_fit_data(metadata, records, events)

        data = {
            'events': events,
            'summary': summary,
            'records': records,
        }

        super().__init__(metadata, data, source='local')



    @classmethod
    def from_fit_file(cls, filepath):
        '''
        Initialize an activity directly from a FIT file
    
        **intended for testing only**
        (note that there is no strava_metadata)
        
        Parameters
        filepath : path to a local FIT file

        '''
        
        data = file_utils.parse_fit(filepath)
        activity = cls(data)
        return activity


    @classmethod
    def from_strava_export(cls, data):
        '''
        Initialize an activity from the parsed data cached by managers.StravaExportManager
        
        Parameters
        ----------
        data : dict of message dataframes; usually, this corresponds to one element 
        of the list returned by StravaExportManager.parse_all
        '''
        activity = cls(data, strava_metadata=data['strava_metadata'])
        return activity



    def _raw_data_to_db(self, conn, verbose):
        '''
        Insert or update an activity's *raw* data in a cypy2 database

        Generally, this method should only be called when populating a new database,
        since the raw data should never need to be updated. 
        
        conn : psycopg2 connection to the database

        '''

        activity_id = self.metadata.activity_id

        # ------------------------------------------------------------------------------------
        #
        #  metadata
        #
        # ------------------------------------------------------------------------------------

        # metadata as a (one-row) DataFrame so we can use pgutils.dataframe_to_table
        # TODO: decide how to handle database errors
        metadata = pd.DataFrame(data=[self.metadata])
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
        events = self.events(kind='raw')
        pgutils.dataframe_to_table(conn, 'raw_events', events, raise_errors=False)
        conn.commit()


        # ------------------------------------------------------------------------------------
        #
        #  summary
        #
        # ------------------------------------------------------------------------------------
        # device summary (i.e., the 'session' message)
        # summary = self.summary(kind='raw')


        # ------------------------------------------------------------------------------------
        #
        #  records
        #
        # ------------------------------------------------------------------------------------
        # create a new row in raw_records for this activity
        pgutils.insert_value(conn, 'raw_records', {'activity_id': activity_id})
        conn.commit()

        records = self.records(kind='raw')

        # note that update_value will overwrite any existing values
        columns = pgutils.get_column_names(conn, 'raw_records')
        for column in columns:
            if column in records.columns:
                pgutils.update_value(
                    conn,
                    table='raw_records', 
                    column=column,
                    value=records[column], 
                    selector={'activity_id': activity_id})

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


    @classmethod
    def _generate_metadata(cls, fit_data, strava_metadata=None):
        '''
        Generate metadata from the raw (FIT-file) data

        Metadata columns:        
            - activity id
            - activity type
            - cycling type (indoor/road)
            - FIT file timestamp
            - strava timestamp, title, gear
            - GPS device make and model
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
        file_id, device_info, session, sport = \
            fit_data.get('file_id'), fit_data.get('device_info'), fit_data.get('session'), fit_data.get('sport')

        # column renaming in device_info
        device_info.rename(columns={'garmin_product': 'product_name'}, inplace=True)

        # column renaming in file_id
        # nb this is a bit dangerous, because we are assuming that the 'product' column
        # only appears in Wahoo (e.g., non-Garmin) file_id messages;
        file_id.rename(columns={'garmin_product': 'product_name', 'product': 'product_name'}, inplace=True)

        # there should always be only one message (row) for these message types
        file_id, session = _df_to_series(file_id), _df_to_series(session)

        # strava metadata as a series for convenience (it always has one row by definition)
        strava_metadata = _df_to_series(strava_metadata)

        # ------------------------------------------------------------------------------------
        #
        # initialize metadata with activity_id and timestamps 
        # from both the file_id and the first record, which may not be the same
        # (and the timestamp of the first record will be important in, e.g., self._calculate_pause_mask)
        #
        # ------------------------------------------------------------------------------------
        metadata = {
            'activity_id': cls.id_from_fit(file_id=file_id),
            'file_timestamp': str(file_id.time_created),
            'records_timestamp': str(fit_data['record'].iloc[0].timestamp),
        }

        # copy some fields directly from strava metadata
        if strava_metadata is not None:
            metadata.update({
                'filename': strava_metadata['filename'],
                'strava_title': strava_metadata['name'],
                'strava_timestamp': strava_metadata['date'],
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
        
        metadata = pd.Series(data=metadata)
        return metadata


    @staticmethod
    def _validate_fit_data(metadata, records, events):
        '''
        Check the integrity of raw (FIT-file) data
        
        TODO: check that required message types exist
        - 
        '''

        activity_id = metadata.activity_id

        # check that we have records for the expected sensors
        # (nb there is always speed data, with or without a sensor)
        for sensor in ['heart_rate', 'power']:

            # skip fenix3 because it has a built-in HRM
            if sensor=='heart_rate' and metadata['device_model']=='fenix3':
                continue

            flag = sensor in records.columns
            if metadata['%s_flag' % sensor] and not flag:
                print('Warning: activity %s has %s sensor but no records' % (activity_id, sensor))
            if not metadata['%s_flag' % sensor] and flag:
                print('Warning: activity %s has %s records but no sensor' % (activity_id, sensor))
        

    @staticmethod
    def _parse_fit_data(fit_data, activity_id):
        '''
        Parse the raw FIT-file data to generate database-ready
        'events', 'summary', and 'record' dataframes

        TODO: parse/cleanup summary and records

        '''
        events = fit_data['event'].copy()
        summary = fit_data['session'].copy()
        records = fit_data['record'].copy()

        # column renaming
        records.rename(columns={'timestamp': 'timepoint'}, inplace=True)

        # for now, keep only the event_type and time columns for 'timer' events (starts and stops)
        events = events.loc[events.event=='timer'][['event_type', 'timestamp']]

        # column names for database
        events = events.rename(columns={'timestamp': 'event_time'})

        events['activity_id'] = activity_id

        # 'stop_all' to 'stop', etc
        events.replace(to_replace=re.compile('stop(.*)$'), value='stop', inplace=True)
        events.replace(to_replace=re.compile('start(.*)$'), value='start', inplace=True)

        # check for pairs of start/stop events that have the same timestamp
        # (this is rare, but real)
        if events.shape[0]!=len(events.event_time.unique()):
            print('Warning: at least two events have the same timestamp')

        # remove any such pairs by finding the index of the first event of each pair
        events = events.reset_index(drop=True)
        inds = np.argwhere(np.array([dt.astype(int) for dt in np.diff(events.event_time)])==0).flatten()
        for ind in inds:
            if set(events.iloc[[ind, ind + 1]].event_type)==set(['start', 'stop']):
                events = events.drop([ind, ind + 1], axis=0)
            else:
                # we should never get here
                print('Warning: two events have the same timestamp *and* type')

        # drop the last event when the last two events are both stops
        # (this usually corresponds to a 'stop' and a 'stop_all')
        events = events.reset_index(drop=True)
        if events.iloc[-1].event_type=='stop' and events.iloc[-2].event_type=='stop':
            events = events.drop(len(events) - 1, axis=0)

        return events, summary, records
