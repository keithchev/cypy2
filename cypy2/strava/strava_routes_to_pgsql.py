import os
import sys
import psycopg2
import argparse
import subprocess

from cypy2 import dbutils


def _gpx2pgsql(dbname, filename):
    '''
    Insert a GPX file into a postGIS database using ogr2ogr

    Note that the arguments '-dim 3 -oo GPX_ELE_AS_25D=YES' are required
    to include elevation data in the point and linestring geometries
    '''
    command = (
        'ogr2ogr -update -append -dim 3 -oo GPX_ELE_AS_25D=YES -f PostgreSQL '
        'PG:dbname=%s %s tracks track_points'
    ) % (dbname, filename)

    subprocess.run(
        command, 
        shell=True, 
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True)


def insert_routes(conn, gpx_filenames):
    '''
    Create a database of Strava routes from the GPX files found in Strava exports
    (in the 'routes/' directory)
    
    To do so, we use the GDAL ogr2ogr utility, which creates (or updates) its own schema,
    which consists of linestrings in the 'tracks' table and points in the 'track_points' table. 

    However, it turns out that the geometries (points and linestrings) created by ogr2ogr
    do not include elevation (the z-values are always zero). Presumably, this is a bug, 
    but in the mean time it means that we need to get the elevations from the 'ele' column
    in the track_points table, which in turn requires joining the metadata (e.g., track name) 
    from the 'tracks' table.
    
    To do so, we use the hack-ish approach below to update the track_fid column of the track_points table
    to match the ogc_fid column of tracks table after each call to ogr2ogr.

    This then enables queries like
    'select tracks.name, ST_Force2D(ST_Collect(track_points.geom)) from track_points, tracks
    where tracks.track_id = track_points.track_id and tracks.name like '%Diablo%'
    group by tracks.name'

    '''

    # drop existing tables
    dbutils.execute_query('drop table if exists tracks', conn)
    dbutils.execute_query('drop table if exists track_points', conn)
    conn.commit()

    # insert the first GPX file to create the schema
    _gpx2pgsql(conn.info.dbname, gpx_filenames[0])
    
    # remove all rows
    dbutils.truncate_table('tracks', conn, for_real=True)
    dbutils.truncate_table('track_points', conn, for_real=True)

    # add a date_created column to the 'tracks' table
    dbutils.execute_query(
        'alter table tracks add column date_created timestamptz default now();',
        conn,
        raise_errors=False)

    conn.commit()

    # insert the GPX files one at a time
    for filename in gpx_filenames:
        print('Inserting %s' % filename)

        # step 1: insert the GPX file using ogr2ogr
        # this inserts one row into the 'tracks' table,
        # and a row for each point (lat/lon coord) into the 'track_points' table
        _gpx2pgsql(conn.info.dbname, filename)

        # step 2: get the ogc_id of the track we just inserted
        row = dbutils.execute_query(
            'select ogc_fid from tracks order by date_created desc limit 1;',
            conn)
        track_ogc_fid = row[0][0]

        # step 3: set the track_fid of the new rows in 'track_points' 
        # to the ogc_id of the new row in 'tracks'
        # (ogr2ogr itself always sets track_points.track_fid to zero)
        # ***note that this assumes that tracks.ogc_id is never zero***
        dbutils.update_value(
            conn, 
            table='track_points', 
            column='track_fid',
            value=track_ogc_fid, 
            selector={'track_fid': 0}, 
            only_one=False)

    # column renaming
    dbutils.execute_query('alter table tracks rename ogc_fid to track_id;', conn)
    dbutils.execute_query('alter table tracks rename wkb_geometry to geom;', conn)

    dbutils.execute_query('alter table track_points rename ele to elevation;', conn)
    dbutils.execute_query('alter table track_points rename wkb_geometry to geom;', conn)
    dbutils.execute_query('alter table track_points rename track_fid to track_id;', conn)
    dbutils.execute_query('alter table track_points rename track_seg_point_id to point_order;', conn)
    conn.commit()

    # columns to retain
    columns = {
        'tracks': ['track_id', 'name', 'type', 'geom'],
        'track_points': ['track_id', 'point_order', 'elevation', 'geom']
    }

    # drop unneeded columns
    for table in ['tracks', 'track_points']:
        for column in dbutils.get_column_names(conn, table):
            if column not in columns[table]:
                print('Dropping column %s from table %s' % (column, table))
                dbutils.execute_query(
                    'alter table %s drop column "%s"' % (table, column),
                    conn,
                    commit=True)
