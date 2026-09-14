from .jobsireland import JobsIrelandSource
from .mail_alerts import GmailJobAlertSource
from .oleeo import OleeoSource
from .smartrecruiters import SmartRecruitersCompanySource
from .successfactors import SuccessFactorsSource
from .web_boards import ConfiguredWebBoard

__all__ = [
    "ConfiguredWebBoard",
    "GmailJobAlertSource",
    "JobsIrelandSource",
    "OleeoSource",
    "SmartRecruitersCompanySource",
    "SuccessFactorsSource",
]
