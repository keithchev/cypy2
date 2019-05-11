

import cypy2
import psycopg2

verbose = True

def connect_to_db(dbname):
    # database connection
    user = 'keith'
    host = 'localhost'
    conn = psycopg2.connect(user=user, host=host, dbname=dbname)
    return conn


def main():

    # load FIT-file data from a strava export
    root = '/home/keith/Downloads/export_7989839_2019-05-10'

    print('Parsing FIT files')
    strava_export = cypy2.strava.StravaExportManager(root, from_cache=False)
    strava_export.parse_all()

    print('Caching parsed FIT files')
    strava_export.to_cache()

    manager = cypy2.ActivityManager.from_strava_export(
        strava_export.activity_data, raise_errors=True)

    conn = connect_to_db('cypy2v2')
    for activity in manager.activities():
        
        # process the raw data
        activity.process()
        
        # insert the raw data (metadata, records, and events)
        activity.to_db(conn, kind='raw', verbose=verbose)
        
        # insert the processed records data
        activity.to_db(conn, kind='processed', verbose=verbose)

    # re-instantiate activity manager from database
    manager = cypy2.ActivityManager.from_db(conn)


if __name__=='__main__':
    main()