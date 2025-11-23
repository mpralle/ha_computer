# Llama.cpp Assist - Local AI Assistant for Home Assistant

A fully local, offline-capable Home Assistant custom integration that connects to a **llama.cpp server** and provides intelligent conversation capabilities with device control, persistent memory, shopping list management, and calendar integration through the Assist pipeline.

## Features

✅ **Local & Private** - Runs entirely on your network, no cloud dependencies  
✅ **Natural Language Control** - Control lights, switches, climate, and more  
✅ **Persistent Memory** - Remember preferences, facts, and context  
✅ **Tool/Function Calling** - LLM can directly call HA services  
✅ **Shopping List Integration** - Add/remove items naturally  
✅ **Calendar Management** - Query and create calendar events  
✅ **Context-Aware** - Dynamic system prompts with current time and entity states  
✅ **Multi-Persona Support** - Configure multiple assistants with different behaviors  

---

## Prerequisites

### 1. Llama.cpp Server

You need a running llama.cpp server with OpenAI-compatible API support. The server must expose the `/v1/chat/completions` endpoint.

#### Option A: Docker (Recommended)

```bash
# With CUDA GPU
docker run --rm --gpus all -p 8080:8080 \
  ghcr.io/ggerganov/llama.cpp:server-cuda \
  -m /models/your-model.gguf \
  --host 0.0.0.0 --port 8080

# CPU only
docker run --rm -p 8080:8080 \
  ghcr.io/ggerganov/llama.cpp:server \
  -m /models/your-model.gguf \
  --host 0.0.0.0 --port 8080
```

#### Option B: Manual Installation

```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make
./server -m /path/to/model.gguf --host 0.0.0.0 --port 8080
```

### 2. Recommended Models

For best results with tool calling, use models that support function calling:

- **Home-1B-v3** (lightweight, optimized for HA)
  ```bash
  docker run --rm --gpus all -p 8080:8080 \
    ghcr.io/ggerganov/llama.cpp:server-cuda \
    -hf acon96/Home-1B-v3-GGUF:Q4_K_M \
    --host 0.0.0.0 --port 8080
  ```

- **Llama 3.2 3B** (good balance)
- **Hermes 3** (excellent tool calling)
- **Qwen 2.5** (multilingual support)

---

## Installation

### Method 1: HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right
3. Select "Custom repositories"
4. Add this repository URL
5. Category: Integration
6. Click "Install"
7. Restart Home Assistant

### Method 2: Manual Installation

1. Copy the `custom_components/llamacpp_assist` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

---

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Llama.cpp Assist"
4. Fill in the configuration:
   - **Server URL**: `http://localhost:8080` (or your server address)
   - **API Key**: Optional, if your server requires authentication
   - **Model Name**: Optional, for display purposes
   - **Temperature**: `0.7` (0.0 = deterministic, 2.0 = creative)
   - **Max Tokens**: `512` (maximum response length)
   - **Timeout**: `30` seconds

5. Click **Submit**

The integration will test the connection and register as a conversation agent.

---

## Setting Up as Default Assistant

### For Voice Assistants

1. Go to **Settings** → **Voice Assistants**
2. Select your voice assistant (or create a new one)
3. Under **Conversation Agent**, select **Llama.cpp Assist**
4. Configure STT (Speech-to-Text) and TTS (Text-to-Speech) as desired
5. Save

### For Text Conversations

1. Open the Assist panel (button in the sidebar)
2. Click the settings icon
3. Select **Llama.cpp Assist** as the conversation agent

---

## Usage Examples

### Device Control

**User**: "Turn on the living room lights"  
**Assistant**: *Calls `light.turn_on` on `light.living_room`* "I've turned on the living room lights."

**User**: "Set the thermostat to 21 degrees"  
**Assistant**: *Calls `climate.set_temperature`* "I've set the thermostat to 21 degrees."

**User**: "What's the temperature in the bedroom?"  
**Assistant**: *Calls `get_state('sensor.bedroom_temperature')`* "The bedroom temperature is currently 19.5°C."

### Memory

**User**: "Remember that I like warm lighting in the evening"  
**Assistant**: *Calls `memory_write('preferences.evening_light', 'warm')`* "Got it, I'll remember that you prefer warm lighting in the evening."

**User**: "What do I like in the evening?"  
**Assistant**: *Retrieves from memory* "You like warm lighting in the evening."

### Shopping List

**User**: "Add milk and bread to my shopping list"  
**Assistant**: *Adds items* "I've added milk and bread to your shopping list."

**User**: "What's on my shopping list?"  
**Assistant**: *Lists items* "You have milk, bread, and eggs on your shopping list."

**User**: "Remove eggs from the list"  
**Assistant**: *Removes item* "I've removed eggs from your shopping list."

### Calendar

**User**: "What's on my calendar tomorrow?"  
**Assistant**: *Queries calendar* "You have a dentist appointment at 2 PM and a team meeting at 4 PM."

**User**: "Create a reminder for Friday at 14:00 called dentist appointment"  
**Assistant**: *Creates event* "I've created a calendar event for Friday at 2 PM."

### Contextual Conversations

**User**: "Turn on the lights"  
**Assistant**: "Which room's lights would you like me to turn on?"

**User**: "The bedroom"  
**Assistant**: *Turns on bedroom lights* "I've turned on the bedroom lights."

---

## Available Tools

The assistant has access to the following tools:

### Home Assistant Core
- `get_state(entity_id)` - Get current state and attributes
- `list_entities(domain, area)` - List available entities
- `call_service(domain, service, entity_id, data)` - Execute service calls

### Memory
- `memory_read(key)` - Read from persistent storage
- `memory_write(key, value)` - Store information
- `memory_list_keys()` - List all stored keys

### Shopping List
- `shopping_add_item(item)` - Add item to list
- `shopping_remove_item(item)` - Remove item from list
- `shopping_list_all()` - Get all items

### Calendar
- `calendar_list_events(start, end, calendar_entity)` - List events
- `calendar_create_event(calendar_entity, title, start, end, description)` - Create event

### Utilities
- `get_time()` - Get current time
- `get_date()` - Get current date
- `get_datetime()` - Get current date and time

---

## Advanced Configuration

### Custom System Prompt

You can customize the system prompt to change the assistant's behavior:

1. Go to the integration in **Devices & Services**
2. Click **Configure**
3. Add your custom text to **System Prompt Prefix**

Example:
```
You are a friendly and concise assistant. Keep responses short and to the point.
When controlling devices, always confirm what you did.
```

### Multiple Personas

You can create multiple configurations of this integration for different use cases:

1. **Home Control** - Temperature: 0.5, focused on device control
2. **Creative Mode** - Temperature: 1.5, more conversational
3. **Calendar Assistant** - Custom system prompt focused on scheduling

Each configuration maintains its own memory storage.

---

## Troubleshooting

### "Failed to connect to llama.cpp server"

- Verify the server is running: `curl http://localhost:8080/v1/models`
- Check the URL in the integration configuration
- Ensure there are no firewall rules blocking the connection

### "Server returned an invalid response"

- Ensure your llama.cpp server supports the OpenAI API
- Update llama.cpp to the latest version
- Check the server logs for errors

### "Request timeout"

- Increase the timeout in the integration options
- Check if the server has enough resources (CPU/GPU)
- Try a smaller model or reduce max_tokens

### Tool Calls Not Working

- Verify your model supports function calling
- Check the integration logs for tool execution errors
- Ensure required integrations are installed (shopping_list, calendar)

### View Logs

Check Home Assistant logs for detailed error messages:
```
Settings → System → Logs
```

Filter by `llamacpp_assist` to see integration-specific logs.

---

## Performance Tips

1. **Use a GPU** - Dramatically faster responses (< 1s vs 10s+)
2. **Quantized Models** - Q4_K_M is a good balance of speed and quality
3. **Adjust Max Tokens** - Lower values = faster responses
4. **Lower Temperature** - More deterministic = faster generation
5. **Smaller Models** - 1B-3B models are sufficient for most tasks

---

## Privacy & Data

✅ **100% Local** - No data leaves your network  
✅ **No Telemetry** - No analytics or tracking  
✅ **Encrypted Storage** - Memory stored in Home Assistant's `.storage` folder  
✅ **No Cloud Dependencies** - Works completely offline  

---

## Roadmap

### Planned Features

- [ ] **Streaming responses** - Real-time token generation
- [ ] **Conversation history** - Multi-turn context
- [ ] **RAG (Retrieval Augmented Generation)** - Index documents and manuals
- [ ] **Multi-user profiles** - Per-user memory and preferences
- [ ] **Automation builder** - Generate automations from natural language
- [ ] **Custom tool plugins** - Easy way to add new capabilities
- [ ] **Voice profile integration** - Identify users by voice
- [ ] **Energy advisor** - Smart suggestions for energy saving

---

## Contributing

Contributions are welcome! Please open an issue or pull request.

---

## License

MIT License - See LICENSE file for details

---

## Credits

Built for Home Assistant by the community.

Powered by:
- [llama.cpp](https://github.com/ggerganov/llama.cpp) - Fast LLM inference
- [Home Assistant](https://www.home-assistant.io/) - Open source home automation

---

## Support

- **Issues**: [GitHub Issues](https://github.com/malte/ha_computer/issues)
- **Discussions**: [GitHub Discussions](https://github.com/malte/ha_computer/discussions)
- **Home Assistant Community**: [Community Forum](https://community.home-assistant.io/)
