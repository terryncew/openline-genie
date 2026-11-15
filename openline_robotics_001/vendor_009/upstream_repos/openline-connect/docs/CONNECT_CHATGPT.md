# ChatGPT integration: what is actually supported

The included MCP server uses local stdio and has **not** been connected directly to ChatGPT web. ChatGPT custom MCP connections require remote servers or a supported Secure MCP Tunnel. As of October 2026, full custom MCP apps are available in Business/Enterprise/Edu web workspaces subject to admin/owner controls; individual Pro custom MCP permissions are limited to read/fetch. Other product surfaces and approvals vary. See https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt .

For local development, a compatible MCP client can launch `openline-connect serve --home /absolute/path/to/.openline` over stdio after installing the official `mcp` SDK, and can discover the six tools. Do not advertise this as a published ChatGPT plugin or directory listing.
