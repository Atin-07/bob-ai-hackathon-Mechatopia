"""Pydantic data models for cameras returned by the catalogue endpoint."""

from pydantic import BaseModel, field_validator

_VALID_CODECS = {"H264", "H265"}


class StreamProperties(BaseModel):
    """Encoding / delivery properties of a single camera's stream."""

    width: int
    height: int
    fps: int
    bitrate_kbps: int


class Camera(BaseModel):
    """A single camera entry as returned by GET /api/ingest."""

    camera_id: str
    organization_id: str
    name: str
    location: str
    codec: str
    live: bool
    stream_properties: StreamProperties
    rtsp_url: str
    webrtc_url: str
    hls_url: str

    @field_validator("codec")
    @classmethod
    def normalize_codec(cls, value: str) -> str:
        """Normalize codec to uppercase and ensure it is a supported value."""

        normalized = value.strip().upper()

        if normalized not in _VALID_CODECS:
            raise ValueError(
                f"Unsupported codec '{value}'. Expected one of: "
                f"{sorted(_VALID_CODECS)}"
            )

        return normalized

    @property
    def is_h264(self) -> bool:
        """True if this camera's stream is encoded as H.264."""

        return self.codec == "H264"

    @property
    def is_h265(self) -> bool:
        """True if this camera's stream is encoded as H.265."""

        return self.codec == "H265"