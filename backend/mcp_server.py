"""Compatibility entry point for Ioanna's original MCP launch command.

Both commands expose the same spatial and evidence tools:
  python mcp_server.py
  python -m app.mcp_server
"""
from app.mcp_server import mcp

if __name__ == '__main__':
    mcp.run(transport='stdio')
