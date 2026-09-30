# Acro TD Macros

[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://acronym-lol.github.io/acro-td-macros/)

A system for controlling TouchDesigner components via Macros.

**Documentation:** https://acronym-lol.github.io/acro-td-macros/

## Features

- Hierarchical macro storage with folder-based organization on disk
- Signal/subscription routing system for inter-macro communication
- Per-macro callback DATs with Jinja2 templated stubs
- Logging and error tracking per macro and globally
- Copy/cut/paste and move/reorder operations
- Safety mode for confirmation prompts on destructive actions

## Usage

```python
# Get the main extension via the global shortcut
op.AM.CreateMacro('MyMacro', '/')

# Trigger a macro
op.AM.TriggerMacro('MyMacro', args={'foo': 'bar'})

# Emit a signal to all subscribed macros
op.AM.Emit('mySignal', args={'value': 42})
```

## Installation

This module is typically installed as a git subtree in the acro-td-core template.

```bash
git subtree add --prefix=modules/acro-td-macros https://github.com/acronym-lol/acro-td-macros.git main --squash
```
