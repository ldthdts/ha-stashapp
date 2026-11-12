"""Async GraphQL client for Stash."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse, urlunparse

from aiohttp import ClientError, ClientSession

from .const import ACTIVE_JOB_STATUSES, REQUEST_TIMEOUT

STATS_QUERY = """
query HomeAssistantStats {
  version { version }
  stats {
    scene_count
    scenes_size
    scenes_duration
    image_count
    images_size
    gallery_count
    performer_count
    studio_count
    tag_count
    total_o_count
    total_play_count
    total_play_duration
    scenes_played
  }
  findSceneMarkers { count }
  jobQueue { status }
}
"""

RANDOM_IMAGE_QUERY = """
query HomeAssistantRandomImage($filter: FindFilterType, $imageFilter: ImageFilterType) {
  findImages(filter: $filter, image_filter: $imageFilter) {
    images { id title paths { image } }
  }
}
"""

RANDOM_SCENE_QUERY = """
query HomeAssistantRandomScene($filter: FindFilterType, $sceneFilter: SceneFilterType) {
  findScenes(filter: $filter, scene_filter: $sceneFilter) {
    scenes { id title paths { screenshot } }
  }
}
"""

SCAN_MUTATION = """
mutation HomeAssistantScan($input: ScanMetadataInput!) {
  metadataScan(input: $input)
}
"""

VERSION_QUERY = "query HomeAssistantVersion { version { version } }"


class StashError(Exception):
    """Base error for Stash API."""


class StashAuthenticationError(StashError):
    """Authentication with Stash failed."""


class StashConnectionError(StashError):
    """Communication with Stash failed."""


def _int(source: dict[str, Any], key: str) -> int:
    value = source.get(key)
    return int(value) if value is not None else 0


def _float(source: dict[str, Any], key: str) -> float:
    value = source.get(key)
    return float(value) if value is not None else 0.0


def _random_filter() -> dict[str, Any]:
    return {"per_page": 1, "page": 1, "sort": "random"}


def _tag_filter(tag_ids: list[str] | None) -> dict[str, Any] | None:
    if not tag_ids:
        return None
    return {"tags": {"value": tag_ids, "modifier": "INCLUDES"}}


class StashClient:
    """Async GraphQL client for Stash."""

    def __init__(
        self,
        graphql_url: str,
        session: ClientSession,
        api_key: str | None = None,
    ) -> None:
        self._url = graphql_url.rstrip("/")
        self._session = session
        self._api_key = (api_key or "").strip()

    @property
    def base_url(self) -> str:
        """Return the Stash web UI URL."""
        parsed = urlparse(self._url)
        path = parsed.path.rstrip("/")
        path = path.removesuffix("/graphql")
        return urlunparse(
            parsed._replace(path=path, params="", query="", fragment="")
        ).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {"ApiKey": self._api_key} if self._api_key else {}

    def _absolute(self, url: str) -> str:
        if url.startswith(("http://", "https://")):
            return url
        return f"{self.base_url}/{url.lstrip('/')}"

    async def _post(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a GraphQL request and return its ``data`` payload."""
        payload: dict[str, Any] = {"query": query}
        if variables is not None:
            payload["variables"] = variables

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.post(
                    self._url, json=payload, headers=self._headers()
                ) as resp:
                    if resp.status in (401, 403):
                        raise StashAuthenticationError(
                            f"Authentication failed with HTTP {resp.status}"
                        )
                    if resp.status != 200:
                        text = await resp.text()
                        raise StashConnectionError(
                            f"HTTP {resp.status} from Stash: {text[:500]}"
                        )
                    body: dict[str, Any] = await resp.json()
        except StashError:
            raise
        except TimeoutError as err:
            raise StashConnectionError("Timed out waiting for Stash") from err
        except ClientError as err:
            raise StashConnectionError(f"Cannot connect to Stash: {err}") from err
        except ValueError as err:
            raise StashConnectionError("Stash returned invalid JSON") from err

        if body.get("errors"):
            raise StashError(f"GraphQL error: {body['errors']}")
        return body.get("data") or {}

    async def async_test_connection(self) -> str | None:
        """Validate the endpoint and return the Stash version."""
        data = await self._post(VERSION_QUERY)
        return str((data.get("version") or {}).get("version") or "") or None

    async def async_get_stats(self) -> dict[str, Any]:
        """Fetch library statistics and job state."""
        data = await self._post(STATS_QUERY)
        stats = data.get("stats") or {}
        jobs = data.get("jobQueue") or []
        version = (data.get("version") or {}).get("version")
        markers = data.get("findSceneMarkers") or {}

        return {
            "version": str(version) if version else None,
            "scenes": _int(stats, "scene_count"),
            "images": _int(stats, "image_count"),
            "galleries": _int(stats, "gallery_count"),
            "performers": _int(stats, "performer_count"),
            "studios": _int(stats, "studio_count"),
            "tags": _int(stats, "tag_count"),
            "markers": _int(markers, "count"),
            "scenes_size": _float(stats, "scenes_size"),
            "images_size": _float(stats, "images_size"),
            "scenes_duration": _float(stats, "scenes_duration"),
            "total_o_count": _int(stats, "total_o_count"),
            "total_play_count": _int(stats, "total_play_count"),
            "total_play_duration": _float(stats, "total_play_duration"),
            "scenes_played": _int(stats, "scenes_played"),
            "active_jobs": sum(
                1
                for job in jobs
                if str((job or {}).get("status", "")).upper() in ACTIVE_JOB_STATUSES
            ),
        }

    async def async_get_random_image(
        self, tag_ids: list[str] | None = None
    ) -> dict[str, str] | None:
        """Return a random image, optionally limited to the given tag IDs."""
        data = await self._post(
            RANDOM_IMAGE_QUERY,
            {"filter": _random_filter(), "imageFilter": _tag_filter(tag_ids)},
        )
        images = (data.get("findImages") or {}).get("images") or []
        if not images:
            return None

        image = images[0]
        image_url = (image.get("paths") or {}).get("image")
        if not image_url:
            return None
        return {
            "id": str(image["id"]),
            "title": image.get("title") or "",
            "image_url": self._absolute(image_url),
        }

    async def async_get_random_scene(
        self, tag_ids: list[str] | None = None
    ) -> dict[str, str] | None:
        """Return a random scene, optionally limited to the given tag IDs."""
        data = await self._post(
            RANDOM_SCENE_QUERY,
            {"filter": _random_filter(), "sceneFilter": _tag_filter(tag_ids)},
        )
        scenes = (data.get("findScenes") or {}).get("scenes") or []
        if not scenes:
            return None

        scene = scenes[0]
        scene_id = str(scene["id"])
        screenshot = (scene.get("paths") or {}).get("screenshot")
        return {
            "id": scene_id,
            "title": scene.get("title") or "",
            "url": f"{self.base_url}/scenes/{scene_id}",
            "screenshot_url": self._absolute(screenshot) if screenshot else "",
        }

    async def async_fetch_image(self, url: str) -> tuple[bytes, str]:
        """Download an image from Stash and return its bytes and content type."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.get(
                    self._absolute(url), headers=self._headers()
                ) as resp:
                    if resp.status in (401, 403):
                        raise StashAuthenticationError(
                            f"Authentication failed with HTTP {resp.status}"
                        )
                    if resp.status != 200:
                        raise StashConnectionError(
                            f"HTTP {resp.status} fetching image from Stash"
                        )
                    content = await resp.read()
                    content_type = resp.content_type or "image/jpeg"
        except StashError:
            raise
        except (TimeoutError, ClientError) as err:
            raise StashConnectionError(f"Cannot fetch image from Stash: {err}") from err
        return content, content_type

    async def async_metadata_scan(self) -> str:
        """Start a full library scan and return its job id."""
        data = await self._post(SCAN_MUTATION, {"input": {}})
        job_id = data.get("metadataScan")
        if job_id is None:
            raise StashError("Stash did not return a job id for the scan")
        return str(job_id)
