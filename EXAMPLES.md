# Example Dialogues for Llama.cpp Assist

This document provides example conversations to test and demonstrate the capabilities of the Llama.cpp Assist integration.

## Basic Device Control

### Lights

**User**: Turn on the kitchen lights  
**Expected**: Calls `light.turn_on` with entity_id `light.kitchen`  
**Response**: "I've turned on the kitchen lights."

**User**: Set the bedroom lights to 50% brightness  
**Expected**: Calls `light.turn_on` with `brightness_pct: 50`  
**Response**: "I've set the bedroom lights to 50% brightness."

**User**: Make the living room lights blue  
**Expected**: Calls `light.turn_on` with color parameters  
**Response**: "I've changed the living room lights to blue."

### Climate

**User**: What's the current temperature?  
**Expected**: Calls `get_state` on temperature sensor  
**Response**: "The current temperature is 21.5°C."

**User**: Set the thermostat to 22 degrees  
**Expected**: Calls `climate.set_temperature`  
**Response**: "I've set the thermostat to 22 degrees."

**User**: Turn on the heater  
**Expected**: Calls `climate.set_hvac_mode` with mode `heat`  
**Response**: "I've turned on the heater."

### Media Players

**User**: Play music in the living room  
**Expected**: Calls `media_player.media_play`  
**Response**: "Playing media in the living room."

**User**: Pause the TV  
**Expected**: Calls `media_player.media_pause`  
**Response**: "I've paused the TV."

**User**: Set volume to 50%  
**Expected**: Calls `media_player.volume_set` with `volume_level: 0.5`  
**Response**: "I've set the volume to 50%."

---

## Memory Operations

### Storing Preferences

**User**: Remember that I prefer the temperature at 21 degrees  
**Expected**: Calls `memory_write('preferences.temperature', '21')`  
**Response**: "I've remembered that you prefer the temperature at 21 degrees."

**User**: My cat's name is Luna  
**Expected**: Calls `memory_write('facts.pet_name', 'Luna')`  
**Response**: "Got it, I'll remember that your cat is named Luna."

### Retrieving Memory

**User**: What temperature do I prefer?  
**Expected**: Calls `memory_read('preferences.temperature')`  
**Response**: "You prefer the temperature at 21 degrees."

**User**: What's my cat's name?  
**Expected**: Calls `memory_read('facts.pet_name')`  
**Response**: "Your cat's name is Luna."

### Context-Aware Behavior

**User**: Remember I like warm lighting in the evening  
**Expected**: Stores preference  

**User**: It's evening, adjust the lights  
**Expected**: Uses memory to set warm color temperature  
**Response**: "I've set the lights to warm, as you prefer in the evening."

---

## Shopping List

### Adding Items

**User**: Add milk to my shopping list  
**Expected**: Calls `shopping_add_item('milk')`  
**Response**: "I've added milk to your shopping list."

**User**: I need to buy eggs, bread, and butter  
**Expected**: Adds three items  
**Response**: "I've added eggs, bread, and butter to your shopping list."

### Viewing Items

**User**: What's on my shopping list?  
**Expected**: Calls `shopping_list_all()`  
**Response**: "Your shopping list has: milk, eggs, bread, and butter."

### Removing Items

**User**: Remove milk from the list  
**Expected**: Calls `shopping_remove_item('milk')`  
**Response**: "I've removed milk from your shopping list."

**User**: I got the eggs  
**Expected**: Interprets as removing eggs  
**Response**: "I've removed eggs from your shopping list."

---

## Calendar Management

### Querying Events

**User**: What's on my calendar today?  
**Expected**: Calls `calendar_list_events(start='today', end='today')`  
**Response**: "You have a team meeting at 10 AM and lunch with Sarah at noon."

**User**: Do I have any appointments this week?  
**Expected**: Lists events for the current week  
**Response**: "This week you have: Monday - dentist at 2 PM, Wednesday - haircut at 4 PM, Friday - dinner reservation at 7 PM."

**User**: What's my next meeting?  
**Expected**: Gets upcoming events and returns the soonest  
**Response**: "Your next meeting is the team standup at 10 AM."

### Creating Events

**User**: Create an event for tomorrow at 3 PM called "Doctor appointment"  
**Expected**: Calls `calendar_create_event` with appropriate parameters  
**Response**: "I've created a calendar event 'Doctor appointment' for tomorrow at 3 PM."

**User**: Remind me about the package delivery on Friday at noon  
**Expected**: Creates calendar event  
**Response**: "I've added a reminder for Friday at noon about the package delivery."

---

## Complex Multi-Step Interactions

### Good Morning Routine

**User**: Good morning  
**Expected**: Multiple tool calls:
1. Get current time
2. Check calendar for today
3. Check weather (if available)
4. Adjust lights based on preferences
**Response**: "Good morning! It's 7:30 AM. You have a team meeting at 10 AM today. I've set the kitchen lights to your preferred morning brightness."

### Evening Routine

**User**: I'm going to bed  
**Expected**: 
1. Turns off all lights except bedroom
2. Sets thermostat to night mode
3. Locks doors (if available)
**Response**: "Goodnight! I've turned off the lights, set the thermostat to 19 degrees, and locked the doors."

### Context Switching

**User**: Turn on the lights  
**Assistant**: "Which room's lights would you like me to turn on?"

**User**: The bedroom  
**Expected**: Calls `light.turn_on` for bedroom  
**Response**: "I've turned on the bedroom lights."

### Planning Assistance

**User**: I'm having a dinner party on Saturday. Help me prepare  
**Expected**:
1. Creates calendar event
2. Asks about shopping list needs
3. Suggests scene settings

**Response**: "I've created a calendar event for Saturday. Would you like me to add ingredients to your shopping list? I can also set the dining room to a warm, ambient lighting scene when your guests arrive."

---

## Error Handling

### Entity Not Found

**User**: Turn on the garage lights  
**Expected**: If entity doesn't exist  
**Response**: "I couldn't find the garage lights. Could you check the entity name?"

### Ambiguous Request

**User**: Turn it on  
**Expected**: Ask for clarification  
**Response**: "What would you like me to turn on?"

### Service Call Failure

**User**: Set the thermostat to 100 degrees  
**Expected**: Service call might fail due to out-of-range value  
**Response**: "I tried to set the thermostat to 100 degrees, but it's outside the allowed range. The thermostat supports temperatures between 10 and 30 degrees."

---

## Testing Checklist

- [ ] Basic light control (on/off, brightness, color)
- [ ] Climate control (temperature, mode)
- [ ] Media player control
- [ ] Memory write and read
- [ ] Shopping list add/remove/list
- [ ] Calendar event listing
- [ ] Calendar event creation
- [ ] Multi-step conversations
- [ ] Context awareness
- [ ] Error handling for missing entities
- [ ] Error handling for ambiguous requests
- [ ] Integration with voice assistants (STT/TTS)
- [ ] Performance (response time < 1.5s with GPU)

---

## Advanced Test Scenarios

### Automation-Like Behavior

**User**: When I say "movie time", dim the living room lights to 20%, close the blinds, and turn on the TV  
**Expected**: Could store this as a preference or directly execute  
**Response**: "I'll remember that. When you say 'movie time', I'll dim the lights to 20%, close the blinds, and turn on the TV."

### Energy Awareness

**User**: Am I using a lot of power right now?  
**Expected**: Queries power sensors  
**Response**: "Your current power usage is 2.3 kW. The main consumers are the electric heater (1.5 kW) and the dishwasher (0.6 kW)."

### Proactive Suggestions

**User**: I'm cold  
**Expected**: Multiple options:
- Increase thermostat
- Check window/door sensors
- Suggest warm clothing
**Response**: "I can turn up the thermostat to 22 degrees. I also notice the bedroom window is open - would you like me to remind you to close it?"
