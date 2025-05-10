import paramiko
import time
import socket
import logging
from typing import Tuple, Optional, Dict, Any
from config.settings import SSH_HOST, SSH_PORT, SSH_USERNAME, SSH_PASSWORD, SSH_KEY_PATH, SSH_OPTIONS

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='ssh_client.log',
                    filemode='a')
logger = logging.getLogger('SSHClient')

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
        
        # Log initialization with connection details
        logger.info(f"Initializing SSH client for {username}@{host}:{port}")
        logger.info(f"Using SSH options: {self.options}")
        
    def _parse_ssh_options(self) -> Dict[str, Any]:
        """
        Parse SSH options string into paramiko configuration dictionary
        
        Returns:
            Dictionary of SSH options for paramiko
        """
        ssh_config = {}
        
        if not self.options:
            return ssh_config
        
        logger.debug(f"Parsing SSH options: {self.options}")
            
        options = self.options.strip().split()
        for option in options:
            if option.startswith("-o"):
                # Remove the -o prefix
                option = option[2:]
                if "=" in option:
                    key, value = option.split("=", 1)
                    logger.debug(f"Processing SSH option: {key}={value}")
                    
                    # Handle HostKeyAlgorithms option
                    if key == "HostKeyAlgorithms":
                        if value.startswith("+"):
                            # Add algorithms to the default list
                            value = value[1:]  # Remove the + sign
                            logger.info(f"Adding key algorithms: {value}")
                            ssh_config["disabled_algorithms"] = {"pubkeys": []}
                            
                            # For ssh-rsa specifically
                            if "ssh-rsa" in value:
                                logger.info("Enabling ssh-rsa support")
                                ssh_config["allow_agent"] = False
                                # Tell paramiko to accept ssh-rsa keys
                                transport = paramiko.Transport((self.host, self.port))
                                transport.get_security_options().key_types = ['ssh-rsa'] + list(transport.get_security_options().key_types)
                                
        logger.debug(f"Parsed SSH config: {ssh_config}")
        return ssh_config
        
    def connect(self) -> bool:
        """
        Establish an SSH connection and create an interactive shell
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        logger.info(f"Attempting to connect to {self.host}:{self.port} as {self.username}")
        
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            logger.debug("Created SSH client with AutoAddPolicy for host keys")
            
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
                logger.info(f"Using key-based authentication with key: {self.key_path}")
                connect_kwargs['key_filename'] = self.key_path
            else:
                # Use password authentication
                logger.info("Using password authentication")
                connect_kwargs['password'] = self.password
            
            # Handle ssh-rsa specifically
            if self.options and "HostKeyAlgorithms=+ssh-rsa" in self.options:
                # Configure paramiko to accept ssh-rsa keys
                logger.info("Configuring paramiko to prioritize ssh-rsa keys")
                paramiko.Transport._preferred_pubkeys = ['ssh-rsa'] + [
                    k for k in paramiko.Transport._preferred_pubkeys if k != 'ssh-rsa'
                ]
            
            logger.debug(f"Connection parameters: {connect_kwargs}")
            self.client.connect(**connect_kwargs)
            logger.info(f"Successfully connected to {self.host}")
            
            # Create interactive shell session
            logger.debug("Invoking shell")
            self.shell = self.client.invoke_shell()
            
            # Wait for shell to initialize
            time.sleep(1)
            
            # Clear initial output
            if self.shell.recv_ready():
                initial_output = self.shell.recv(4096).decode('utf-8', errors='ignore')
                logger.debug(f"Initial shell output: {initial_output}")
                
            logger.info("SSH shell session established successfully")
            return True
        
        except (paramiko.AuthenticationException, paramiko.SSHException, 
                socket.error, Exception) as e:
            logger.error(f"SSH connection error: {str(e)}")
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
            logger.error("No active shell connection")
            return "", "No active shell connection"
        
        try:
            # Log the command being executed
            logger.info(f"Executing command: {command}")
            
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
            
            # Log a truncated version of the output (to avoid huge log files)
            log_output = output[:500] + "..." if len(output) > 500 else output
            logger.debug(f"Command output: {log_output}")
            
            elapsed_time = time.time() - start_time
            logger.info(f"Command completed in {elapsed_time:.2f} seconds")
            
            return output, None
                
        except Exception as e:
            error_msg = f"Command execution error: {str(e)}"
            logger.error(error_msg)
            return "", error_msg
    
    def close(self):
        """Close the SSH connection"""
        logger.info("Closing SSH connection")
        if self.shell:
            self.shell.close()
        if self.client:
            self.client.close()
        logger.info("SSH connection closed")