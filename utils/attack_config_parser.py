"""
Attack Configuration Parser

This module handles loading and parsing attack configurations from JSON files.
It validates the configuration structure and prepares it for use by the attack workflow.
"""

import os
import json
from typing import Dict, List, Any, Optional, Union


class AttackConfigParser:
    """Parser for attack configuration files in JSON format"""
    
    def __init__(self):
        self.config = {}
        
    def load_from_file(self, file_path: str) -> Dict[str, Any]:
        """
        Load attack configuration from a JSON file
        
        Args:
            file_path: Path to the JSON configuration file
            
        Returns:
            Dictionary containing the parsed attack configuration
            
        Raises:
            FileNotFoundError: If the specified file does not exist
            json.JSONDecodeError: If the file contains invalid JSON
            ValueError: If the configuration structure is invalid
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Attack configuration file not found: {file_path}")
            
        try:
            with open(file_path, 'r') as f:
                self.config = json.load(f)
                
            # Validate the configuration structure
            self._validate_config()
            
            return self.config
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in configuration file: {str(e)}", e.doc, e.pos)
    
    def _validate_config(self) -> None:
        """
        Validate the structure of the loaded configuration
        
        Raises:
            ValueError: If the configuration structure is invalid
        """
        # Check for required top-level keys
        required_keys = ["target", "tasks"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required key in configuration: {key}")
        
        # Validate target information
        target = self.config["target"]
        if not isinstance(target, dict):
            raise ValueError("Target must be a dictionary")
            
        required_target_keys = ["host"]
        for key in required_target_keys:
            if key not in target:
                raise ValueError(f"Missing required key in target configuration: {key}")
        
        # Validate tasks
        tasks = self.config["tasks"]
        if not isinstance(tasks, list) or len(tasks) == 0:
            raise ValueError("Tasks must be a non-empty list")
            
        # Validate each task
        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                raise ValueError(f"Task at index {i} must be a dictionary")
                
            required_task_keys = ["id", "name", "goal"]
            for key in required_task_keys:
                if key not in task:
                    raise ValueError(f"Missing required key '{key}' in task at index {i}")
    
    def get_target_info(self) -> Dict[str, Any]:
        """
        Get the target system information
        
        Returns:
            Dictionary containing target system details
        """
        return self.config.get("target", {})
    
    def get_global_settings(self) -> Dict[str, Any]:
        """
        Get global settings for the attack
        
        Returns:
            Dictionary containing global settings
        """
        return self.config.get("global_settings", {})
    
    def get_tasks(self) -> List[Dict[str, Any]]:
        """
        Get the list of attack tasks
        
        Returns:
            List of task dictionaries
        """
        return self.config.get("tasks", [])
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific task by its ID
        
        Args:
            task_id: The ID of the task to retrieve
            
        Returns:
            Task dictionary or None if not found
        """
        tasks = self.get_tasks()
        for task in tasks:
            if task.get("id") == task_id:
                return task
        return None
    
    def get_task_dependencies(self, task_id: str) -> List[str]:
        """
        Get the IDs of tasks that a specific task depends on
        
        Args:
            task_id: The ID of the task
            
        Returns:
            List of task IDs that this task depends on
        """
        task = self.get_task_by_id(task_id)
        if not task:
            return []
            
        return task.get("requires", [])
    
    def resolve_task_order(self) -> List[str]:
        """
        Resolve the order in which tasks should be executed based on dependencies
        
        Returns:
            List of task IDs in the order they should be executed
        """
        tasks = self.get_tasks()
        task_ids = [task["id"] for task in tasks]
        ordered_tasks = []
        visited = set()
        temp_visited = set()
        
        def visit(task_id):
            if task_id in temp_visited:
                raise ValueError(f"Circular dependency detected involving task {task_id}")
            
            if task_id in visited:
                return
                
            temp_visited.add(task_id)
            
            # Visit dependencies first
            deps = self.get_task_dependencies(task_id)
            for dep_id in deps:
                if dep_id not in task_ids:
                    raise ValueError(f"Task {task_id} depends on non-existent task {dep_id}")
                visit(dep_id)
            
            temp_visited.remove(task_id)
            visited.add(task_id)
            ordered_tasks.append(task_id)
        
        # Visit all tasks
        for task_id in task_ids:
            if task_id not in visited:
                visit(task_id)
                
        return ordered_tasks
    
    def get_max_steps(self, task_id: Optional[str] = None) -> int:
        """
        Get the maximum number of steps for a task or globally
        
        Args:
            task_id: Optional task ID to get specific max steps
            
        Returns:
            Maximum number of steps
        """
        # Default max steps
        default_max_steps = 15
        
        # Get global setting if available
        global_max_steps = self.get_global_settings().get("max_steps", default_max_steps)
        
        # If no task_id specified, return global setting
        if task_id is None:
            return global_max_steps
            
        # Get task-specific setting if available
        task = self.get_task_by_id(task_id)
        if not task:
            return global_max_steps
            
        return task.get("max_steps", global_max_steps)
    
    def should_use_summarizer(self, task_id: Optional[str] = None) -> bool:
        """
        Determine if summarizer should be used for a task or globally
        
        Args:
            task_id: Optional task ID to get specific setting
            
        Returns:
            Boolean indicating whether to use the summarizer
        """
        # Default setting
        default_setting = True
        
        # Get global setting if available
        global_setting = self.get_global_settings().get("use_summarizer", default_setting)
        
        # If no task_id specified, return global setting
        if task_id is None:
            return global_setting
            
        # Get task-specific setting if available
        task = self.get_task_by_id(task_id)
        if not task:
            return global_setting
            
        return task.get("use_summarizer", global_setting)
    
    def get_target_for_task(self, task_id: str) -> Dict[str, Any]:
        """
        Get target information for a specific task, falling back to global target if needed
        
        Args:
            task_id: The ID of the task
            
        Returns:
            Dictionary containing target system details for the task
        """
        global_target = self.get_target_info()
        
        task = self.get_task_by_id(task_id)
        if not task:
            return global_target
            
        # If task has its own target, merge with global target with task target taking precedence
        task_target = task.get("target", {})
        if not task_target:
            return global_target
            
        return {**global_target, **task_target}
    
    def get_output_dir(self) -> str:
        """
        Get the output directory for attack results
        
        Returns:
            Path to output directory, defaults to './attack_results'
        """
        return self.get_global_settings().get("output_dir", "./attack_results")