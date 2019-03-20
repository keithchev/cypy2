

verbose = True

# database connection
user = 'keith'
host = 'localhost'
dbname = 'cypy2'
conn = psycopg2.connect(user=user, host=host, dbname=dbname)


# load parsed FIT-file data
root = '/home/keith/Downloads/export_7989839-1'
strava_export = cypy2.StravaExportManager(root, from_cache=True)
activity_manager = cypy2.ActivityManager.from_strava_export(strava_export)


# populate the database with the metadata, the raw records and events, and the processed records
for activity in activity_manager.activities():
    activity.to_db(conn, kind='raw', verbose=verbose)
    activity.to_db(conn, kind='processed', verbose=verbose)


# re-instantiate activity manager from database
activity_manager = cypy2.ActivityManager.from_db(conn)

