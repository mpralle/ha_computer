# Using the Multi-Agent System

## Activation

The multi-agent system is now integrated and can be toggled via Home Assistant's configuration UI.

### Steps to Enable

1. **Go to Settings → Devices & Services**
2. **Find "Llama.cpp Assist"** in your integrations
3. **Click "Configure"** (or the three dots → Configure)
4. **Check the box**: ☑️ **"Enable multi-agentic system"**
5. **Click "Submit"**
6. The integration will reload automatically

### What Happens

**When DISABLED (default)**:
- Uses the classic tool-calling conversation pipeline
- Same behavior as before

**When ENABLED**:
- Uses the new 5-agent pipeline:
  1. **Planner** → Decides tasks or chat response
  2. **Resolver** → Provides available entities (splits shopping items!)
  3. **Selection** → LLM chooses specific entities
  4. **Executor** → Executes with deduplication
  5. **Summariser** → Natural language response

## Testing Checklist

### Device Control
```
✅ "Schalte Regallampe und Schranklampe an"
Expected: Both lights turn on
```

### Shopping List (Key Feature!)
```
✅ "Packe Käse und Wein auf die Einkaufsliste"
Expected: TWO separate items: "Käse", "Wein"
```

### Conversational
```
✅ "Guten Morgen"
Expected: Friendly greeting response
```

### Multiple Actions
```
✅ "Schalte Lampe an und packe Milch auf die Liste"
Expected: Light turns on AND Milch added to shopping list
```

## Logs to Watch

Enable debug logging to see the pipeline in action:

```yaml
logger:
  default: info
  logs:
    custom_components.llamacpp_assist: debug
```

Look for:
- `Using MULTI-AGENT conversation pipeline` (on startup)
- `Planner created X task(s)`
- `Resolver processed X task(s)`
- `Selector processed X task(s)`
- `Executor: X successful, Y failed`

## Troubleshooting

### Pipeline Doesn't Activate
- Make sure you saved the configuration
- Check logs for "Using MULTI-AGENT conversation pipeline"
- Try reloading the integration

### Shopping Items Still Combined
- Check logs to verify Resolver is running
- Look for `Resolved shopping_add: 'X und Y' → N item(s)`
- Should show 2+ items, not 1

### Entity Selection Issues
- Selection Agent logs will show which entities were chosen
- Look for `Selected N entities: [...]` in logs

## Performance

Expected improvements:
- **70-80% fewer tokens** vs. classic system
- **Faster responses** (fewer LLM calls)
- **More reliable** entity selection

## Reverting

Simply uncheck the box to go back to the classic system. Both systems work independently.
