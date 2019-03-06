'''
Here we explicitly list the fields to aggregate for the following message types:

file_id:  device type and timestamp
sport:    sport type and subtype
event:    timer start/stop events (both manual and auto-pauses)
session:  summary statistics for the session (always one per activity)
record:   time-series data

'''

field_names = {}

# -----------------------------------------------------------------------------
#
# 'file_id'
#
#  ----------------------------------------------------------------------------- 
field_names['file_id'] = [
    'type',            # always 'activity'
    'manufacturer',    # 'wahoo_fitness' or 'garmin'
    'time_created',    # timestamp
]


# -----------------------------------------------------------------------------
#
# 'sport'
#
#  ----------------------------------------------------------------------------- 
field_names['sport'] = [
    'sport',        # always 'cycling'
    'sub_sport',    # 'generic' if outdoors, 'indoor_cycling' if indoors
]


# -----------------------------------------------------------------------------
#
# 'event'
# note: only events where event=='timer' are useful to identify pauses
#
#  -----------------------------------------------------------------------------
field_names['event'] = [
    'event',           # 'timer', 'session', 'off_course', 'power_down/up', 'recovery_hr'
    'event_type',      # 'start', 'stop', 'stop_all', 'stop_disable_all', 'marker'
    'timer_trigger',   # 'manual', 'auto', None
    'timestamp',
]


# -----------------------------------------------------------------------------
#
# 'record'
#
# all of these fields are common to *ride* data from both Garmin and Wahoo,
# except for 'grade' and 'gps_accuracy' (which are Wahoo-only)
#
#  ----------------------------------------------------------------------------- 
field_names['record'] = [

    'timestamp',
    'position_lat',       # semicircles
    'position_long',      # semicircles
    'altitude',           # meters
    'enhanced_altitude',  # meters
    'distance',           # meters
    'speed',              # m/s
    'enhanced_speed',     # m/s
    'temperature',        # degrees C

    'cadence',            # rpm
    'heart_rate',         # bpm
    'power',              # watts

    'gps_accuracy',       # meters
    'grade',              # percent
]


# -----------------------------------------------------------------------------
#
# 'session'
#
# these are all the 'session' fields that appear in *rides* 
# from both Garmin and Wahoo
#
#  ----------------------------------------------------------------------------- 
field_names['session'] = [
    
    'sport',
    'timestamp',
    'start_time',

    'avg_cadence',
    'max_cadence',

    'avg_heart_rate',
    'max_heart_rate',

    'avg_speed',
    'max_speed',
    'enhanced_avg_speed',
    'enhanced_max_speed',

    'avg_power',
    'max_power',
    'normalized_power',
    'threshold_power',

    'time_in_hr_zone',
    'time_in_power_zone',

    'total_ascent',
    'total_calories',
    'total_descent',
    'total_distance',
    'total_elapsed_time',
    'total_timer_time',
    'total_work',

    'intensity_factor',
    'training_stress_score'
]

# -----------------------------------------------------------------------------
#
# exclude time-in-zone fields (whose values are tuples)
#
for name in ['time_in_power_zone', 'time_in_hr_zone']:
    field_names['session'].remove(name)
#
#  ----------------------------------------------------------------------------- 


# for reference only: 'session' fields in Garmin but not Wahoo FIT files
# (excludes 'unknown' fieldnames)
garmin_not_wahoo = [
    'avg_cadence_position',
    'avg_combined_pedal_smoothness',
    'avg_fractional_cadence',
    'avg_left_pco',
    'avg_left_pedal_smoothness',
    'avg_left_power_phase',
    'avg_left_power_phase_peak',
    'avg_left_torque_effectiveness',
    'avg_power_position',
    'avg_right_pco',
    'avg_right_pedal_smoothness',
    'avg_right_power_phase',
    'avg_right_power_phase_peak',
    'avg_right_torque_effectiveness',
    'event_group',
    'first_lap_index',
    'left_right_balance',
    'max_cadence_position',
    'max_fractional_cadence',
    'max_power_position',
    'message_index',
    'nec_lat',
    'nec_long',
    'sport_index',
    'stand_count',
    'start_position_lat',
    'start_position_long',
    'sub_sport',
    'swc_lat',
    'swc_long',
    'time_standing',
    'total_cycles',
    'total_fat_calories',
    'total_fractional_cycles',
    'trigger'
]


# for reference only: 'session' fields in Wahoo but not Garmin FIT files
wahoo_not_garmin = [
    'avg_altitude',
    'avg_grade',
    'avg_temperature',
    'enhanced_avg_altitude',
    'enhanced_max_altitude',
    'enhanced_min_altitude',
    'max_altitude',
    'max_neg_grade',
    'max_pos_grade',
    'max_temperature',
    'min_altitude',
    'min_heart_rate'
]

