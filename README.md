# Monkey Patching LangChain

A live demo showing how to monkey patch LangChain runnables to either observe their execution (autologging) or intercept and modify their behavior.

### Core Files

*   **`main.py`**: Runs the FastAPI server to serve the API and the pre-built React UI.
*   **`patcher.py`**: Contains the `Patcher` class which implements the core monkey patching logic.
*   **`demo.py`**: A simple script to demonstrate the patcher's two different modes.
*   **`chain_builder.py`**: A helper that defines the simple LangChain pipeline used in the demo.

### Setup

1.  Create and activate the virtual environment:
    ```
    uv venv
    source .venv/bin/activate
    # On Windows: .\.venv\Scripts\activate
    ```

2.  Install dependencies:
    ```
    uv sync
    ```

### Running the Demo

You need two terminals.

1.  **Start the Server** (Terminal 1):
    ```
    uvicorn main:app --port 8000
    ```

2.  **Run the Demo Script** (Terminal 2):
    
    Open `demo.py`, select a mode by uncommenting one of the `patcher.autolog()` lines, and then run:
    ```
    python demo.py
    ```

The "production" mode sends logs to the UI at `http://127.0.0.1:8000`, while "simple" mode intercepts the call and prints a different result to the console.