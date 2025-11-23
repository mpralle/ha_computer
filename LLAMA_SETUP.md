# Setting Up llama.cpp for Tool Calling

The integration works best with tool calling enabled, which allows the LLM to control devices, access memory, manage shopping lists, and more.

## ✅ Quick Fix for Your Issue

The error you're seeing means your llama.cpp version doesn't fully support the tool calling format we're using. Here are solutions:

### Solution 1: Update llama.cpp (Recommended)

Use the latest llama.cpp server:

```bash
# Stop your current server, then:
docker pull ghcr.io/ggerganov/llama.cpp:server-cuda

# Restart with --jinja flag:
docker run --rm --gpus all -p 8080:8080 \
  ghcr.io/ggerganov/llama.cpp:server-cuda \
  -hf acon96/Home-1B-v3-GGUF:Q4_K_M \
  --host 0.0.0.0 --port 8080 \
  --jinja
```

### Solution 2: Use Without Tools (Basic Mode)

The integration now automatically falls back to basic conversation mode if tools aren't supported. You'll see this warning in the logs:

```
llama.cpp server doesn't support tools properly. Falling back to basic conversation mode.
```

**Basic mode limitations**:
- ❌ No device control (can't turn on lights, etc.)
- ❌ No memory storage
- ❌ No shopping list management
- ❌ No calendar access
- ✅ Still works for basic Q&A conversations

### Solution 3: Use a Compatible Model

Some models have better tool calling support than others:

**Best for Tool Calling**:
- `acon96/Home-1B-v3-GGUF` (specifically designed for Home Assistant)
- `NousResearch/Hermes-3-Llama-3.1-8B-GGUF`
- `Qwen/Qwen2.5-7B-Instruct-GGUF`

**Start command with Home-1B-v3**:
```bash
docker run --rm --gpus all -p 8080:8080 \
  ghcr.io/ggerganov/llama.cpp:server-cuda \
  -hf acon96/Home-1B-v3-GGUF:Q4_K_M \
  --host 0.0.0.0 --port 8080 \
  --jinja
```

---

## Understanding the Error

The errors you saw:

1. **"tools param requires --jinja flag"**
   - llama.cpp was started without `--jinja`
   - Solution: Add `--jinja` to startup command

2. **"Unknown method: keys"**
   - Your llama.cpp version has an older Jinja template parser
   - Solution: Update llama.cpp to latest version

---

## Verifying Tool Support

Test if your setup supports tools:

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "test"}],
    "tools": [{"type": "function", "function": {"name": "test", "parameters": {"type": "object", "properties": {}}}}],
    "max_tokens": 10
  }'
```

**Success**: Returns JSON with "choices"  
**Failure**: Returns error about tools or jinja

---

## Current Behavior

With the latest update, the integration:

1. **Tries with tools first** (normal mode)
2. **If server doesn't support tools**: Automatically switches to basic conversation mode
3. **Logs a warning**: So you know tools aren't available
4. **Continues working**: For basic Q&A, just without device control

---

## Recommended Setup

For the **best experience**:

```bash
# 1. Pull latest llama.cpp
docker pull ghcr.io/ggerganov/llama.cpp:server-cuda

# 2. Start with Home Assistant optimized model
docker run --rm --gpus all -p 8080:8080 \
  ghcr.io/ggerganov/llama.cpp:server-cuda \
  -hf acon96/Home-1B-v3-GGUF:Q4_K_M \
  --host 0.0.0.0 --port 8080 \
  --jinja \
  -ngl 99  # Use GPU for all layers

# 3. Restart Home Assistant integration (reload it)

# 4. Test with: "Turn on the lights" or "What time is it?"
```

---

## Troubleshooting

### Still getting Jinja errors after adding --jinja

**Update llama.cpp**:
```bash
# For Docker
docker pull ghcr.io/ggerganov/llama.cpp:server-cuda

# For manual build
cd llama.cpp
git pull
make clean
make
```

### Want to force tools off

This isn't currently a config option, but the integration automatically detects and disables tools when they fail.

### Need more help

Check the Home Assistant logs:
```
Settings → System → Logs
Filter: llamacpp_assist
```

Look for:
- `"Falling back to basic conversation mode"` - Tools disabled, basic mode active
- `"Initialized Llama.cpp conversation agent with 15 tools"` - Tools attempted
- `"Calling llama.cpp (iteration X, tools=True)"` - Using tools
- `"Calling llama.cpp (iteration X, tools=False)"` - Not using tools

---

## What Works in Each Mode

### 🔧 With Tools (Full Mode)
✅ Natural language device control  
✅ Memory storage and retrieval  
✅ Shopping list management  
✅ Calendar access  
✅ Entity state queries  
✅ Service calls  
✅ All 15 tools available  

### 💬 Without Tools (Basic Mode)
✅ General conversation  
✅ Q&A about topics  
❌ No device control  
❌ No memory  
❌ No shopping list  
❌ No calendar  

---

## Next Steps

1. **Restart your llama.cpp server with the latest version + --jinja**
2. **Reload the integration** in Home Assistant (Settings → Devices & Services → Llama.cpp Assist → Reload)
3. **Test**: Ask "What time is it?" (uses tools) or "Turn on the kitchen light"
4. **Check logs**: Confirm you see `tools=True` in debug logs

If you continue having issues, the integration will work in basic mode for now, and you can upgrade llama.cpp when convenient.
