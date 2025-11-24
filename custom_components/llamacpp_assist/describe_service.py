from typing import Any
import logging
from custom_components.llamacpp_assist.tools import Tool

_LOGGER = logging.getLogger(__name__)


class DescribeServiceTool(Tool):
    """Tool to inspect Home Assistant service schema and fields."""

    @property
    def name(self) -> str:
        return "describe_service"

    @property
    def description(self) -> str:
        return (
            "Get information about a Home Assistant service: its description, "
            "required/optional fields, and example data. Use this if you are "
            "unsure how to call a specific service."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Service domain (e.g., 'light', 'switch', 'climate')",
                },
                "service": {
                    "type": "string",
                    "description": "Service name (e.g., 'turn_on', 'turn_off', 'set_temperature')",
                },
            },
            "required": ["domain", "service"],
        }

    async def async_call(
        self,
        domain: str,
        service: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Return description for a given service."""
        try:
            # async_get_all_descriptions returns a nested dict: {domain: {service: {...}}}
            descriptions = await self.hass.services.async_get_all_descriptions()
            domain_info = descriptions.get(domain, {})
            service_info = domain_info.get(service)

            if not service_info:
                return {
                    "success": False,
                    "error": f"Service {domain}.{service} not found",
                }

            return {
                "success": True,
                "domain": domain,
                "service": service,
                "description": service_info,
            }

        except Exception as err:
            _LOGGER.error("describe_service failed: %s", err)
            return {
                "success": False,
                "error": str(err),
            }
