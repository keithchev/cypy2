
try:
    import dbutils
except ModuleNotFoundError:
    sys.path.append('../../../projects-gh/dbutils/')
    import dbutils

from cypy2 import (
	strava,
	utils,
	file_utils,
	file_settings,
)

from cypy2.managers import ActivityManager
from cypy2.activity import (Activity, LocalActivity)