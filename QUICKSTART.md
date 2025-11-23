# Quick Start Guide - Getting Your First Response

You've successfully installed and configured the integration! Here's how to start testing:

## ⚡ Fastest Way to Test (Text Only)

### Step 1: Open Assist Panel
- Look for the **💬 chat bubble icon** in your Home Assistant sidebar (left side)
- Click it to open the Assist panel

### Step 2: Select Llama.cpp Assist
- At the **top right** of the Assist panel, click the **⚙️ gear/settings icon**
- You'll see a dropdown labeled **"Conversation agent"**
- Select **"Llama.cpp Assist"** from the list
- Close the settings (click outside or press ESC)

### Step 3: Send a Test Message
Type one of these:
- `Hello`
- `What time is it?`
- `List all lights`

You should get a response from your llama.cpp server!

---

## 🎤 Setting Up Voice Control (Optional)

### Step 1: Create a Voice Assistant
1. Go to **Settings** → **Voice assistants**
2. Click **"+ Add assistant"**
3. Name it (e.g., "Llama Home")

### Step 2: Configure the Agent
- **Conversation agent**: Select **"Llama.cpp Assist"**
- **Speech-to-text (STT)**: Choose your preferred option
  - **Whisper** (best quality, local)
  - **Piper** (lightweight, local)
  - **Google** (cloud, requires internet)
- **Text-to-speech (TTS)**: Choose your preferred option
  - **Piper** (natural sounding, local)
  - **Google** (cloud, requires internet)

### Step 3: Save and Test
- Click **"Create"**
- Use a voice device or the Assist panel with microphone icon

---

## 🔍 Verify It's Working

### Check 1: Integration is Loaded
1. **Settings** → **Devices & Services**
2. Find **"Llama.cpp Assist"** in your integrations
3. Should show your server URL and model name

### Check 2: Agent is Registered
1. Open Assist panel (💬 icon)
2. Click settings gear (⚙️)
3. **"Llama.cpp Assist"** should be in the conversation agent dropdown

### Check 3: Server is Responding
Test your llama.cpp server directly:
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "test"}],
    "max_tokens": 10
  }'
```

Expected: JSON response with "choices" array

---

## 🚨 Troubleshooting

### "Llama.cpp Assist" Not in Dropdown

**Solution 1: Restart Home Assistant**
```
Settings → System → Restart
```
Wait 1-2 minutes, then check again.

**Solution 2: Check Logs**
```
Settings → System → Logs
```
Filter by: `llamacpp_assist`

Look for:
- ✅ **"Initialized Llama.cpp conversation agent with 15 tools"** = Working
- ❌ **Import errors or exceptions** = Problem (see TROUBLESHOOTING.md)

**Solution 3: Reload Integration**
1. Settings → Devices & Services
2. Find "Llama.cpp Assist"
3. Click ⋮ (three dots) → Reload

### Messages Don't Get a Response

**Check llama.cpp server status:**
```bash
# Should return models list
curl http://localhost:8080/v1/models
```

**Check Home Assistant can reach it:**
```bash
# If HA is in Docker:
docker exec homeassistant curl http://HOST_IP:8080/health

# Replace HOST_IP with your server's IP
```

**Increase timeout:**
1. Settings → Devices & Services → Llama.cpp Assist
2. Click "Configure"
3. Increase timeout to 60 seconds
4. Try again

### Responses are Slow (>10 seconds)

**Quick fixes:**
1. Lower max_tokens: Settings → Configure → Set to 256
2. Lower temperature: Settings → Configure → Set to 0.5
3. Use GPU for llama.cpp server (see README)
4. Use smaller model (1B-3B parameters)

---

## ✅ Example Test Sequence

Try these in order to verify functionality:

### 1. Basic Response
**Input:** `Hello, how are you?`  
**Expected:** Friendly greeting from LLM

### 2. Time/Date (Tests utility tools)
**Input:** `What time is it?`  
**Expected:** Current time (from `get_time()` tool)

### 3. Entity Listing (Tests HA integration)
**Input:** `List all lights`  
**Expected:** List of your light entities

### 4. Device Control (Tests service calls)
**Input:** `Turn on the kitchen light`  
**Expected:** Light turns on + confirmation message
*(Adjust entity name to match your setup)*

### 5. Memory (Tests persistence)
**Input:** `Remember that my favorite color is blue`  
**Expected:** Confirmation of storage

**Then:** `What is my favorite color?`  
**Expected:** "Blue" (from memory)

### 6. Shopping List (Tests integration)
**Input:** `Add milk to my shopping list`  
**Expected:** Confirmation of addition

---

## 📊 Success Criteria

You're all set when you can:
- ✅ See "Llama.cpp Assist" in conversation agent dropdown
- ✅ Get responses to simple messages
- ✅ Control at least one device
- ✅ Store and retrieve a memory item

---

## 📚 Next Steps

Once basic functionality works:

1. **Explore Examples**: Check [EXAMPLES.md](EXAMPLES.md) for advanced scenarios
2. **Customize System Prompt**: Settings → Configure → Add custom instructions
3. **Optimize Performance**: See README.md performance tips
4. **Add More Tools**: Review the tool framework in the code
5. **Set Up Voice**: Configure STT/TTS for hands-free control

---

## 🆘 Still Stuck?

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for:
- Detailed diagnostic steps
- Common error solutions
- Debug logging configuration
- Performance optimization

Or check logs:
```
Settings → System → Logs
Filter: llamacpp_assist
```

Good luck! 🚀
