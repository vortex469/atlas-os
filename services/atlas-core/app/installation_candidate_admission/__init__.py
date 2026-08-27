"""Pure, non-persistent Installation Candidate Admission v1 contract."""

from app.installation_candidate_admission.assembly import (
    InstallationCandidateAdmissionInputMissing,
    InstallationCandidateAdmissionInputUnavailable,
    InstallationCandidateAdmissionReadDependency,
)
from app.installation_candidate_admission.contract import (
    InstallationCandidateAdmissionV1,
    InstallationCandidateRecordV1,
)
from app.installation_candidate_admission.evaluation import (
    evaluate_installation_candidate_admission,
)

__all__ = [
    "InstallationCandidateAdmissionInputMissing",
    "InstallationCandidateAdmissionInputUnavailable",
    "InstallationCandidateAdmissionReadDependency",
    "InstallationCandidateAdmissionV1",
    "InstallationCandidateRecordV1",
    "evaluate_installation_candidate_admission",
]
