import paramiko
import time
import socket
from typing import Tuple, Optional, Dict, Any
from config.settings import SSH_HOST, SSH_PORT, SSH_USERNAME, SSH_PASSWORD, SSH_KEY_PATH, SSH_OPTIONS

class SSHClient:
    """SSH client for connecting to and executing commands on remote systems"""
    
    def __init__(self, host=SSH_HOST, port=SSH_PORT, username=SSH_USERNAME, 
                 password=SSH_PASSWORD, key_path=SSH_KEY_PATH, options=SSH_OPTIONS):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_path = key_path
        self.options = options or ""
        self.client = None
        self.shell = None
        
    def _parse_ssh_options(self) -> Dict[str, Any]:
        """
        Parse SSH options string into paramiko configuration dictionary
        
        Returns:
            Dictionary of SSH options for paramiko
        """
        ssh_config = {}
        
        if not self.options:
            return ssh_config
            
        options = self.options.strip().split()
        for option in options:
            if option.startswith("-o"):
                # Remove the -o prefix
                option = option[2:]
                if "=" in option:
                    key, value = option.split("=", 1)
                    
                    # Handle HostKeyAlgorithms option
                    if key == "HostKeyAlgorithms":
                        if value.startswith("+"):
                            # Add algorithms to the default list
                            value = value[1:]  # Remove the + sign
                            ssh_config["disabled_algorithms"] = {"pubkeys": []}
                            
                            # For ssh-rsa specifically
                            if "ssh-rsa" in value:
                                ssh_config["allow_agent"] = False
                                # Tell paramiko to accept ssh-rsa keys
                                transport = paramiko.Transport((self.host, self.port))
                                transport.get_security_options().key_types = ['ssh-rsa'] + list(transport.get_security_options().key_types)
                                
        return ssh_config
        
    def connect(self) -> bool:
        """
        Establish an SSH connection and create an interactive shell
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Parse any custom SSH options
            ssh_config = self._parse_ssh_options()
            
            connect_kwargs = {
                'hostname': self.host,
                'port': self.port,
                'username': self.username,
                'timeout': 10
            }
            
            # Add any custom SSH options
            for key, value in ssh_config.items():
                connect_kwargs[key] = value
            
            if self.key_path:
                # Use key-based authentication if a key path is provided
                connect_kwargs['key_filename'] = self.key_path
            else:
                # Use password authentication
                connect_kwargs['password'] = self.password
            
            # Handle ssh-rsa specifically
            if self.options and "HostKeyAlgorithms=+ssh-rsa" in self.options:
                # Configure paramiko to accept ssh-rsa keys
                paramiko.Transport._preferred_pubkeys = ['ssh-rsa'] + [
                    k for k in paramiko.Transport._preferred_pubkeys if k != 'ssh-rsa'
                ]
                
            self.client.connect(**connect_kwargs)
            
            # Create interactive shell session
            self.shell = self.client.invoke_shell()
            
            # Wait for shell to initialize
            time.sleep(1)
            
            # Clear initial output
            if self.shell.recv_ready():
                self.shell.recv(4096).decode('utf-8', errors='ignore')
                
            return True
        
        except (paramiko.AuthenticationException, paramiko.SSHException, 
                socket.error, Exception) as e:
            print(f"SSH connection error: {str(e)}")
            return False
    
    def execute_command(self, command: str, timeout: int = 30) -> Tuple[str, Optional[str]]:
        """
        Execute a command on the remote system
        
        Args:
            command: The command to execute
            timeout: Maximum time to wait for output (seconds)
            
        Returns:
            Tuple containing (output, error_message)
        """
        if not self.shell:
            return "", "No active shell connection"
        
        try:
            # Send command to the shell
            self.shell.send(command + "\n")
            
            # Wait for output
            output = ""
            start_time = time.time()
            
            while (time.time() - start_time) < timeout:
                if self.shell.recv_ready():
                    chunk = self.shell.recv(4096).decode('utf-8', errors='ignore')
                    output += chunk
                    
                    # If we see a shell prompt, we're likely done
                    if "$" in chunk or "#" in chunk or ">" in chunk:
                        if not self.shell.recv_ready():
                            break
                
                time.sleep(0.1)
            
            return output, None
                
        except Exception as e:
            return "", f"Command execution error: {str(e)}"
    
    def close(self):
        """Close the SSH connection"""
        if self.shell:
            self.shell.close()
        if self.client:
            self.client.close()