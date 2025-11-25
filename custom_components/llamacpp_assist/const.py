"""Constants for the Llama.cpp Assist integration."""

DOMAIN = "llamacpp_assist"

# Configuration
CONF_SERVER_URL = "server_url"
CONF_API_KEY = "api_key"
CONF_MODEL_NAME = "model_name"
CONF_TEMPERATURE = "temperature"
CONF_MAX_TOKENS = "max_tokens"
CONF_TIMEOUT = "timeout"
CONF_SYSTEM_PROMPT_PREFIX = "system_prompt_prefix"
CONF_ENABLE_MULTI_AGENT = "enable_multi_agentic_system"

# Defaults
DEFAULT_SERVER_URL = "http://localhost:8080"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 512
DEFAULT_TIMEOUT = 30
DEFAULT_MODEL_NAME = "llama.cpp"

# Storage
STORAGE_KEY = "llamacpp_assist_memory"
STORAGE_VERSION = 1

# Tool categories
TOOL_CATEGORY_HA = "home_assistant"
TOOL_CATEGORY_MEMORY = "memory"
TOOL_CATEGORY_SHOPPING = "shopping_list"
TOOL_CATEGORY_CALENDAR = "calendar"
TOOL_CATEGORY_UTILITY = "utility"

# Error messages
ERROR_SERVER_UNREACHABLE = "llama.cpp server is unreachable"
ERROR_INVALID_RESPONSE = "Invalid response from llama.cpp server"
ERROR_TOOL_EXECUTION_FAILED = "Tool execution failed"
ERROR_MEMORY_READ_FAILED = "Failed to read memory"
ERROR_MEMORY_WRITE_FAILED = "Failed to write memory"
