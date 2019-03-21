
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

