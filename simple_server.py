#!/usr/bin/env python3
"""
Simplified MCP Server for API integration
Compatible with current MCP library versions
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
import aiohttp
import yaml
from pydantic import BaseModel, Field

# MCP imports - simplified approach
try:
    from mcp.server.models import InitializationOptions
    from mcp.server import NotificationOptions, Server
    from mcp.types import (
        CallToolRequest,
        CallToolResult,
        ListToolsRequest,
        Tool,
        TextContent,
    )
    from mcp.server.stdio import stdio_server
except ImportError as e:
    print(f"MCP library import error: {e}")
    print("Please install MCP: pip install mcp")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simple-mcp-server")


class APIEndpoint(BaseModel):
    """Configuration for an API endpoint"""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    method: str = Field(default="GET", description="HTTP method")
    url: str = Field(..., description="API endpoint URL")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    path_params: List[str] = Field(default_factory=list, description="URL path parameters")
    query_params: List[str] = Field(default_factory=list, description="Query parameters")
    body_template: Optional[str] = Field(None, description="Request body template")
    auth_type: Optional[str] = Field(None, description="Authentication type")
    auth_config: Dict[str, str] = Field(default_factory=dict, description="Auth configuration")


class ServerConfig(BaseModel):
    """Server configuration"""
    name: str = Field(default="Simple API MCP Server", description="Server name")
    version: str = Field(default="1.0.0", description="Server version")
    base_url: Optional[str] = Field(None, description="Base URL for relative endpoints")
    global_headers: Dict[str, str] = Field(default_factory=dict, description="Global headers")
    endpoints: List[APIEndpoint] = Field(..., description="API endpoints configuration")


class SimpleAPIServer:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config: Optional[ServerConfig] = None
        self.session: Optional[aiohttp.ClientSession] = None

        # Create MCP server
        self.app = Server("simple-api-mcp-server")

        # Register handlers
        @self.app.list_tools()
        async def handle_list_tools() -> List[Tool]:
            return await self._handle_list_tools()

        @self.app.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> List[TextContent]:
            return await self._handle_call_tool(name, arguments)

    async def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_path, 'r') as f:
                if self.config_path.endswith('.yaml') or self.config_path.endswith('.yml'):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)

            self.config = ServerConfig(**data)
            logger.info(f"Loaded configuration with {len(self.config.endpoints)} endpoints")

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    async def setup_session(self):
        """Setup HTTP session"""
        self.session = aiohttp.ClientSession()

    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()

    def _build_tool_schema(self, endpoint: APIEndpoint) -> Tool:
        """Build tool schema from endpoint configuration"""
        properties = {}
        required = []

        # Add path parameters
        for param in endpoint.path_params:
            properties[param] = {
                "type": "string",
                "description": f"Path parameter: {param}"
            }
            required.append(param)

        # Add query parameters
        for param in endpoint.query_params:
            param_config = endpoint.parameters.get(param, {})
            properties[param] = {
                "type": param_config.get("type", "string"),
                "description": param_config.get("description", f"Query parameter: {param}")
            }
            if param_config.get("required", False):
                required.append(param)

        # Add any additional parameters from config
        for param_name, param_config in endpoint.parameters.items():
            if param_name not in properties:
                properties[param_name] = param_config
                if param_config.get("required", False):
                    required.append(param_name)

        return Tool(
            name=endpoint.name,
            description=endpoint.description,
            inputSchema={
                "type": "object",
                "properties": properties,
                "required": required
            }
        )

    async def _handle_list_tools(self) -> List[Tool]:
        """Handle list tools request"""
        if not self.config:
            return []

        tools = []
        for endpoint in self.config.endpoints:
            tool = self._build_tool_schema(endpoint)
            tools.append(tool)

        logger.info(f"Listed {len(tools)} tools")
        return tools

    def _prepare_auth_headers(self, endpoint: APIEndpoint) -> Dict[str, str]:
        """Prepare authentication headers"""
        headers = {}

        if endpoint.auth_type == "bearer":
            token = endpoint.auth_config.get("token") or os.getenv("API_TOKEN")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        elif endpoint.auth_type == "basic":
            username = endpoint.auth_config.get("username") or os.getenv("API_USERNAME")
            password = endpoint.auth_config.get("password") or os.getenv("API_PASSWORD")
            if username and password:
                import base64
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {credentials}"

        elif endpoint.auth_type == "api_key":
            api_key = endpoint.auth_config.get("key") or os.getenv("API_KEY")
            header_name = endpoint.auth_config.get("header", "X-API-Key")
            if api_key:
                headers[header_name] = api_key

        return headers

    def _build_url(self, endpoint: APIEndpoint, arguments: Dict[str, Any]) -> str:
        """Build URL with path parameters"""
        url = endpoint.url

        # Handle base URL
        if self.config.base_url and not url.startswith(('http://', 'https://')):
            url = urljoin(self.config.base_url, url)

        # Replace path parameters
        for param in endpoint.path_params:
            if param in arguments:
                url = url.replace(f"{{{param}}}", str(arguments[param]))

        return url

    def _build_query_params(self, endpoint: APIEndpoint, arguments: Dict[str, Any]) -> Dict[str, str]:
        """Build query parameters"""
        params = {}
        for param in endpoint.query_params:
            if param in arguments:
                params[param] = str(arguments[param])
        return params

    def _build_request_body(self, endpoint: APIEndpoint, arguments: Dict[str, Any]) -> Optional[str]:
        """Build request body from template and arguments"""
        if not endpoint.body_template:
            return None

        try:
            body = endpoint.body_template
            for key, value in arguments.items():
                body = body.replace(f"{{{key}}}", str(value))
            return body
        except Exception as e:
            logger.error(f"Failed to build request body: {e}")
            return None

    async def _handle_call_tool(self, name: str, arguments: dict) -> List[TextContent]:
        """Handle tool call request"""
        try:
            # Find the endpoint configuration
            endpoint = None
            for ep in self.config.endpoints:
                if ep.name == name:
                    endpoint = ep
                    break

            if not endpoint:
                return [TextContent(type="text", text=f"Tool '{name}' not found")]

            # Prepare request
            url = self._build_url(endpoint, arguments or {})
            headers = {**self.config.global_headers, **endpoint.headers}
            headers.update(self._prepare_auth_headers(endpoint))

            query_params = self._build_query_params(endpoint, arguments or {})
            request_body = self._build_request_body(endpoint, arguments or {})

            # Make HTTP request
            async with self.session.request(
                    method=endpoint.method,
                    url=url,
                    headers=headers,
                    params=query_params,
                    data=request_body
            ) as response:
                response_text = await response.text()

                # Try to parse as JSON for better formatting
                try:
                    response_data = json.loads(response_text)
                    formatted_response = json.dumps(response_data, indent=2)
                except json.JSONDecodeError:
                    formatted_response = response_text

                if response.status >= 400:
                    error_msg = f"HTTP {response.status}: {formatted_response}"
                    logger.error(f"API call failed: {error_msg}")
                    return [TextContent(type="text", text=f"Error: {error_msg}")]

                logger.info(f"Successfully called {endpoint.name}")
                return [TextContent(
                    type="text",
                    text=f"API Response (Status: {response.status}):\n\n{formatted_response}"
                )]

        except Exception as e:
            error_msg = f"Failed to call tool '{name}': {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=f"Error: {error_msg}")]


async def main():
    """Main entry point"""
    config_path = os.getenv("MCP_CONFIG_PATH", "local_api_config.yaml")

    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    server = SimpleAPIServer(config_path)

    try:
        await server.load_config()
        await server.setup_session()

        # Run the server
        logger.info("Starting Simple MCP API Server...")
        logger.info(f"Using configuration: {config_path}")
        logger.info(f"Loaded {len(server.config.endpoints)} endpoints")

        async with stdio_server() as (read_stream, write_stream):
            await server.app.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name=server.config.name,
                    server_version=server.config.version,
                    capabilities=server.app.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )

    except Exception as e:
        logger.error(f"Server error: {e}")
        raise

    finally:
        await server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
