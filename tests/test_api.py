"""Tests for the Stash GraphQL client."""

from __future__ import annotations

from typing import Any
from unittest import IsolatedAsyncioTestCase

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer

from custom_components.stashapp.api import (
    StashAuthenticationError,
    StashClient,
)

IMAGE_BYTES = b"\xff\xd8\xff fake jpeg"


class FakeStash:
    """Minimal Stash server that records requests."""

    def __init__(self) -> None:
        self.status = 200
        self.data: dict[str, Any] = {}
        self.requests: list[dict[str, Any]] = []
        self.image_api_key: str | None = None

    async def graphql(self, request: web.Request) -> web.Response:
        payload = await request.json()
        self.requests.append(payload | {"api_key": request.headers.get("ApiKey")})
        if self.status != 200:
            return web.Response(status=self.status, text="rejected")
        return web.json_response({"data": self.data})

    async def image(self, request: web.Request) -> web.Response:
        self.image_api_key = request.headers.get("ApiKey")
        return web.Response(body=IMAGE_BYTES, content_type="image/jpeg")


class StashClientTest(IsolatedAsyncioTestCase):
    """Exercise the client against a fake Stash server."""

    async def asyncSetUp(self) -> None:
        self.fake = FakeStash()
        app = web.Application()
        app.router.add_post("/graphql", self.fake.graphql)
        app.router.add_get("/image/1/image", self.fake.image)
        self.server = TestServer(app)
        await self.server.start_server()
        self.session = ClientSession()
        self.addAsyncCleanup(self.session.close)
        self.addAsyncCleanup(self.server.close)
        self.client = StashClient(
            str(self.server.make_url("/graphql")), self.session, "secret"
        )

    async def test_stats_are_parsed_and_api_key_is_sent(self) -> None:
        self.fake.data = {
            "version": {"version": "0.27.0"},
            "stats": {
                "scene_count": 12,
                "scenes_size": 2147483648.0,
                "scenes_duration": 7200.0,
                "image_count": 5,
                "total_play_count": 40,
                "total_play_duration": 3600.0,
            },
            "findSceneMarkers": {"count": 3},
            "jobQueue": [{"status": "RUNNING"}, {"status": "FINISHED"}],
        }

        stats = await self.client.async_get_stats()

        self.assertEqual(stats["version"], "0.27.0")
        self.assertEqual(stats["scenes"], 12)
        self.assertEqual(stats["markers"], 3)
        self.assertEqual(stats["scenes_size"], 2147483648.0)
        self.assertEqual(stats["galleries"], 0)
        self.assertEqual(stats["active_jobs"], 1)
        self.assertEqual(self.fake.requests[0]["api_key"], "secret")

    async def test_random_image_applies_tag_filter_and_resolves_relative_url(
        self,
    ) -> None:
        self.fake.data = {
            "findImages": {
                "images": [
                    {"id": "7", "title": "Beach", "paths": {"image": "/image/1/image"}}
                ]
            }
        }

        found = await self.client.async_get_random_image(["3"])

        assert found is not None
        self.assertEqual(found["id"], "7")
        self.assertEqual(found["title"], "Beach")
        self.assertEqual(found["image_url"], f"{self.client.base_url}/image/1/image")
        variables = self.fake.requests[0]["variables"]
        self.assertEqual(variables["filter"]["sort"], "random")
        self.assertEqual(
            variables["imageFilter"],
            {"tags": {"value": ["3"], "modifier": "INCLUDES"}},
        )

    async def test_random_image_returns_none_when_nothing_matches(self) -> None:
        self.fake.data = {"findImages": {"images": []}}

        self.assertIsNone(await self.client.async_get_random_image(["999"]))

    async def test_rejected_api_key_raises_authentication_error(self) -> None:
        self.fake.status = 401

        with self.assertRaises(StashAuthenticationError):
            await self.client.async_test_connection()

    async def test_fetch_image_sends_api_key(self) -> None:
        content, content_type = await self.client.async_fetch_image(
            f"{self.client.base_url}/image/1/image"
        )

        self.assertEqual(content, IMAGE_BYTES)
        self.assertEqual(content_type, "image/jpeg")
        self.assertEqual(self.fake.image_api_key, "secret")
