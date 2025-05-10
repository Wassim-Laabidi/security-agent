"""
Attack Runner

This module provides functionality to run attacks defined in JSON configuration files.
It orchestrates the execution of multiple attack tasks based on their dependencies
and configurations.
"""

import os
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from utils.attack_config_parser import AttackConfigParser
from utils.context_manager import ContextManager
from workflows.attack_workflow import run_attack_workflow

class AttackRunner:
    """
    Runner for executing attacks defined in configuration files
    """
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the attack runner
        
        Args:
            verbose: Enable verbose output
        """
        self.config_parser = AttackConfigParser()
        self.context_manager = ContextManager()
        self.verbose = verbose
        self.results = {
            "tasks": {},
            "summary": {},
            "start_time": "",
            "end_time": "",
            "duration_seconds": 0
        }
    
    def load_attack_config(self, config_file: str) -> bool:
        """
        Load attack configuration from a JSON file
        
        Args:
            config_file: Path to the JSON configuration file
            
        Returns:
            True if configuration was loaded successfully, False otherwise
        """
        try:
            self.config_parser.load_from_file(config_file)
            return True
        except Exception as e:
            print(f"Error loading attack configuration: {str(e)}")
            return False
    
    def run_attack(self, config_file: str) -> Dict[str, Any]:
        """
        Run the complete attack scenario defined in the configuration file
        
        Args:
            config_file: Path to the JSON configuration file
            
        Returns:
            Dictionary containing the attack results
        """
        if not self.load_attack_config(config_file):
            return {"error": "Failed to load attack configuration"}
        
        # Record start time
        start_time = time.time()
        self.results["start_time"] = datetime.now().isoformat()
        
        # Create output directory if it doesn't exist
        output_dir = self.config_parser.get_output_dir()
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # Get the order in which tasks should be executed
            task_order = self.config_parser.resolve_task_order()
            
            if self.verbose:
                print(f"Executing tasks in order: {task_order}")
            
            # Initialize task results
            self.results["tasks"] = {}
            
            # Execute each task in order
            for task_id in task_order:
                task_result = self._run_task(task_id)
                self.results["tasks"][task_id] = task_result
                
                # Save intermediate results
                self._save_results(output_dir)
        
        except Exception as e:
            print(f"Error executing attack: {str(e)}")
            self.results["error"] = str(e)
        
        # Calculate execution time
        end_time = time.time()
        duration = end_time - start_time
        
        # Update results
        self.results["end_time"] = datetime.now().isoformat()
        self.results["duration_seconds"] = duration
        
        # Generate summary
        summary = self._generate_summary()
        self.results["summary"] = summary
        
        # Save final results
        self._save_results(output_dir)
        
        return self.results
    
    def _run_task(self, task_id: str) -> Dict[str, Any]:
        """
        Run a specific task
        
        Args:
            task_id: ID of the task to run
            
        Returns:
            Dictionary containing the task results
        """
        task = self.config_parser.get_task_by_id(task_id)
        if not task:
            return {"error": f"Task {task_id} not found"}
        
        if self.verbose:
            print(f"Executing task {task_id}: {task.get('name', 'Unnamed task')}")
            print(f"Goal: {task.get('goal', 'No goal specified')}")
        
        # Get task-specific settings
        max_steps = self.config_parser.get_max_steps(task_id)
        use_summarizer = self.config_parser.should_use_summarizer(task_id)
        
        # Update target settings based on task configuration
        task_target = self.config_parser.get_target_for_task(task_id)
        
        # Create a new context manager for this task
        context_manager = ContextManager()
        context_manager.set_attack_goal(task["goal"])
        
        task_start_time = time.time()
        
        # Execute the task
        results = run_attack_workflow(
            goal=task["goal"],
            context_manager=context_manager,
            verbose=self.verbose,
            max_steps=max_steps
        )
        
        task_duration = time.time() - task_start_time
        
        # Prepare task result
        task_result = {
            "name": task.get("name", "Unnamed task"),
            "category": task.get("category", "uncategorized"),
            "goal": task.get("goal", "No goal specified"),
            "goal_reached": results.get("goal_reached", False),
            "steps_executed": results.get("step_count", 0),
            "max_steps": max_steps,
            "duration_seconds": task_duration,
            "vulnerabilities": results.get("vulnerabilities", []),
            "history": results.get("history", []),
            "error": results.get("error", "")
        }
        
        return task_result
    
    def _generate_summary(self) -> Dict[str, Any]:
        """
        Generate a summary of the attack results
        
        Returns:
            Dictionary containing the attack summary
        """
        task_results = self.results.get("tasks", {})
        
        # Count tasks by category
        categories = {}
        for task_id, result in task_results.items():
            category = result.get("category", "uncategorized")
            if category not in categories:
                categories[category] = {
                    "total": 0,
                    "completed": 0,
                    "vulnerabilities": 0
                }
            
            categories[category]["total"] += 1
            if result.get("goal_reached", False):
                categories[category]["completed"] += 1
            
            categories[category]["vulnerabilities"] += len(result.get("vulnerabilities", []))
        
        # Count total vulnerabilities
        total_vulnerabilities = sum(
            len(result.get("vulnerabilities", [])) 
            for result in task_results.values()
        )
        
        # Calculate overall completion rate
        total_tasks = len(task_results)
        completed_tasks = sum(
            1 for result in task_results.values() 
            if result.get("goal_reached", False)
        )
        
        completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
        
        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": completion_rate,
            "total_vulnerabilities": total_vulnerabilities,
            "categories": categories
        }
    
    def _save_results(self, output_dir: str) -> None:
        """
        Save the results to a file
        
        Args:
            output_dir: Directory to save the results to
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = os.path.join(output_dir, f"attack_results_{timestamp}.json")
        
        try:
            with open(filename, "w") as f:
                json.dump(self.results, f, indent=2)
                
            if self.verbose:
                print(f"Results saved to {filename}")
        except Exception as e:
            print(f"Error saving results: {str(e)}")