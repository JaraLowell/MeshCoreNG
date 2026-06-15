# CLI Server - Remote Management Interface

The CLI Server provides TCP-based remote access to MeshCore CLI commands over WiFi, allowing you to manage and monitor your device from any network-connected device without physical access.

## Features

- **Telnet-compatible** text interface
- **Optional password** authentication
- **Single client** connection to prevent conflicts
- **Idle timeout** for security
- **Line-based** command protocol
- Compatible with telnet, netcat, PuTTY, or any TCP client

## Requirements

- ESP32 platform with WiFi support
- WiFi connection configured (`wifi.ssid` and `wifi.password`)
- TCP bridge support enabled (`WITH_TCP_BRIDGE`)

## Configuration

### Enable CLI Server

Configure the CLI server using serial CLI commands:

```bash
# Enable the CLI server
set cli.server.enabled on

# Set the TCP port (default: 2323)
set cli.server.port 2323

# Optional: Set password for authentication
set cli.server.password your_secret_password

# Reboot to apply settings
```

### Query Current Settings

```bash
# Check if CLI server is enabled
get cli.server.enabled

# Check configured port
get cli.server.port

# Check if password is set
get cli.server.password
```

## Usage

### Connect with Telnet

From any computer on the same network:

```bash
# Using telnet
telnet 192.168.1.100 2323

# Using netcat
nc 192.168.1.100 2323

# Using Windows PowerShell
Test-NetConnection -ComputerName 192.168.1.100 -Port 2323
```

### Session Example

```
$ telnet 192.168.1.100 2323
Trying 192.168.1.100...
Connected to 192.168.1.100.
Escape character is '^]'.
MeshCore CLI Server
Type 'help' for commands, 'exit' to disconnect
Password: ********
Authenticated
> ver
v1.15.2 (Build: 2026-06-15)
> stats-core
Uptime: 12h 34m, Free mem: 89456
> get freq
> 915.8
> set name MyRepeater
OK
> exit
Goodbye
Connection closed by foreign host.
```

## Security Features

### Password Authentication

When a password is configured, clients must authenticate before executing commands:

1. Client connects to the server
2. Server prompts for password (characters masked with `*`)
3. Client has 30 seconds to enter the correct password
4. After authentication, full CLI access is granted

If no password is set, all clients are automatically authenticated (not recommended for production).

### Connection Management

- **Single client limit**: Only one client can connect at a time
- **Idle timeout**: Connections are terminated after 5 minutes of inactivity
- **Auth timeout**: Unauthenticated clients are disconnected after 30 seconds

### Network Security Recommendations

1. **Use strong passwords**: Minimum 12 characters with mixed case, numbers, and symbols
2. **Restrict network access**: Use firewall rules to limit which IPs can connect
3. **Use VPN**: Access CLI server through VPN for added security
4. **Monitor connections**: Check logs for unauthorized access attempts
5. **Consider disabling**: Turn off CLI server when not actively needed

## Available Commands

All standard CLI commands are supported. See [terminal_chat_cli.md](terminal_chat_cli.md) for the full command reference.

### Commonly Used Remote Commands

```bash
# System information
ver                    # Firmware version
board                  # Board type
stats-core             # System statistics
stats-radio            # Radio statistics
stats-packets          # Packet statistics

# Configuration
get freq               # Get current frequency
set freq 915.8         # Set frequency
get name               # Get node name
set name MyNode        # Set node name

# Monitoring
neighbors              # List neighbor nodes
regions                # Show regional information
atlas stats            # Atlas statistics (if enabled)

# Control
advert                 # Send advertisement
```

### Built-in CLI Server Commands

```bash
help                   # Show available commands
exit                   # Disconnect from server (alias: quit)
```

## Integration Example

### Python Client

```python
import socket
import time

def cli_command(host, port, password, command):
    """Send a command to MeshCore CLI server and get response"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        sock.settimeout(5.0)
        
        # Read welcome banner
        data = sock.recv(1024).decode('utf-8')
        print(data)
        
        # Send password if required
        if 'Password:' in data:
            sock.sendall(f"{password}\n".encode('utf-8'))
            data = sock.recv(1024).decode('utf-8')
            if 'failed' in data.lower():
                return None
        
        # Send command
        sock.sendall(f"{command}\n".encode('utf-8'))
        time.sleep(0.1)
        
        # Receive response
        response = sock.recv(4096).decode('utf-8')
        return response.strip()
    finally:
        sock.close()

# Example usage
response = cli_command('192.168.1.100', 2323, 'secret', 'ver')
print(f"Firmware: {response}")
```

### Bash Script

```bash
#!/bin/bash

CLI_HOST="192.168.1.100"
CLI_PORT="2323"
CLI_PASSWORD="secret"

# Send command and get response
cli_cmd() {
    local cmd="$1"
    {
        sleep 0.2
        echo "$CLI_PASSWORD"
        sleep 0.2
        echo "$cmd"
        sleep 0.2
        echo "exit"
    } | nc "$CLI_HOST" "$CLI_PORT" | grep -A 1 "^>"
}

# Get firmware version
cli_cmd "ver"

# Get statistics
cli_cmd "stats-core"
```

## Troubleshooting

### Server Not Starting

**Problem**: CLI server doesn't start after enabling.

**Solutions**:
1. Verify WiFi is connected: `get wifi.status`
2. Check server is enabled: `get cli.server.enabled`
3. Verify port is valid (1024-65535): `get cli.server.port`
4. Reboot the device after configuration changes
5. Check serial console for error messages

### Cannot Connect

**Problem**: Client cannot connect to the server.

**Solutions**:
1. Verify device IP address (check router DHCP table or serial output)
2. Ensure client is on the same network
3. Check firewall rules on both client and network
4. Try ping test: `ping 192.168.1.100`
5. Verify port is not blocked: `telnet 192.168.1.100 2323`

### Authentication Failed

**Problem**: Password is rejected.

**Solutions**:
1. Verify password matches exactly (case-sensitive)
2. Check for invisible characters (copy-paste issues)
3. Reset password via serial CLI
4. Temporarily disable password for testing

### Connection Drops

**Problem**: Connection closes unexpectedly.

**Solutions**:
1. Increase idle timeout (requires code modification)
2. Send periodic commands to keep connection alive
3. Check WiFi signal strength and stability
4. Monitor device logs for crashes or reboots

## Performance Considerations

### Memory Usage

The CLI server allocates:
- Command buffer: 256 bytes
- Reply buffer: 512 bytes
- WiFi stack overhead: ~2-4 KB

Total: Approximately 3-5 KB RAM when active.

### Network Bandwidth

- Average command: 20-100 bytes
- Average response: 50-500 bytes
- Keep-alive overhead: minimal (only during active sessions)

Impact on mesh operations is negligible for typical usage.

## Limitations

- **Single client**: Only one connection at a time
- **No encryption**: Commands sent in plaintext (use VPN for secure access)
- **ESP32 only**: Not available on nRF52 or STM32 platforms
- **Requires WiFi**: Must have active WiFi connection
- **Local commands only**: Some commands restricted to serial access only

## Future Enhancements

Possible improvements for future versions:

- Multi-client support with connection queuing
- TLS/SSL encryption for secure communication
- SSH protocol support
- This does not have UPnP so behind a firewall/router, this would not be reachable.
  unless one forwards the port. Both UPnp and Port forwarding would bring a risk
  of DDOS, Bruteforse attacks and other potentional firmware exploids.

```cpp
    // In CLIServer.h
    #ifdef UPNP_SUPPORT
        #include <TinyUPnP.h>
    #endif

    class CLIServer {
        private:
        #ifdef UPNP_SUPPORT
        TinyUPnP* _upnp;
        bool _upnp_port_mapped;
        unsigned long _last_upnp_update;
        
        bool setupUPnP();
        void updateUPnP();
        void releaseUPnP();
        #endif
    };

    // In CLIServer.cpp
    bool CLIServer::begin() {
        // ... existing code ...
        
        #ifdef UPNP_SUPPORT
        if (_prefs->cli_server_upnp_enabled) {
            setupUPnP();
        }
        #endif
        }

        bool CLIServer::setupUPnP() {
        _upnp = new TinyUPnP(20000);  // timeout ms
        _upnp->addPortMappingConfig(
            WiFi.localIP(),
            _prefs->cli_server_port,
            RULE_PROTOCOL_TCP,
            _prefs->cli_server_port,
            "MeshCore CLI"
        );
        
        if (_upnp->commitPortMappings()) {
            _upnp_port_mapped = true;
            return true;
        }
        return false;
    }
```

## See Also

- [terminal_chat_cli.md](terminal_chat_cli.md) - Full CLI command reference
- [companion_protocol.md](companion_protocol.md) - Binary protocol for apps
- [tcp_bridge_server.py](../tools/tcp_bridge_server.py) - Bridge server implementation
