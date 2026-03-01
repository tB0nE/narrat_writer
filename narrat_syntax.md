# Narrat Script Syntax Reference

## Core Structure
- **Labels:** `[label_name]:` (Indentation defines scope)
- **Dialogue:** `talk [character_id] [pose_id] "[text]"`
- **Comments:** Lines starting with `//` are ignored.

## Navigation & Flow
- **Jumps:** `jump [label_name]` (Instantly jumps to another label)
- **Choices:**
  ```narrat
  choice:
      "Option Text":
          jump target_label
      "Another Option":
          jump another_label
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
main:
    background neon_street
    talk nero idle "Welcome to the future."
    set has_started true
    choice:
        "Let's go":
            jump explore
        "Wait...":
            jump wait_a_bit

wait_a_bit:
    talk nero idle "Take your time."
    jump main
```
