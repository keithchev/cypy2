
-- misc queries of interest for cypy2


-- number of timepoints for each activity
select activity_id, array_length(altitude, 1) as len from proc_records


-- delete all but the most recent processed records for each activity
delete from proc_records
where (activity_id, date_created) not in (
	select activity_id, max(date_created) from proc_records group by activity_id
);


-- the nth-most-recent activity of each type
select activity_id, activity_type from (
	select *, 
	rank() over (partition by activity_type order by file_date desc) as r
	from metadata) md
where r = n

-- the nth most-recent processed records for a given activity
select * from (
	select *, row_number() over (order by date_created desc) as n
	from proc_records where activity_id = '20180923163103'
) temp where n = n


-- bounding box of all geometries in a table
select ST_Envelope(ST_Collect(geom)) from roads


-- extract points and order from a linestring
-- (note that ST_DumpPoints returns a set)
select name, path, ST_AsText(geom) from (
	select name, (ST_DumpPoints(ST_Simplify(geom, .001))).* 
	FROM roads WHERE name like 'King Ridge %') temp


-- find all intersections between OSM roads
-- (ST_Union eliminates duplicate points)
with cropped_roads as (
	select name, geom from roads
	WHERE name is not null and code < 5130
	and ST_Intersects(ST_MakeEnvelope(-122.3, 37.86, -122.15, 37.88, 4326), geom)
)
select ST_union(geom) from (
	select ST_Intersection(a.geom, b.geom) geom
	from cropped_roads a, cropped_roads b
	where a.name != b.name 
	and ST_Intersects(a.geom, b.geom)) as ints


-- count segments of roads in berkeley
select name, count(name) from roads
where ST_Intersects(ST_MakeEnvelope(-122.3, 37.86, -122.15, 37.923, 4326), geom)
group by name
order by count desc


-- straighforward way to merge all segments of the same road in an ROI
select name, ST_LineMerge(ST_Union(geom)) from (
	select a.name as name, a.geom as geom 
	from roads a, roads b
	where a.name = b.name
	and a.osm_id != b.osm_id
	and ST_Intersects(a.geom, b.geom)
	and ST_Intersects(ST_MakeEnvelope(-122.3, 37.86, -122.15, 37.923, 4326), a.geom)
) as ints
group by name
order by name

-- a faster way to merge all segments of the same road,
-- by doing the cross join only on the roads in the ROI
with tmp as (
	select * from roads
	where ST_Intersects(ST_MakeEnvelope(-122.3, 37.86, -122.15, 37.923, 4326), geom)
)
select name, ST_LineMerge(ST_Union(geom)) from (
	select a.name as name, a.geom as geom 
	from tmp a, tmp b
	where a.name = b.name
	and a.osm_id != b.osm_id
	and ST_Intersects(a.geom, b.geom)
) as ints
group by name
order by name