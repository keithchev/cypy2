#!/usr/bin/env python

'''

'''

import os
import io
import sys
import pdb
import glob
import json
import flask
import psycopg2
import numpy as np
import pandas as pd
from flask_cors import CORS
from psycopg2 import sql
from flask import Flask, render_template, request, send_file, g, abort, jsonify

try:
    import dbutils
except ModuleNotFoundError:
    sys.path.append('/home/keith/Dropbox/projects-gh/dbutils/')
    import dbutils

import cypy2

app = Flask(__name__)
CORS(app)

user = 'keith'
host = 'localhost'
dbname = 'cypy2v2'
conn = psycopg2.connect(user=user, host=host, dbname=dbname)
manager = cypy2.ActivityManager.from_db(conn)


def _is_activity_id(activity_id):
    return activity_id in manager.metadata().activity_id.values


def metadata_to_json(metadata):
    if 'activity' in metadata.columns:
        metadata.drop('activity', axis=1, inplace=True)
    data = json.loads(metadata.to_json(orient='records', date_format='iso'))
    return data


@app.route('/')
def home():
    return flask.render_template('index.html')


@app.route('/metadata/<activity_id>')
def metadata(activity_id):
    '''
    '''
    metadata = manager.metadata(activity_id=str(activity_id))
    return flask.jsonify(metadata_to_json(metadata))


@app.route('/records/<activity_id>')
def records(activity_id):
    '''
    One or more record columns for one activity (e.g., power, heart rate, etc)
    '''

    def _nan_to_none(iterable):
        return [None if pd.isna(val) else val for val in iterable]

    if not _is_activity_id(activity_id):
        return flask.jsonify(dict())

    activity = cypy2.Activity.from_db(conn, activity_id)
    activity.load(conn, kind='processed')
    records = activity.records('processed')

    # sampling rate in seconds
    sampling = int(request.args.get('sampling'))
    if not sampling:
        sampling = 10

    columns = request.args.get('columns')
    if columns:
        columns = columns.split(',')
    else:
        columns = list(records.columns)

    data = {}
    for column in columns:
        if column not in records.columns or column in ['geom', 'geom4d']:
            continue
        values = records[column].iloc[::sampling].tolist()
        if column in ['lat', 'lon']:
            values = [float(v) if v is not None else None for v in values]
        data[column] = _nan_to_none(values)
 
    return flask.jsonify(data)

    
@app.route('/trajectory/<activity_id>')
def trajectory(activity_id):
    '''
    GPS lat/lon coords for an activity (as geoJSON)
    '''

    if not _is_activity_id(activity_id):
        return flask.jsonify(dict())

    tolerance = request.args.get('tolerance')
    if not tolerance:
        tolerance = 0

    query = sql.SQL(
        'select ST_AsGeoJSON(ST_Simplify(geom, {tolerance})) from proc_records')

    query = sql.SQL(' ').join([
        query.format(tolerance=sql.SQL(tolerance)), 
        dbutils.where_clause({'activity_id': activity_id})])

    data = dbutils.execute_query(conn, query)[0][0]
    return flask.jsonify(json.loads(data))


@app.route('/near/<lat>/<lon>')
def near(lat, lon):
    '''
    Return the metadata for all activities within 50 meters of the (lat, lon) point
    (Note that ST_DistanceSphere returns distances in meters when coords are lat/lon)
    '''

    query = '''
        select activity_id, dist from(
        select activity_id, ST_DistanceSphere(
            ST_Simplify(geom, .001), 
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)) dist
        from proc_records order by dist) tmp;'''

    data = []
    result = dbutils.execute_query(conn, query, (lon, lat))
    for row in result:
        activity_id, proximity = row
        if proximity is not None:
            proximity *= cypy2.constants.miles_per_meter
        data.append({'activity_id': activity_id, 'proximity': proximity})

    return flask.jsonify(data)


if __name__=='__main__':
    app.run(debug=True)


