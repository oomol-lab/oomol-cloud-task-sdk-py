"""Shared types for the Oomol Cloud Task SDK."""

from enum import Enum
from os import PathLike
from typing import Any, BinaryIO, Callable, Dict, List, NamedTuple, Optional, Union

try:
    from typing import Literal, TypedDict
except ImportError:  # pragma: no cover - Python 3.7 fallback
    from typing_extensions import Literal, TypedDict


class BackoffStrategy(Enum):
    """Polling interval backoff strategy."""

    FIXED = "fixed"
    EXPONENTIAL = "exp"


class RunTaskErrorCode(str, Enum):
    """Normalized task failure categories."""

    INSUFFICIENT_QUOTA = "INSUFFICIENT_QUOTA"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"


class TaskStatus(str, Enum):
    """Task lifecycle states returned by the API."""

    QUEUED = "queued"
    SCHEDULING = "scheduling"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TaskType(str, Enum):
    """User task ownership types."""

    USER = "user"
    SHARED = "shared"


class QueuePauseType(str, Enum):
    """Queue pause origin."""

    USER = "user"
    SYSTEM = "system"
    BILLING = "billing"


class WorkloadType(str, Enum):
    """Task workload types."""

    SERVERLESS = "serverless"


InputValues = Dict[str, Any]
Metadata = Dict[str, Any]
TaskResultDataItem = Dict[str, Any]
TaskResultData = List[TaskResultDataItem]
InProgressTaskStatus = Literal["queued", "scheduling", "scheduled", "running"]
TaskTerminalStatus = Literal["success", "failed"]
UploadSource = Union[str, PathLike, BinaryIO]


class BaseCreateTaskRequest(TypedDict, total=False):
    """Base fields shared by task creation requests."""

    inputValues: InputValues


class _CreateServerlessTaskRequestRequired(TypedDict):
    packageName: str
    packageVersion: str
    blockName: str


class CreateServerlessTaskRequest(BaseCreateTaskRequest, _CreateServerlessTaskRequestRequired, total=False):
    """Request payload for creating a serverless task."""

    type: Literal["serverless"]
    webhookUrl: str
    metadata: Metadata


CreateTaskRequest = CreateServerlessTaskRequest
TaskCreateRequest = CreateTaskRequest


class TaskCreateResponse(TypedDict):
    """Response returned after creating a task."""

    taskID: str


CreateTaskResponse = TaskCreateResponse


class TaskListItem(TypedDict):
    """Task list item from GET /v3/users/me/tasks."""

    taskID: str
    taskType: TaskType
    ownerID: str
    subscriptionID: Optional[str]
    packageID: Optional[str]
    status: TaskStatus
    progress: float
    workload: WorkloadType
    workloadID: str
    resultURL: Optional[str]
    failedMessage: Optional[str]
    createdAt: int
    updatedAt: int
    startTime: Optional[int]
    endTime: Optional[int]
    schedulerPayload: Dict[str, Any]


class TaskListResponse(TypedDict):
    """Response of GET /v3/users/me/tasks."""

    tasks: List[TaskListItem]
    nextToken: Optional[str]


class ListTasksQuery(TypedDict, total=False):
    """Query options for GET /v3/users/me/tasks."""

    size: int
    nextToken: str
    status: TaskStatus
    taskType: TaskType
    workload: WorkloadType
    workloadID: str
    packageID: str


class LatestTaskItem(TypedDict):
    """Item from GET /v3/users/me/tasks/latest."""

    taskID: str
    workloadID: str
    status: TaskStatus
    progress: float
    createdAt: int
    startTime: Optional[int]
    endTime: Optional[int]


LatestTasksResponse = List[LatestTaskItem]


class DashboardLimits(TypedDict):
    maxConcurrency: int
    maxQueueSize: int


class DashboardCount(TypedDict):
    queued: int
    scheduling: int
    scheduled: int
    running: int


class DashboardPause(TypedDict):
    paused: bool
    type: Optional[QueuePauseType]
    canResume: bool


class DashboardResponse(TypedDict):
    """Response of GET /v3/users/me/dashboard."""

    limits: DashboardLimits
    count: DashboardCount
    pause: DashboardPause


class SetTasksPauseResponse(TypedDict):
    """Response of POST /v3/user/pause and POST /v3/user/resume."""

    pauseType: Optional[QueuePauseType]


class UserTaskDetail(TypedDict):
    """User task detail object."""

    taskType: Literal["user"]
    taskID: str
    status: TaskStatus
    progress: float
    workload: WorkloadType
    workloadID: str
    schedulerPayload: Dict[str, Any]
    createdAt: int
    startTime: Optional[int]
    endTime: Optional[int]
    resultURL: Optional[str]
    failedMessage: Optional[str]


class SharedTaskDetail(TypedDict):
    """Shared task detail object."""

    taskType: Literal["shared"]
    taskID: str
    packageID: Optional[str]
    subscriptionID: Optional[str]
    status: TaskStatus
    progress: float
    schedulerPayload: Dict[str, Any]
    createdAt: int
    startTime: Optional[int]
    endTime: Optional[int]
    resultURL: Optional[str]
    failedMessage: Optional[str]


TaskDetailResponse = Union[UserTaskDetail, SharedTaskDetail]


class TaskResultInProgress(TypedDict):
    """Task result while the task is still running."""

    status: InProgressTaskStatus
    progress: float


class _TaskResultSuccessRequired(TypedDict):
    status: Literal["success"]
    resultURL: Optional[str]


class TaskResultSuccess(_TaskResultSuccessRequired, total=False):
    """Successful task result."""

    resultData: TaskResultData


class TaskResultFailed(TypedDict):
    """Failed task result."""

    status: Literal["failed"]
    error: Optional[str]


TaskResult = Union[TaskResultInProgress, TaskResultSuccess, TaskResultFailed]
TaskResultResponse = TaskResult


class CreateAndWaitResponse(NamedTuple):
    taskID: str
    result: TaskResultSuccess


ProgressCallback = Callable[[float, InProgressTaskStatus], None]
UploadProgressCallback = Callable[[int], None]


class BackoffOptions(TypedDict, total=False):
    """Backoff configuration for polling intervals."""

    strategy: BackoffStrategy
    max_interval_ms: int


class AwaitOptions(TypedDict, total=False):
    """Options shared by await_result and create_and_wait polling."""

    interval_ms: int
    timeout_ms: int
    on_progress: ProgressCallback
    backoff: BackoffOptions


class ClientOptions(TypedDict, total=False):
    """Constructor options exposed for parity with the TypeScript SDK concepts."""

    api_key: str
    base_url: str
    default_headers: Dict[str, str]
    session: Any


class UploadOptions(TypedDict, total=False):
    """Options for upload_file."""

    upload_base_url: str
    on_progress: UploadProgressCallback
    retries: int
