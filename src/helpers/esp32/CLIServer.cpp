#include "CLIServer.h"
#include "../CommonCLI.h"
#include <Arduino.h>

#define CLI_DEBUG 0

#if CLI_DEBUG
  #define CLI_LOG(...) Serial.printf("CLIServer: " __VA_ARGS__)
#else
  #define CLI_LOG(...) {}
#endif

CLIServer::CLIServer(NodePrefs* prefs, CommonCLI* cli)
    : _prefs(prefs), _cli(cli), _server(nullptr), 
      _running(false), _client_connected(false), _client_authenticated(false),
      _client_connect_time(0), _last_activity_time(0), _command_count(0),
      _command_pos(0) {
  memset(_command_buffer, 0, sizeof(_command_buffer));
  memset(_reply_buffer, 0, sizeof(_reply_buffer));
}

CLIServer::~CLIServer() {
  end();
}

bool CLIServer::begin() {
  if (_running) {
    CLI_LOG("Already running\n");
    return true;
  }

  if (!_prefs->cli_server_enabled) {
    CLI_LOG("CLI server disabled in preferences\n");
    return false;
  }

  if (WiFi.status() != WL_CONNECTED) {
    CLI_LOG("WiFi not connected\n");
    return false;
  }

  uint16_t port = _prefs->cli_server_port;
  if (port == 0) {
    port = 2323;  // default telnet alternative port
  }

  _server = new WiFiServer(port);
  if (!_server) {
    CLI_LOG("Failed to allocate server\n");
    return false;
  }

  _server->begin();
  _server->setNoDelay(true);  // disable Nagle algorithm for responsiveness
  
  _running = true;
  _client_connected = false;
  _client_authenticated = false;
  _command_count = 0;
  resetCommandBuffer();

  CLI_LOG("Started on port %d\n", port);
  return true;
}

void CLIServer::end() {
  if (!_running) {
    return;
  }

  disconnectClient("Server stopping");
  
  if (_server) {
    _server->stop();
    delete _server;
    _server = nullptr;
  }

  _running = false;
  CLI_LOG("Stopped\n");
}

void CLIServer::loop() {
  if (!_running || !_server) {
    return;
  }

  // Check for new connection
  if (!_client_connected) {
    WiFiClient newClient = _server->available();
    if (newClient) {
      handleNewConnection();
    }
  }

  // Handle existing client
  if (_client_connected) {
    if (!_client.connected()) {
      disconnectClient("Client disconnected");
      return;
    }

    if (checkTimeout()) {
      return;  // client was disconnected
    }

    if (_client.available()) {
      handleClientData();
    }
  }
}

void CLIServer::handleNewConnection() {
  WiFiClient newClient = _server->available();
  if (!newClient) {
    return;
  }

  // Disconnect any existing client
  if (_client_connected) {
    disconnectClient("New connection");
  }

  _client = newClient;
  _client_connected = true;
  _client_authenticated = !requiresAuth();  // if no password, auto-authenticate
  _client_connect_time = millis();
  _last_activity_time = millis();
  resetCommandBuffer();

  CLI_LOG("Client connected from %s\n", _client.remoteIP().toString().c_str());

  // Send welcome banner
  sendReply("MeshCore CLI Server\r\n");
  sendReply("Type 'help' for commands, 'exit' to disconnect\r\n");

  if (requiresAuth()) {
    sendReply("Password: ");
  } else {
    sendPrompt();
  }
}

void CLIServer::handleClientData() {
  while (_client.available()) {
    char c = _client.read();
    _last_activity_time = millis();

    // Handle backspace/delete
    if (c == '\b' || c == 0x7F) {
      if (_command_pos > 0) {
        _command_pos--;
        _command_buffer[_command_pos] = '\0';
        // Echo backspace (BS + Space + BS to erase character)
        _client.write("\b \b", 3);
      }
      continue;
    }

    // Handle line ending (CR or LF)
    if (c == '\r' || c == '\n') {
      // Skip empty lines
      if (_command_pos == 0) {
        continue;
      }

      _client.write("\r\n", 2);  // Echo newline

      // Null-terminate command
      _command_buffer[_command_pos] = '\0';

      // Process authentication if required
      if (!_client_authenticated) {
        if (strcmp(_command_buffer, _prefs->cli_server_password) == 0) {
          _client_authenticated = true;
          sendReply("Authenticated\r\n");
          sendPrompt();
        } else {
          sendReply("Authentication failed\r\n");
          disconnectClient("Auth failed");
          return;
        }
        resetCommandBuffer();
        continue;
      }

      // Process command
      processCommand(_command_buffer);
      resetCommandBuffer();
      continue;
    }

    // Handle printable characters
    if (c >= 32 && c <= 126) {
      if (_command_pos < CLI_MAX_COMMAND_LEN - 1) {
        _command_buffer[_command_pos++] = c;
        
        // Echo character (unless entering password)
        if (!requiresAuth() || _client_authenticated) {
          _client.write(c);
        } else {
          _client.write('*');  // mask password
        }
      }
    }
  }
}

void CLIServer::processCommand(const char* cmd) {
  if (!cmd || !_client_authenticated) {
    return;
  }

  CLI_LOG("Command: %s\n", cmd);

  // Handle built-in commands
  if (strcmp(cmd, "exit") == 0 || strcmp(cmd, "quit") == 0) {
    sendReply("Goodbye\r\n");
    disconnectClient("User exit");
    return;
  }

  if (strcmp(cmd, "help") == 0) {
    sendReply("Available commands:\r\n");
    sendReply("  ver, stats-core, stats-radio, stats-packets\r\n");
    sendReply("  get <setting>, set <setting> <value>\r\n");
    sendReply("  atlas, neighbors, regions\r\n");
    sendReply("  exit - disconnect from server\r\n");
    sendReply("See docs/terminal_chat_cli.md for full command list\r\n");
    sendPrompt();
    return;
  }

  // Pass command to CommonCLI for processing
  // sender_timestamp = 0 means local/serial command (allows all commands)
  memset(_reply_buffer, 0, sizeof(_reply_buffer));
  _cli->handleCommand(0, const_cast<char*>(cmd), _reply_buffer);
  _command_count++;

  // Send reply to client
  if (strlen(_reply_buffer) > 0) {
    sendReply(_reply_buffer);
    sendReply("\r\n");
  }

  sendPrompt();
}

void CLIServer::sendReply(const char* text) {
  if (!_client_connected || !text) {
    return;
  }

  _client.print(text);
}

void CLIServer::sendPrompt() {
  if (!_client_connected || !_client_authenticated) {
    return;
  }

  sendReply("> ");
}

void CLIServer::disconnectClient(const char* reason) {
  if (!_client_connected) {
    return;
  }

  CLI_LOG("Disconnecting client: %s\n", reason ? reason : "unknown");

  _client.stop();
  _client_connected = false;
  _client_authenticated = false;
  resetCommandBuffer();
}

bool CLIServer::checkTimeout() {
  if (!_client_connected) {
    return false;
  }

  uint32_t now = millis();

  // Check authentication timeout
  if (!_client_authenticated && requiresAuth()) {
    if (now - _client_connect_time > CLI_AUTH_TIMEOUT_MS) {
      sendReply("\r\nAuthentication timeout\r\n");
      disconnectClient("Auth timeout");
      return true;
    }
  }

  // Check idle timeout
  if (now - _last_activity_time > CLI_IDLE_TIMEOUT_MS) {
    sendReply("\r\nIdle timeout\r\n");
    disconnectClient("Idle timeout");
    return true;
  }

  return false;
}

void CLIServer::resetCommandBuffer() {
  _command_pos = 0;
  memset(_command_buffer, 0, sizeof(_command_buffer));
}

bool CLIServer::requiresAuth() const {
  return _prefs->cli_server_password[0] != '\0';
}
