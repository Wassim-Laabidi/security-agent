#!/usr/bin/env python3
import os
import sys
import json
import time
import argparse
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn

from config.settings import DEFAULT_ATTACK_GOALS
from utils.attack_config_parser import AttackConfigParser
from utils.attack_runner import AttackRunner
from utils.context_manager import ContextManager
from workflows.attack_workflow import run_attack_workflow

console = Console()

def print_banner():
    """Print the application banner"""
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     ██╗  █████╗ ███████╗ ██████╗ ██╗███████╗██╗  ██╗                        ║
║    ███║ ██╔══██╗██╔════╝██╔════╝ ██║██╔════╝╚██╗██╔╝                        ║
║    ╚██║ ███████║█████╗  ██║  ███╗██║███████╗ ╚███╔╝                         ║
║     ██║ ██╔══██║██╔══╝  ██║   ██║██║╚════██║ ██╔██╗                         ║
║     ██║ ██║  ██║███████╗╚██████╔╝██║███████║██╔╝ ██╗                        ║
║     ╚═╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═╝╚══════╝╚═╝  ╚═╝                        ║
║                                                                              ║
║             Autonomous Security Testing Agent                                ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    console.print(Panel(banner, border_style="red"))

def print_attack_goals():
    """Print available attack goals"""
    table = Table(title="Available Attack Goals")
    
    table.add_column("ID", style="dim")
    table.add_column("Goal Description", style="green")
    
    for i, goal in enumerate(DEFAULT_ATTACK_GOALS):
        table.add_row(str(i+1), goal)
    
    console.print(table)

def select_attack_goal() -> str:
    """Allow user to select an attack goal"""
    print_attack_goals()
    
    while True:
        try:
            choice = console.input("\n[bold]Select a goal by ID or enter a custom goal:[/bold] ")
            
            # Check if choice is a number
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(DEFAULT_ATTACK_GOALS):
                    return DEFAULT_ATTACK_GOALS[idx]
                else:
                    console.print("[red]Invalid selection. Please try again.[/red]")
            else:
                # Custom goal
                if len(choice.strip()) > 10:
                    return choice.strip()
                else:
                    console.print("[red]Custom goal must be at least 10 characters long.[/red]")
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")

def display_tasks(tasks: List[Dict[str, Any]]):
    """Display available tasks from the configuration file"""
    table = Table(title="Available Attack Tasks")
    
    table.add_column("ID", style="dim")
    table.add_column("Name", style="blue")
    table.add_column("Category", style="green")
    table.add_column("Description", style="yellow")
    
    for task in tasks:
        table.add_row(
            task["id"],
            task["name"],
            task.get("category", "general"),
            task.get("goal", "No description")
        )
    
    console.print(table)

def select_task(tasks: List[Dict[str, Any]]) -> str:
    """Allow user to select a task from the config file"""
    display_tasks(tasks)
    
    task_ids = [task["id"] for task in tasks]
    
    while True:
        try:
            choice = console.input("\n[bold]Select a task ID:[/bold] ")
            if choice in task_ids:
                return choice
            else:
                console.print("[red]Invalid task ID. Please try again.[/red]")
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")

def display_attack_results(results: Dict[str, Any]):
    """Display the attack results in a formatted manner"""
    if not results:
        console.print("[red]No results to display[/red]")
        return
    
    # Display attack summary
    console.print(Panel(f"[bold]Attack Goal:[/bold] {results.get('goal', 'N/A')}", title="Summary", border_style="blue"))
    
    # Display each attack step
    steps = results.get('history', [])
    if not steps:
        console.print("[yellow]No attack steps were performed[/yellow]")
    else:
        for i, step in enumerate(steps):
            step_panel = Panel(
                f"[bold]Command:[/bold] {step.get('command', 'N/A')}\n\n"
                f"[bold]Output:[/bold]\n{step.get('output', 'N/A')[:500]}{'...' if len(step.get('output', '')) > 500 else ''}",
                title=f"Step {i+1}: {step.get('plan', 'Action')}",
                border_style="green"
            )
            console.print(step_panel)
    
    # Display vulnerabilities found
    vulnerabilities = results.get('vulnerabilities', [])
    if vulnerabilities:
        vuln_table = Table(title="Vulnerabilities Found")
        vuln_table.add_column("Type", style="red")
        vuln_table.add_column("Description", style="yellow")
        
        for vuln in vulnerabilities:
            vuln_table.add_row(
                vuln.get('type', 'Unknown'),
                vuln.get('description', 'No description available')
            )
        
        console.print(vuln_table)
    else:
        console.print("[green]No vulnerabilities were found[/green]")
    
    # Save results to file
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"results/attack_results_{timestamp}.json"
    
    os.makedirs("results", exist_ok=True)
    with open(filename, "w") as f:
        json.dump(results, f, indent=2)
    
    console.print(f"\n[blue]Results saved to: {filename}[/blue]")

def run_single_task(task_id: str, config_parser: AttackConfigParser, verbose: bool = False):
    """Run a single task from the attack configuration"""
    runner = AttackRunner(verbose=verbose)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        transient=True,
    ) as progress:
        prog_task = progress.add_task(f"[green]Running task {task_id}...", total=None)
        
        try:
            # Load configuration and run only the specified task
            runner.load_attack_config(config_parser.get_output_dir() + "/attack_tasks.json")
            results = runner.run_attack(config_parser.get_output_dir() + "/attack_tasks.json")
            task_result = results["tasks"].get(task_id, {"error": f"Task {task_id} not found in results"})
            progress.update(prog_task, completed=True, description=f"[green]Task {task_id} completed!")
            return task_result
        except Exception as e:
            progress.update(prog_task, completed=True, description=f"[red]Task {task_id} failed!")
            console.print(f"[red]Error: {str(e)}[/red]")
            return None

def run_multiple_tasks(task_ids: List[str], config_parser: AttackConfigParser, verbose: bool = False):
    """Run multiple tasks from the attack configuration"""
    runner = AttackRunner(verbose=verbose)
    all_results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        transient=True,
    ) as progress:
        prog_task = progress.add_task(f"[green]Running all tasks...", total=None)
        
        try:
            # Run all tasks in the configuration
            runner.load_attack_config(config_parser.get_output_dir() + "/attack_tasks.json")
            results = runner.run_attack(config_parser.get_output_dir() + "/attack_tasks.json")
            for task_id in task_ids:
                task_result = results["tasks"].get(task_id, {"error": f"Task {task_id} not found in results"})
                all_results.append({"task_id": task_id, "results": task_result})
            progress.update(prog_task, completed=True, description=f"[green]All tasks completed!")
        except Exception as e:
            progress.update(prog_task, completed=True, description=f"[red]Tasks failed!")
            console.print(f"[red]Error: {str(e)}[/red]")
    
    return all_results
    
def run_traditional_attack(goal: str, verbose: bool = False, max_steps: Optional[int] = None):
    """Run a traditional attack with a goal (for backward compatibility)"""
    context_manager = ContextManager()
    context_manager.set_attack_goal(goal)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("[green]Running security test...", total=None)
        
        try:
            # Call run_attack_workflow with only the parameters it accepts
            results = run_attack_workflow(
                goal=goal,
                context_manager=context_manager,
                verbose=verbose,
                max_steps=max_steps
            )
            
            progress.update(task, completed=True, description="[green]Security test completed!")
            return results
        except Exception as e:
            progress.update(task, completed=True, description="[red]Security test failed!")
            console.print(f"[red]Error: {str(e)}[/red]")
            return None

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="AutoAttacker - Autonomous Security Testing Agent")
    parser.add_argument("--goal", "-g", type=str, help="Security testing goal (traditional mode)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    parser.add_argument("--max-steps", "-m", type=int, default=None, help="Maximum number of attack steps")
    parser.add_argument("--config", "-c", type=str, help="Path to attack configuration file")
    parser.add_argument("--task", "-t", type=str, help="Task ID to run from configuration file")
    parser.add_argument("--run-all", "-a", action="store_true", help="Run all tasks in the configuration file")
    
    return parser.parse_args()

def main():
    """Main entry point for the application"""
    args = parse_arguments()
    
    print_banner()
    
    # Check if we're using the new task-based approach or traditional mode
    if args.config:
        # New task-based mode
        config_parser = AttackConfigParser()  # Initialize without arguments
        try:
            config_parser.load_from_file(args.config)  # Load the config file
            
            if not config_parser.get_tasks():  # Check if there are tasks defined
                console.print("[red]Error: No tasks found in configuration file.[/red]")
                sys.exit(1)
            
            if args.task:
                # Run a specific task
                console.print(f"\n[bold]Running task:[/bold] {args.task}\n")
                results = run_single_task(args.task, config_parser, args.verbose)
                if results:
                    display_attack_results(results)
            elif args.run_all:
                # Run all tasks
                console.print("\n[bold]Running all tasks in configuration[/bold]\n")
                task_ids = config_parser.resolve_task_order()  # Get task IDs in dependency order
                all_results = run_multiple_tasks(task_ids, config_parser, args.verbose)
                
                # Display a summary of all tasks
                table = Table(title="Task Execution Summary")
                table.add_column("Task ID", style="dim")
                table.add_column("Status", style="green")
                table.add_column("Vulnerabilities", style="red")
                
                for result in all_results:
                    task_id = result["task_id"]
                    task_results = result["results"]
                    status = "Completed" if task_results else "Failed"
                    vuln_count = len(task_results.get("vulnerabilities", [])) if task_results else 0
                    
                    table.add_row(task_id, status, str(vuln_count))
                
                console.print(table)
            elif args.interactive:
                # Interactive task selection
                tasks = config_parser.get_tasks()
                task_id = select_task(tasks)
                console.print(f"\n[bold]Running task:[/bold] {task_id}\n")
                results = run_single_task(task_id, config_parser, args.verbose)
                if results:
                    display_attack_results(results)
            else:
                console.print("[red]Error: Please specify a task ID with --task or use --run-all to run all tasks.[/red]")
        except Exception as e:
            console.print(f"[red]Error loading configuration: {str(e)}[/red]")
            sys.exit(1)
    else:
        # Traditional mode
        goal = args.goal
        if not goal:
            if args.interactive:
                goal = select_attack_goal()
            else:
                console.print("[red]Error: No goal specified. Use --goal or --interactive, or use --config for task-based mode.[/red]")
                sys.exit(1)
        
        console.print(f"\n[bold]Starting security test with goal:[/bold] {goal}\n")
        
        results = run_traditional_attack(
            goal=goal,
            verbose=args.verbose,
            max_steps=args.max_steps
        )
        
        if results:
            display_attack_results(results)

if __name__ == "__main__":
    main()