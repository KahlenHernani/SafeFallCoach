#!/usr/bin/env python3
"""
SafeFall Active Learning Wizard — Launcher

Starts the FastAPI server on port 8000. The Flutter desktop app connects
to this server for camera feed, session management, and real-time state.
"""

import uvicorn


def main():
    uvicorn.run(
        "active_learning_engine.server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
