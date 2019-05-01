#!/bin/bash

# Loading OSM shapefiles into postGIS
# adapted from https://gist.github.com/mojodna/b1f169b33db907f2b8dd
#
# Example usage:
# osm_roads_to_pgsql.sh norcal-latest-free.shp/ utah-latest-free.shp/
#
# These directories (*-latest-free.shp) are snapshots of OSM data from 
# http://download.geofabrik.de/north-america.html
#
# Keith Cheveralls
# May 2019
#

DB=osm_roads
TABLE=roads
SRID=4326 # 4326 allows preview in pgadmin

# create the database
createdb $DB

psql -q -d $DB -c 'create extension postgis'
psql -q -d $DB -c 'create extension postgis_topology'

# name of the roads shapefile in an OSM directory
filename="gis_osm_roads_free_1.shp"

# create the schema from the first directory
echo "Creating schema"
shp2pgsql -p -D -t 2d -s $SRID -W LATIN1 "$1/$filename" $TABLE | psql -d $DB -q

# Import the files
for dirname in "$@"; do
    echo "Importing $dirname"
    shp2pgsql -a -D -t 2d -s $SRID -W LATIN1 "$dirname/$filename" $TABLE | psql -d $DB -q
done

# create spatial index
echo "Creating indexes"
psql -q -d $DB -c "create index geom_gist on roads using gist(geom);"


