

verbose = True

# database connection
user = 'keith'
host = 'localhost'
dbname = 'cypy2'
conn = psycopg2.connect(user=user, host=host, dbname=dbname)

# load FIT-file data from a strava export
root = '/home/keith/Downloads/export_7989839-1'
strava_export = cypy2.StravaExportManager(root, from_cache=True)
manager = cypy2.ActivityManager.from_strava_export(strava_export.activity_data, raise_errors=True)

# process each activity's raw data and populate the database 
for activity in manager.activities():
    
    # process the raw data
    activity.process()
    
    # insert the raw data (metadata, records, and events)
    activity.to_db(conn, kind='raw', verbose=verbose)
    
    # insert the processed records data
    activity.to_db(conn, kind='processed', verbose=verbose)

# re-instantiate activity manager from database
manager = cypy2.ActivityManager.from_db(conn)

