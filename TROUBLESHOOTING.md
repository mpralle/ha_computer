# Troubleshooting Guide for Llama.cpp Assist

## Integration Not Appearing in Assist

If you've successfully installed and configured the integration but cannot see it in the Assist interface, follow these steps:

### Step 1: Verify Integration is Loaded

1. Go to **Settings** → **System** → **Logs**
2. Look for log entries containing `llamacpp_assist`
3. You should see a line like:
   ```
   Initialized Llama.cpp conversation agent with 15 tools
   ```

### Step 2: Check Configuration Entry

1. Go to **Settings** → **Devices & Services**
2. Find "Llama.cpp Assist" in your integrations
3. Click on it to ensure configuration is complete
4. You should see the server URL and model name

### Step 3: Select the Conversation Agent

The integration registers as a **conversation agent**, not as a standalone interface. You need to select it in Assist settings:

#### For Voice Assistants:

1. Go to **Settings** → **Voice assistants**
2. If you don't have a voice assistant yet, click **"+ Add assistant"**
3. Give it a name (e.g., "Llama Assistant")
4. Under **Conversation agent**, select **"Llama.cpp Assist"** from the dropdown
5. Configure Speech-to-Text (STT) and Text-to-Speech (TTS) if needed
6. Click **Create** or **Update**

#### For Text-Only Testing:

1. Click the **Assist** button in the sidebar (💬 icon)
2. At the top of the Assist panel, click the **⚙️ (settings/gear)** icon
3. Under **Conversation agent**, select **"Llama.cpp Assist"**
4. Close settings and try typing a message

### Step 4: Test the Integration

Once selected, try these test phrases:

**Simple test**:
- Type: "Hello"
- Expected: A greeting response from the LLM

**Entity query**:
- Type: "List all lights"
- Expected: LLM calls `list_entities` tool and responds with a list

**Device control** (if you have lights):
- Type: "Turn on the kitchen light"
- Expected: LLM calls `call_service` to control the light

### Step 5: Check Llama.cpp Server Connection

If the agent is selected but not responding:

1. Verify llama.cpp server is running:
   ```bash
   curl http://localhost:8080/v1/models
   ```

2. Check Home Assistant logs for errors:
   ```
   Settings → System → Logs
   Filter: llamacpp_assist
   ```

3. Common errors and solutions:
   - **"Connection timeout"**: Increase timeout in integration options
   - **"Invalid response"**: Ensure llama.cpp server supports OpenAI API format
   - **"Tool not found"**: Normal - LLM attempted unavailable tool, should retry

### Step 6: Reload Integration (if needed)

If changes were made after initial setup:

1. Go to **Settings** → **Devices & Services**
2. Find "Llama.cpp Assist"
3. Click the **⋮** (three dots) menu
4. Select **"Reload"**
5. Wait for reload to complete
6. Try selecting the agent again

---

## Common Issues

### "Llama.cpp Assist" doesn't appear in conversation agent dropdown

**Solutions**:
1. Restart Home Assistant completely
2. Check that the integration is enabled (not disabled)
3. Verify no errors in logs during startup
4. Ensure `conversation.py` is properly loaded (check logs)

### Agent is selected but shows "Agent not available"

**Solutions**:
1. Check llama.cpp server is accessible from Home Assistant host
2. Test with: `docker exec homeassistant curl http://YOUR_SERVER:8080/health`
3. Verify API key if server requires authentication
4. Check firewall rules

### Responses are very slow (>10 seconds)

**Solutions**:
1. Use GPU acceleration for llama.cpp
2. Reduce `max_tokens` in integration options (try 256)
3. Use a smaller model (1B-3B parameters)
4. Lower temperature for faster, more deterministic responses
5. Increase timeout in integration options

### LLM doesn't call tools / doesn't control devices

**Solutions**:
1. Verify model supports function calling (Home-1B-v3, Hermes, Llama 3+)
2. Check system prompt includes tool descriptions (enable debug logs)
3. Lower temperature (0.5-0.7 works best for tool calling)
4. Try explicit commands: "Use the call_service tool to turn on light.kitchen"

### Tool execution errors in logs

**Solutions**:
1. **"Entity not found"**: Check entity_id exists in HA
2. **"Service not found"**: Verify service is available (e.g., `light.turn_on`)
3. **"shopping_list not loaded"**: Enable shopping_list integration
4. **"calendar.create_event failed"**: Ensure calendar integration supports event creation

---

## Debug Mode

To enable detailed logging:

1. Edit `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.llamacpp_assist: debug
   ```

2. Restart Home Assistant

3. Check logs for detailed information:
   - System prompt generation
   - Tool calling
   - LLM requests and responses
   - Tool execution results

---

## Quick Verification Checklist

- [ ] Integration appears in **Settings → Devices & Services**
- [ ] Configuration shows server URL and model name
- [ ] Logs show "Initialized Llama.cpp conversation agent with 15 tools"
- [ ] llama.cpp server responds to curl test
- [ ] Created/selected voice assistant or clicked Assist sidebar button
- [ ] "Llama.cpp Assist" appears in conversation agent dropdown
- [ ] Selected "Llama.cpp Assist" as the active agent
- [ ] Test message returns a response (even if simple)

---

## Still Not Working?

If you've completed all steps and it's still not working:

1. **Collect diagnostic information**:
   - Full Home Assistant logs
   - llama.cpp server logs
   - Integration configuration (from Devices & Services)
   - Model being used
   - Hardware (CPU/GPU)

2. **Create a GitHub issue** with:
   - Title: "Conversation agent not appearing in Assist UI"
   - Description of what you tried
   - Logs (with sensitive info redacted)
   - HA version and installation type (Docker, HAOS, Core, etc.)

3. **Temporary workaround**:
   - If nothing works, try reinstalling:
     1. Remove integration from Devices & Services
     2. Restart Home Assistant
     3. Delete `.storage/llamacpp_assist*` files
     4. Re-add integration
     5. Restart again
     6. Configure voice assistant

---

## Expected Behavior (Working Correctly)

When everything is working, you should see:

1. **In Settings → Voice Assistants**:
   - Your voice assistant listed
   - "Llama.cpp Assist" shown as conversation agent

2. **In Assist panel**:
   - Settings gear shows "Llama.cpp Assist" selected
   - Typing messages gets responses from LLM

3. **In Logs**:
   - "Initialized Llama.cpp conversation agent with 15 tools"
   - "Processing conversation input: [your message]"
   - "Calling llama.cpp (iteration 1): [server URL]"
   - Tool execution messages (if tools are called)
   - Response generation

4. **In Practice**:
   - Natural language responses
   - Device control works
   - Memory stores preferences
   - Shopping list updates
   - Calendar queries work

---

## Performance Expectations

- **Response time with GPU**: 0.5-2 seconds
- **Response time with CPU**: 5-15 seconds
- **First response** (cold start): +2-5 seconds (model loading)
- **Tool calling overhead**: +0.5 seconds per tool call
- **Network latency**: Minimal if local (< 50ms)

If your responses are significantly slower, review the performance tips in README.md.
