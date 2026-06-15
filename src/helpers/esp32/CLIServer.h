#pragma once

#include <WiFi.h>

#ifndef CLI_MAX_COMMAND_LEN
#define CLI_MAX_COMMAND_LEN 256
#endif

#ifndef CLI_MAX_REPLY_LEN
#define CLI_MAX_REPLY_LEN 512
#endif

#ifndef CLI_IDLE_TIMEOUT_MS
#define CLI_IDLE_TIMEOUT_MS 300000  // 5 minutes
#endif

#ifndef CLI_AUTH_TIMEOUT_MS
#define CLI_AUTH_TIMEOUT_MS 30000  // 30 seconds
#endif

class CommonCLI;
struct NodePrefs;

/**
 * @brief TCP-based CLI server for remote management
 * 
 * Provides telnet-like access to CLI commands over TCP/IP.
 * Features:
 * - Optional password authentication
 * - Single client connection
 * - Idle timeout
 * - Line-based text protocol
 * - Compatible with telnet, netcat, or any TCP client
 */
class CLIServer {
public:
  CLIServer(NodePrefs* prefs, CommonCLI* cli);
  ~CLIServer();

  /**
   * @brief Initialize and start the CLI server
   * @return true if server started successfully
   */
  bool begin();

  /**
   * @brief Stop the CLI server and close connections
   */
  void end();

  /**
   * @brief Process incoming connections and commands (call from main loop)
   */
  void loop();

  /**
   * @brief Check if server is currently running
   */
  bool isRunning() const { return _running; }

  /**
   * @brief Check if a client is currently connected
   */
  bool isClientConnected() const { return _client_connected; }

  /**
   * @brief Get number of commands processed since start
   */
  uint32_t getCommandCount() const { return _command_count; }

private:
  NodePrefs* _prefs;
  CommonCLI* _cli;
  WiFiServer* _server;
  WiFiClient _client;
  
  bool _running;
  bool _client_connected;
  bool _client_authenticated;
  uint32_t _client_connect_time;
  uint32_t _last_activity_time;
  uint32_t _command_count;
  
  char _command_buffer[CLI_MAX_COMMAND_LEN];
  size_t _command_pos;
  
  char _reply_buffer[CLI_MAX_REPLY_LEN];

  void handleNewConnection();
  void handleClientData();
  void processCommand(const char* cmd);
  void sendReply(const char* text);
  void sendPrompt();
  void disconnectClient(const char* reason = nullptr);
  bool checkTimeout();
  void resetCommandBuffer();
  bool requiresAuth() const;
};
