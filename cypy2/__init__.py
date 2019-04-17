
try:
    import dbutils
except ModuleNotFoundError:
    sys.path.append('../../../_projects-gh/dbutils/')
    import dbutils

from cypy2 import (
	utils,
	file_utils,
	file_settings
)

from cypy2.activity import (Activity, LocalActivity)
from cypy2.managers import (ActivityManager, StravaExportManager)