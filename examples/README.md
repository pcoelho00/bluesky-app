# Examples

This folder contains example scripts and workflows for the Bluesky Feed Summarizer.

## Files

### `example_workflow.py`

Demonstrates how to integrate the streaming service with periodic summarization for a complete monitoring workflow.

**Usage:**
```bash
# Run from the project root directory
cd /home/pedrocoelho/bluesky-app
python examples/example_workflow.py
```

**What it shows:**
- Starting the streaming service with filters
- Generating summaries from accumulated data
- Checking system status
- Viewing recent posts
- Best practices for workflow integration

## Running Examples

All examples should be run from the project root directory:

```bash
cd /home/pedrocoelho/bluesky-app
python examples/example_workflow.py
```

This ensures the Python module paths are correct and the examples can find the bluesky_summarizer package.
