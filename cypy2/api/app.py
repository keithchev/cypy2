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
dbname = 'cypy2'
conn = psycopg2.connect(user=user, host=host, dbname=dbname)
manager = cypy2.ActivityManager.from_db(conn)


def _is_activity_id(activity_id):
    return activity_id in manager.metadata().activity_id.values


@app.route('/')
def home():
    return flask.render_template('index.html')


@app.route('/metadata/<activity_id>')
def metadata(activity_id):
    '''

    '''
    metadata = manager.metadata(activity_id=str(activity_id))
    metadata.drop('activity', axis=1, inplace=True)
    return flask.jsonify(json.loads(metadata.to_json(orient='records', date_format='iso')))


@app.route('/records/<activity_id>')
def records(activity_id):
    '''
    One or more record columns for one activity (e.g., power, heart rate, etc)
    '''

    if not _is_activity_id(activity_id):
        return flask.jsonify(dict())

    activity = cypy2.Activity.from_db(conn, activity_id)
    activity.load(conn, kind='processed')
    records = activity.records('proc')

    columns = request.args.get('columns')
    if columns:
        columns = columns.split(',')
    else:
        columns = list(records.columns)

    data = {
        'columns': columns,
        'values': json.loads(records[columns].head().to_json(orient='values')),
    }
    
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


if __name__=='__main__':
    app.run(debug=True)


