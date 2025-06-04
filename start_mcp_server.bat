@echo off
REM MCP Server Launcher Script

REM Navigate to the correct directory
cd /d "C:\Users\tny2kor\OneDrive - Bosch Group\ETL3_Projects\MiDAS_GIT_VS_Code\custom-mcp-server\mcp-server-claude"

REM Set environment variable
set MCP_CONFIG_PATH=local_api_config.yaml

REM Launch the MCP server
python simple_server.py

REM Pause on error to see what happened
if %ERRORLEVEL% neq 0 (
    echo Error occurred: %ERRORLEVEL%
    pause
)
