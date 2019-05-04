
import os
import sys
import psycopg2

sys.path.append('../cypy2/')
import cypy2

root = '/home/keith/Downloads/export_7989839-1'
wahoo_example = '2326365683.fit.gz'
garmin_example = '2122584483.fit.gz'
garmin_indoor_example = '2324139976.fit.gz'

user = 'keith'
host = 'localhost'
dbname = 'cypy2'
conn = psycopg2.connect(user=user, host=host, dbname=dbname)

# from a local FIT file
a = cypy2.LocalActivity.from_fit_file(os.path.join(root, 'activities', wahoo_example))
# a.process()

# from the database
a = cypy2.Activity.from_db(conn, '20181208223529', kind='all')
a.process()
