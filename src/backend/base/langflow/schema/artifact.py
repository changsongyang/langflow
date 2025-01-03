from __future__ import annotations

from collections.abc import Generator
from enum import Enum

from fastapi.encoders import jsonable_encoder
from loguru import logger
from pydantic import BaseModel

from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.encoders import CUSTOM_ENCODERS
from langflow.schema.message import Message
from langflow.schema.serialize import recursive_serialize_or_str


class ArtifactType(str, Enum):
    TEXT = "text"
    DATA = "data"
    OBJECT = "object"
    ARRAY = "array"
    STREAM = "stream"
    UNKNOWN = "unknown"
    MESSAGE = "message"


def get_artifact_type(value, build_result=None) -> str:
    result = ArtifactType.UNKNOWN
    match value:
        case Message():
            result = (
                ArtifactType.MESSAGE if isinstance(value.text, str) else ArtifactType(get_artifact_type(value.text))
            )
        case Data():
            result = ArtifactType(get_artifact_type(value.data))
        case str():
            result = ArtifactType.TEXT
        case dict():
            result = ArtifactType.OBJECT
        case list() | DataFrame():
            result = ArtifactType.ARRAY
    if (result == ArtifactType.UNKNOWN and (build_result and isinstance(build_result, Generator))) or (
        isinstance(value, Message) and isinstance(value.text, Generator)
    ):
        result = ArtifactType.STREAM
    return result.value


def _to_list_of_dicts(raw):
    raw_ = []
    for item in raw:
        if hasattr(item, "dict") or hasattr(item, "model_dump"):
            raw_.append(recursive_serialize_or_str(item))
        else:
            raw_.append(str(item))
    return raw_


def post_process_raw(raw, artifact_type: str):
    match artifact_type:
        case ArtifactType.STREAM.value:
            raw = ""
        case ArtifactType.ARRAY.value:
            raw = raw.to_dict(orient="records") if isinstance(raw, DataFrame) else _to_list_of_dicts(raw)
        case ArtifactType.UNKNOWN.value if raw is not None:
            if isinstance(raw, (BaseModel, dict)):
                try:
                    raw = jsonable_encoder(raw, custom_encoder=CUSTOM_ENCODERS)
                except Exception:  # noqa: BLE001
                    logger.opt(exception=True).debug(f"Error converting to json: {raw} ({type(raw)})")
                    raw = "Built Successfully ✨"
                artifact_type = ArtifactType.OBJECT.value
            else:
                raw = "Built Successfully ✨"
    return raw, artifact_type
