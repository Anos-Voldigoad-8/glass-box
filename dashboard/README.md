# GLASS BOX Dashboard

Cyberpunk/terminal-themed observability dashboard for GLASS BOX.

## Features

- Terminal-inspired UI with dark background and neon accents
- Real-time trace updates via WebSocket
- Session list with filtering capabilities
- Trace visualization with collapsible tree view
- Live metrics panel (token usage, cost, latency)
- Replay mode for stepping through traces
- Diff mode for comparing two traces

## Technology Stack

- Vanilla JavaScript (no frameworks)
- WebSocket for real-time communication
- CSS3 for cyberpunk terminal aesthetic
- Vanilla JS for DOM manipulation and state management

## Setup

1. Ensure the GLASS BOX backend is running on http://localhost:8000
2. Open dashboard/index.html in a browser
3. The dashboard will automatically connect to the backend via WebSocket

## Development

To customize the dashboard:
- Edit `dashboard/index.html` for structure
- Edit `dashboard/style.css` for styling
- Edit `dashboard/script.js` for functionality

The dashboard is designed to be lightweight and dependency-free for easy deployment.