# Narrat Script Syntax Reference

## Core Structure
- **Labels:** `label [label_name]:` (Indentation defines scope)
- **Dialogue:** `talk [character_id] "[text]"`
- **Comments:** Lines starting with `//` are ignored.

## Navigation & Flow
- **Jumps:** `-> [label_name]` (Instantly jumps to another label)
- **Choices:**
  ```narrat
  choice:
      "Option Text":
          -> target_label
      "Another Option":
          talk nero "You chose this."
  ```

## Variables & Logic
- **Set Variable:** `set [var_name] [value]`
- **If Statement:** `if [expression]:`
- **Expressions:** `(== $var 1)`, `(> $var 10)`, `(! $flag)`
- **Data Access:** Variables are usually stored in `$data.property_name`.

## Commands
- **Background:** `background [bg_id]`
- **Scene:** `scene [scene_id]`
- **Play/Stop Sound:** `play [sound_id]`, `stop [sound_id]`
- **Set Character Expression:** `set_expression [character_id] [expression_id]`

## Example Block
```narrat
label start:
    background neon_street
    talk nero "Welcome to the future."
    set has_started true
    choice:
        "Let's go":
            -> explore
        "Wait...":
            talk nero "Take your time."
            -> start
```
