import enum


class BackupType(str, enum.Enum):
    """
    Type of backup.
    """

    FULL = "FULL"
    INCREMENTAL = "INCREMENTAL"


class BackupFrequency(str, enum.Enum):
    """
    Type of backup frequency.
    """

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class BackupLogMode(str, enum.Enum):
    """
    Type of backup log mode.
    """

    MANUAL = "MANUAL"
    SCHEDULE = "SCHEDULE"
