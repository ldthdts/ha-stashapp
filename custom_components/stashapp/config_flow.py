"""Config flow for the Stash integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .api import StashAuthenticationError, StashClient, StashError
from .const import (
    CONF_API_KEY,
    CONF_AUTO_REFRESH_SECONDS,
    CONF_TAGS,
    CONF_URL,
    DOMAIN,
    MAX_AUTO_REFRESH_SECONDS,
    MIN_AUTO_REFRESH_SECONDS,
    SUBENTRY_TYPE_FEED,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_API_KEY, default=""): cv.string,
    }
)

REAUTH_SCHEMA = vol.Schema({vol.Optional(CONF_API_KEY, default=""): cv.string})

FEED_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_TAGS): TextSelector(TextSelectorConfig(multiple=True)),
        vol.Optional(CONF_AUTO_REFRESH_SECONDS): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=MAX_AUTO_REFRESH_SECONDS,
                step=1,
                unit_of_measurement="s",
                mode=NumberSelectorMode.BOX,
            )
        ),
    }
)


def _to_graphql_url(url: str) -> str:
    """Accept either the Stash base URL or the full /graphql endpoint."""
    url = url.strip().rstrip("/")
    if not url.endswith("/graphql"):
        url = f"{url}/graphql"
    return url


def _auto_refresh_seconds(user_input: dict[str, Any]) -> int:
    """Auto refresh interval in seconds; 0 means auto refresh is off."""
    return int(user_input.get(CONF_AUTO_REFRESH_SECONDS) or 0)


def _feed_data(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_TAGS: user_input.get(CONF_TAGS) or [],
        CONF_AUTO_REFRESH_SECONDS: _auto_refresh_seconds(user_input),
    }


def _auto_refresh_too_short(user_input: dict[str, Any]) -> bool:
    seconds = _auto_refresh_seconds(user_input)
    return 0 < seconds < MIN_AUTO_REFRESH_SECONDS


class StashFeedSubentryFlow(ConfigSubentryFlow):
    """Add or edit an image feed: random images limited to a set of tags."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a new image feed."""
        errors: dict[str, str] = {}
        schema = FEED_SCHEMA
        if user_input is not None:
            if not _auto_refresh_too_short(user_input):
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=_feed_data(user_input)
                )
            errors["base"] = "auto_refresh_too_short"
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an existing image feed."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _auto_refresh_too_short(user_input):
                return self.async_update_and_abort(
                    entry,
                    subentry,
                    title=user_input[CONF_NAME],
                    data=_feed_data(user_input),
                )
            errors["base"] = "auto_refresh_too_short"
            schema = self.add_suggested_values_to_schema(FEED_SCHEMA, user_input)
        else:
            schema = self.add_suggested_values_to_schema(
                FEED_SCHEMA,
                {
                    CONF_NAME: subentry.title,
                    CONF_TAGS: subentry.data.get(CONF_TAGS, []),
                    CONF_AUTO_REFRESH_SECONDS: subentry.data.get(
                        CONF_AUTO_REFRESH_SECONDS, 0
                    ),
                },
            )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )


class StashConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Stash."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Image feeds can be added to a Stash server."""
        return {SUBENTRY_TYPE_FEED: StashFeedSubentryFlow}

    def _client(self, graphql_url: str, api_key: str) -> StashClient:
        return StashClient(graphql_url, async_get_clientsession(self.hass), api_key)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the Stash URL and optional API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            graphql_url = _to_graphql_url(user_input[CONF_URL])
            api_key = user_input[CONF_API_KEY]
            client = self._client(graphql_url, api_key)
            try:
                await client.async_test_connection()
            except StashAuthenticationError:
                errors["base"] = "invalid_auth"
            except StashError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(client.base_url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Stash",
                    data={CONF_URL: graphql_url, CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start re-authentication after Stash rejected the API key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            client = self._client(entry.data[CONF_URL], api_key)
            try:
                await client.async_test_connection()
            except StashAuthenticationError:
                errors["base"] = "invalid_auth"
            except StashError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"url": entry.data[CONF_URL]},
        )
